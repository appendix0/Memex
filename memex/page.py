"""Render the Library as one self-contained HTML page, readable over file://.

Vault Books are AES-GCM encrypted into the page behind a passphrase the owner types at
build time. Without that passphrase their titles and text are not recoverable
from the file, so the page satisfies ACCESS_POLICY.md even if it is copied off
the box. That is the only real protection here: a page that merely *hides* vault
text in the DOM protects nothing.

This page is still a local artifact. It is never pushed, served, or published.

Beyond memex's PyYAML this uses `markdown` and `cryptography`, both already
installed on this machine. Run:

    python3 -m memex.page            # prompts for the passphrase
    python3 -m memex.page --open     # ... and prints the file:// URL
"""
from __future__ import annotations

import argparse
import base64
import getpass
import hmac
import html
import json
import os
import re
import secrets
import sys
from pathlib import Path

import markdown
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from .library import books, ROOT, BRAIN

PBKDF2_ITERATIONS = 300_000
VERIFY_ITERATIONS = 200_000
DEFAULT_OUT = ROOT / "library.html"
VERIFIER = Path.home() / ".local" / "share" / "memex" / "vault.verifier"

_WIKILINK = re.compile(r"\[\[([^\]]+)\]\]")
_FENCE = re.compile(r"^\s*(```|~~~)")


# --------------------------------------------------------------------------
# markdown -> html, with [[wikilinks]] turned into clickable book links
# --------------------------------------------------------------------------

def _resolve(target: str, slugs: set[str], by_basename: dict[str, str]) -> str | None:
    """A wikilink target -> a real slug, or None when it dangles."""
    t = target.split("|")[0].split("#")[0].strip().lstrip("./")
    if t in slugs:
        return t
    return by_basename.get(t)


def _linkify(md_text: str, slugs: set[str],
             by_basename: dict[str, str]) -> tuple[str, list[str]]:
    """Swap [[x]] for a placeholder, never inside a fenced code block.

    The anchor HTML is held aside and put back after conversion, so the
    converter itself can run with raw HTML disabled.
    """
    out, anchors, in_fence = [], [], False
    for line in md_text.split("\n"):
        if _FENCE.match(line):
            in_fence = not in_fence
        if in_fence:
            out.append(line)
            continue

        def sub(m: re.Match) -> str:
            raw = m.group(1)
            label = raw.split("|")[-1] if "|" in raw else raw
            slug = _resolve(raw, slugs, by_basename)
            if slug is None:
                a = (f'<a class="wl dangling" title="no Book at this link yet">'
                     f'{html.escape(label)}</a>')
            else:
                a = (f'<a class="wl" href="#{html.escape(slug)}" '
                     f'data-slug="{html.escape(slug)}">{html.escape(label)}</a>')
            anchors.append(a)
            return f"MEMEXWL{len(anchors) - 1}ENDWL"

        out.append(_WIKILINK.sub(sub, line))
    return "\n".join(out), anchors


_STATE = re.compile(r"^(## (?:State|Rules)\s*\n)(.*?)(?=^## |\Z)", re.S | re.M)


def _keep_field_breaks(md_text: str) -> str:
    """`## State` is line-per-field, and markdown would run those into one
    paragraph. Give each line a hard break so it reads as written."""
    def fix(m: re.Match) -> str:
        body = "\n".join(
            ln + "  " if ln.strip() and not ln.rstrip().endswith("  ") else ln
            for ln in m.group(2).split("\n"))
        return m.group(1) + body
    return _STATE.sub(fix, md_text)


def _render(md_text: str, slugs: set[str], by_basename: dict[str, str]) -> str:
    if not md_text.strip():
        return ""
    body, anchors = _linkify(_keep_field_breaks(md_text), slugs, by_basename)
    md = markdown.Markdown(extensions=["tables", "fenced_code", "sane_lists"])
    # A Book is rendered into innerHTML on a page that holds the vault
    # passphrase in sessionStorage, and papers/ and sources/ carry third-party
    # material an agent filed. Raw HTML in a Book would therefore be stored
    # XSS, so it renders as text. attr_list is dropped for the same reason:
    # it can attach an onclick to any element.
    md.preprocessors.deregister("html_block")
    md.inlinePatterns.deregister("html")
    out = md.convert(body)
    for i, a in enumerate(anchors):
        out = out.replace(f"MEMEXWL{i}ENDWL", a)
    return out


# --------------------------------------------------------------------------
# the Library -> records the page can render
# --------------------------------------------------------------------------

def _split_body(body: str) -> tuple[str, str]:
    """Above the line: compiled truth. Below it: the append-only appendix."""
    parts = re.split(r"\n---\s*\n", body, maxsplit=1)
    return (parts[0], parts[1] if len(parts) > 1 else "")


def build_records() -> list[dict]:
    bs = books(include_resolvers=True)
    slugs = {b.slug for b in bs}
    seen: dict[str, str] = {}
    for b in bs:                                   # basename -> slug, when unambiguous
        base = b.slug.split("/")[-1]
        seen[base] = "" if base in seen else b.slug
    by_basename = {k: v for k, v in seen.items() if v}

    records = []
    for b in bs:
        facts, appendix = _split_body(b.body)
        links = [s for s in (_resolve(t, slugs, by_basename)
                             for t in b.links()) if s and s != b.slug]
        records.append({
            "slug": b.slug,
            "shelf": b.slug.split("/")[0] if "/" in b.slug else "root",
            "title": b.title,
            "type": b.type,
            "created": str(b.frontmatter.get("created", "")),
            "vault": b.vault,
            "words": len(b.body.split()),
            "facts": _render(facts, slugs, by_basename),
            "appendix": _render(appendix, slugs, by_basename),
            "text": (b.title + "\n" + b.body).lower(),
            "links": sorted(set(links)),
        })

    # backlinks: who points here
    back: dict[str, list[str]] = {r["slug"]: [] for r in records}
    for r in records:
        for target in r["links"]:
            back[target].append(r["slug"])
    for r in records:
        r["backlinks"] = sorted(back[r["slug"]])
    return records


# --------------------------------------------------------------------------
# encryption of the vault half
# --------------------------------------------------------------------------

def derive(passphrase: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    salt = salt or os.urandom(16)
    key = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                     iterations=PBKDF2_ITERATIONS).derive(passphrase.encode())
    return key, salt


def encrypt(payload: str, key: bytes, salt: bytes) -> dict:
    """Re-encrypting live needs a fresh iv every time; never reuse one."""
    iv = os.urandom(12)
    ct = AESGCM(key).encrypt(iv, payload.encode(), None)
    b64 = lambda raw: base64.b64encode(raw).decode()
    return {"salt": b64(salt), "iv": b64(iv), "ct": b64(ct),
            "iterations": PBKDF2_ITERATIONS}


def _verifier_for(passphrase: str, salt: bytes) -> bytes:
    return PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt,
                      iterations=VERIFY_ITERATIONS).derive(passphrase.encode())


def check_or_enrol(passphrase: str) -> bool:
    """The passphrase has to be a secret, not just a key the caller picks.

    Without this the vault is not protected at all from anything that can
    reach the port: it could POST a passphrase of its own, get the payload
    back encrypted under that passphrase, and read every vault Book. So the
    first passphrase enrols and every later one must match it.

    The file holds a salt and a PBKDF2 hash. It never holds the passphrase and
    never holds the encryption key, so it cannot decrypt anything -- it can
    only say yes or no. Enrolment is the one open moment: whoever sets the
    passphrase first owns it, so set it yourself right after a reboot.
    """
    if VERIFIER.exists():
        try:
            rec = json.loads(VERIFIER.read_text())
            want = base64.b64decode(rec["hash"])
            got = _verifier_for(passphrase, base64.b64decode(rec["salt"]))
        except (ValueError, KeyError):
            return False
        return hmac.compare_digest(want, got)

    salt = os.urandom(16)
    VERIFIER.parent.mkdir(parents=True, exist_ok=True)
    VERIFIER.write_text(json.dumps({
        "salt": base64.b64encode(salt).decode(),
        "hash": base64.b64encode(_verifier_for(passphrase, salt)).decode(),
        "iterations": VERIFY_ITERATIONS,
    }))
    VERIFIER.chmod(0o600)
    return True


def read_passphrase() -> str:
    """Never through an argument or the environment of a logged session."""
    env = os.environ.get("MEMEX_PAGE_PASSPHRASE")
    if env:
        return env
    if not sys.stdin.isatty():
        sys.exit("no tty: run this in a terminal, or set MEMEX_PAGE_PASSPHRASE")
    while True:
        a = getpass.getpass("passphrase for the vault Books: ")
        if not a:
            print("  empty — try again")
            continue
        if a != getpass.getpass("again: "):
            print("  they differ — try again")
            continue
        return a


# --------------------------------------------------------------------------

def _embed(obj) -> str:
    """JSON for a <script> block: '</' would end the element early."""
    return json.dumps(obj, ensure_ascii=False).replace("</", "<\\/")


def _tokenise(public: list[dict], vault_slugs: set[str]) -> dict[str, str]:
    """A locked vault leaks nothing, and a slug names a person.

    Public Books wiki-link to vault Books, so the raw slug would sit in the
    clear. Swap every such reference for an opaque per-build token; the
    token -> slug map ships inside the encrypted blob, so the links come back
    the moment the vault is unlocked and stay meaningless until then.
    """
    tokens = {slug: secrets.token_hex(8) for slug in sorted(vault_slugs)}
    for r in public:
        for field in ("facts", "appendix"):
            for slug, tok in tokens.items():
                r[field] = re.sub(
                    rf'<a class="wl" href="#{re.escape(slug)}" '
                    rf'data-slug="{re.escape(slug)}">[^<]*</a>',
                    f'<a class="wl vaultref" data-vault="{tok}">vault</a>',
                    r[field])
        for field in ("links", "backlinks"):
            r[field] = [f"vault:{tokens[s]}" if s in tokens else s for s in r[field]]
        for slug, tok in tokens.items():
            r["text"] = r["text"].replace(slug.lower(), f"vault:{tok}")
    return tokens


def blobs(key: bytes | None, salt: bytes | None) -> tuple[list, dict | None, dict]:
    """Read the Library from disk and split it into public / encrypted / counts."""
    records = build_records()
    public = [r for r in records if not r["vault"]]
    vault = [r for r in records if r["vault"]]

    n_vault = len(vault)
    # Tokenise first and unconditionally: public Books wiki-link to vault ones,
    # and a slug names a person, so the reference must never sit in the clear
    # whether or not a key exists to unlock it.
    tokens = _tokenise(public, {r["slug"] for r in vault}) if vault else {}

    if vault and key is None:
        # No key: vault Books are left out whole. Even a placeholder would put
        # their titles and slugs in the clear.
        locked, vault = None, []
    elif vault:
        for r in vault:
            for field in ("links", "backlinks"):
                r[field] = [s for s in r[field] if not s.startswith("vault:")]
        payload = {"books": vault, "tokens": {t: s for s, t in tokens.items()}}
        locked = encrypt(json.dumps(payload, ensure_ascii=False), key, salt)
    else:
        locked = None

    counts = {"total": len(records), "vault": n_vault,
              "built": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")}
    return public, locked, counts


def fingerprint() -> str:
    """Cheap 'did the Library change' probe: every Book path and mtime."""
    import hashlib
    h = hashlib.sha256()
    for p in sorted(BRAIN.rglob("*.md")):
        h.update(f"{p}:{p.stat().st_mtime_ns}".encode())
    return h.hexdigest()[:16]


def page_version() -> str:
    """Changes when the page itself is rebuilt, so open tabs can reload."""
    st = (Path(__file__).parent / "page.template.html").stat()
    return f"{st.st_mtime_ns}-{st.st_size}"


def render(public, locked, counts) -> str:
    template = (Path(__file__).parent / "page.template.html").read_text(encoding="utf-8")
    return (template
            .replace("__PUBLIC__", _embed(public))
            .replace("__LOCKED__", _embed(locked))
            .replace("__COUNTS__", _embed(counts)))


def build(out: Path, passphrase: str | None) -> Path:
    records = build_records()
    key, salt = derive(passphrase) if passphrase else (None, None)
    public, locked, counts = blobs(key, salt)
    out.write_text(render(public, locked, counts), encoding="utf-8")
    out.chmod(0o600)
    return out, counts["total"]


def serve(port: int, passphrase: str | None) -> None:   # noqa: C901
    """A viewer on the loopback interface only.

    ACCESS_POLICY.md is wary of servers, and rightly: a server is how "the agent
    can read the vault" becomes "any surface can". Two things hold that line
    here -- the socket is bound to 127.0.0.1 so nothing off this box can reach
    it, and vault Books still leave this process as ciphertext the browser
    decrypts. Reach it from another device by forwarding the port over ssh,
    never by binding a public interface.
    """
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from urllib.parse import urlparse

    # The key lives in memory for the life of this process and is never written
    # to disk. Set it from the page; a reboot asks again. That is the whole
    # reason there is no keyfile to steal.
    vault: dict = {"key": None, "salt": None}
    if passphrase:
        vault["key"], vault["salt"] = derive(passphrase)
    cache: dict = {"fp": None, "body": None, "keyed": False}

    def library() -> bytes:
        fp, keyed = fingerprint(), vault["key"] is not None
        if fp != cache["fp"] or keyed != cache["keyed"]:
            public, locked, counts = blobs(vault["key"], vault["salt"])
            counts["live"] = True
            counts["vaultSet"] = keyed
            counts["vaultEnrolled"] = VERIFIER.exists()
            cache.update(fp=fp, keyed=keyed, body=json.dumps(
                {"public": public, "locked": locked, "counts": counts},
                ensure_ascii=False).encode())
        return cache["body"]

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def _send(self, body: bytes, ctype: str) -> None:
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            route = self.path.split("?")[0]
            if route == "/":
                page = render(None, None, {"live": True}).encode()
                self._send(page, "text/html; charset=utf-8")
            elif route == "/api/version":
                self._send(json.dumps({"v": fingerprint(),
                                       "p": page_version()}).encode(),
                           "application/json")
            elif route == "/api/library":
                self._send(library(), "application/json; charset=utf-8")
            else:
                self.send_error(404)

        def do_POST(self) -> None:
            if self.path.split("?")[0] != "/api/vault":
                return self.send_error(404)
            # A page on another origin must not be able to set this. Compared
            # against this request's own Host so it still holds behind a proxy.
            origin = self.headers.get("Origin")
            if origin and urlparse(origin).netloc != self.headers.get("Host", ""):
                return self.send_error(403)
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                return self.send_error(400)
            if not 0 < n <= 4096:
                return self.send_error(400)
            try:
                given = json.loads(self.rfile.read(n)).get("passphrase") or ""
            except (ValueError, AttributeError):
                return self.send_error(400)
            if not given:
                return self.send_error(400)
            if not check_or_enrol(given):
                print("  vault passphrase refused", flush=True)
                return self.send_error(403)
            vault["key"], vault["salt"] = derive(given)
            print("  vault key set from the page", flush=True)
            self._send(json.dumps({"ok": True}).encode(), "application/json")

        def log_message(self, *a) -> None:      # one line per Book change, not per poll
            pass

    httpd = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    n = len(build_records())
    print(f"The Library — {n} Books, live from {BRAIN}")
    print(f"  on this box:  http://localhost:{port}")
    print(f"  from another device: forward local {port} -> 127.0.0.1:{port} over ssh,")
    print(f"                then open http://localhost:{port} in Safari")
    print("  ctrl-c to stop", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="render the Library as one HTML page")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--no-vault", action="store_true",
                    help="leave vault Books out entirely instead of encrypting them")
    ap.add_argument("--open", action="store_true", help="print the file:// URL")
    ap.add_argument("--serve", action="store_true",
                    help="live viewer on 127.0.0.1, always current with brain/")
    ap.add_argument("--port", type=int, default=8765)
    args = ap.parse_args(argv)

    if args.serve:
        # No prompt: the passphrase is set from the page, so this can start on
        # boot with no terminal attached.
        serve(args.port, os.environ.get("MEMEX_PAGE_PASSPHRASE"))
        return 0

    passphrase = None if args.no_vault else read_passphrase()
    out, n = build(args.out, passphrase)
    print(f"{out}  ({n} Books, mode 0600)")
    if args.open:
        print(f"file://{out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
