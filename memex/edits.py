"""Applying the Scribe's edits to Books, without letting it damage one.

The Scribe does not write files. It emits operations, and this module applies
them. That asymmetry is deliberate: a model handed a whole file will sometimes
return it shorter than it found it, and a Book that silently loses a paragraph
is worse than a Book that never gained one. Here, the only way to remove text
is to quote it exactly.

Ops (JSON, one per edit):

  {"op": "fact",     "book": "projects/x", "text": "...", "replaces": "...",
                     "provenance": "agreed"}
  {"op": "trail",    "book": "projects/x", "date": "2026-09-07", "text": "..."}
  {"op": "timeline", "book": "projects/x", "date": "2026-09-07", "text": "..."}
  {"op": "trail_file", "book": "trails/y", "body": "<the whole file>"}
  {"op": "new",      "book": "sources/z", "title": "...", "type": "source",
                     "about": ["memex"], "text": "<the abstract of the facts>"}

`fact` writes above the line; with `replaces` it substitutes that exact text,
without it appends. It ALWAYS requires provenance: agreed -- a Book holds fact,
never an agent's unconfirmed notice. Anything merely noticed goes to
`candidates.jsonl` and waits for the owner (see candidates.py). `trail` and `timeline` write below the line and are
append-only. `trail_file` is the one whole-file op, and only under trails/.
"""
from __future__ import annotations

import json
import re

import yaml
from datetime import datetime
from pathlib import Path

from .library import BRAIN, SHELF, TZ, about_terms, person_subjects

TYPES = {"person", "project", "research", "concept", "writing", "infra",
         "source", "resolver", "note"}

# RESOLVER Test 0, enforced here rather than only asked for in the prompt. A
# Book about a human cannot be created without the vault label. PROMPT.md
# already says "never write a Book about a person ... without visibility:
# vault" -- but the op had no field for it, so the rule was unenforceable and
# every person Book the Scribe made was world.
#
# Until 2026-09-08 this was a list of ten SHELF NAMES. That made privacy a
# property of a file's path: the guard had to be edited every time a shelf
# changed, and moving a Book silently moved it out of the guard's reach. The
# shelves it named were themselves the defect -- one shelf per aspect of one
# person. Privacy now travels with the Book, in facets it carries.
# See brain/CLASSIFICATION.md.
VAULT_SHELVES = {"people"}

# An `about:` naming a human means the Book is about a human, wherever it sits.
# This is what replaced `direction/ frameworks/ preferences/ routine/ service/
# corrections/ identity/ personal/` -- those Books are now notes/ with
# `about: [owner]`, and this is what still catches them.
#
# Derived from the people/ shelf rather than hardcoded: a literal
# {owner, agent} covered exactly three names and silently covered
# nobody else, which is the same defect as naming the shelves. See
# library.person_subjects().

# Bush keeps two mechanisms apart and we collapsed them into one. The STORE
# takes everything -- §2, "continuously extended"; §6, the user is told to be
# "profligate" about what goes in. The TRAIL is what needs a deliberate press
# of the button -- §7, "the process of tying two items together is the
# important thing". Applying the button to the store meant 37 of 46 runs
# recorded nothing at all.
#
#   observed  a checkable fact nobody had to assent to. APPEND-ONLY, always.
#   agreed    the owner and the agent converged, or the owner said record it. May overwrite.
#
# The owner, 2026-09-07: "append only for observed, overwrite only for agreed."

# A CAPABILITY BOUNDARY, not an instruction. The Scribe runs headless, after
# the session, with nobody to ask -- so it cannot hold the owner's word, and an
# honour-system gate ("quote both lines") is a gate the writer opens for
# itself. It may write BELOW the line and under trails/; it may never write a
# Book's facts or create a Book. Those arrive one way: the memex-input skill
# asks in the session and writes on yes. The owner, 2026-09-08.
BOOKS_ARE_OWNERS = ("the Scribe cannot write a Book -- it queues, and the owner's "
                  "word in a session writes. Emit an observe op instead.")
PROVENANCE = {"observed", "agreed"}



class Refused(ValueError):
    """The op was not applied. The Book on disk is unchanged."""


def split_book(text: str) -> tuple[str, str, str]:
    """-> (frontmatter, above the line, below the line)."""
    fm = ""
    rest = text
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end != -1:
            fm, rest = text[: end + 5], text[end + 5 :]
    parts = rest.split("\n---\n", 1)
    return fm, parts[0], (parts[1] if len(parts) > 1 else "")


def join_book(fm: str, above: str, below: str) -> str:
    above = above.rstrip("\n")
    below = below.strip("\n")
    return f"{fm}{above}\n\n---\n\n{below}\n" if below else f"{fm}{above}\n"


def _section(below: str, heading: str, entry: str, newest_first: bool) -> str:
    marker = f"## {heading}\n"
    if marker in below:
        i = below.index(marker) + len(marker)
        j = below.find("\n## ", i)
        j = len(below) if j == -1 else j
        body = below[i:j].strip("\n")
        body = f"{entry}\n\n{body}" if newest_first else f"{body}\n\n{entry}"
        return below[:i] + "\n" + body.strip("\n") + "\n" + below[j:]
    # rstrip, not strip: this is called on the ABOVE half too, whose leading
    # newline is the blank line after the frontmatter fence. join_book()
    # strips the below half anyway, so nothing is lost there.
    return below.rstrip("\n") + f"\n\n## {heading}\n\n{entry}\n"


_LEADING_DATE = re.compile(r"^\**\s*\d{4}-\d{2}-\d{2}\s*\**\s*(?:[—–-]\s*)?")


def _undate(text: str) -> str:
    """Strip a date the model put at the front; this code supplies the date.

    Left alone it renders as `**2026-09-07** — **2026-09-07** — ...`, which is
    what the first real run produced.
    """
    prev = None
    while prev != text:
        prev, text = text, _LEADING_DATE.sub("", text, count=1).strip()
    return text


def _visibility(text: str) -> str:
    """The visibility a Book's frontmatter actually declares.

    This was a substring test for "visibility: vault", which any comment or
    body line carrying the phrase satisfied -- so a replacement could declare
    `visibility: world` and still pass by mentioning vault anywhere.
    (codex structured review, 2026-09-07)
    """
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    if not m:
        return ""
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return ""
    return str(fm.get("visibility", "") or "") if isinstance(fm, dict) else ""




def _append_fact(above: str, text: str) -> str:
    """Add to the facts, but never below `## See Also`.

    That heading closes the Book with its links; a fact stranded under it reads
    as an afterthought. Every fact write lands here so they cannot disagree
    about where the curated layer actually is.
    """
    for heading in (r"\n## See Also\b",):
        m = re.search(heading, above)
        if m:
            return (above[: m.start()].rstrip("\n") + "\n\n" + text + "\n"
                    + above[m.start():])
    return above.rstrip("\n") + "\n\n" + text


def _target(rel: str) -> Path:
    rel = rel.strip().removesuffix(".md")
    if ".." in rel or rel.startswith("/"):
        raise Refused(f"path escapes the Library: {rel!r}")
    p = (BRAIN / f"{rel}.md").resolve()
    if BRAIN.resolve() not in p.parents:
        raise Refused(f"outside the Library: {rel!r}")
    return p


def apply_op(op: dict, dry: bool = False, created: set[str] | None = None,
             actor: str = "agent") -> str:
    kind = op.get("op")
    rel = op.get("book", "")
    path = _target(rel)
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    created = created if created is not None else set()
    # The canonical slug, not the one the model typed. "./people/x" has shelf
    # "." and would have slipped the vault requirement, and a symlink under
    # trails/ pointing at a project Book would have passed the prefix check
    # while resolving somewhere else entirely. (codex review, 2026-09-07)
    try:
        slug = path.relative_to(BRAIN.resolve()).with_suffix("").as_posix()
    except ValueError:
        raise Refused(f"outside the Library: {rel!r}")

    if kind == "new":
        if actor == "scribe":
            raise Refused(BOOKS_ARE_OWNERS)
        if path.exists() or slug in created:
            raise Refused(f"{rel} already exists — use fact/trail, not new")
        t = op.get("type", "note")
        if t not in TYPES:
            raise Refused(f"unknown type {t!r}")
        # One line, always. A title carrying a newline or a quote used to be
        # interpolated straight into the frontmatter, which let model output
        # inject arbitrary keys -- `visibility: world` among them.
        title = " ".join((op.get("title") or "").split())
        text = (op.get("text") or "").strip()
        if not title or not text:
            raise Refused("a new Book needs a title and a body")
        vis = (op.get("visibility") or "").strip()
        if vis and vis != "vault":
            raise Refused(f"visibility is 'vault' or absent, never {vis!r}")
        # "" is the root, where the resolvers live -- not the filename, which
        # is what split() returns for a Book with no shelf in its slug.
        shelf = slug.split("/")[0] if "/" in slug else ""
        # The shelf is the type. Refused here rather than asked for in prose,
        # because prose is what let the Library reach 20 shelves for 58 Books.
        # trails/ is the one exemption: a trail is a route, not a Book.
        want = SHELF.get(t)
        if shelf != "trails" and want is not None and shelf != want:
            raise Refused(f"a {t!r} Book belongs on {want or 'the root'}/, not "
                          f"{shelf}/ — the shelf is the type "
                          "(brain/CLASSIFICATION.md)")
        # The topic facet. A list of controlled subject slugs; see
        # brain/CLASSIFICATION.md. It is what ties Books that no longer share
        # a shelf, so it is written at creation rather than added later.
        #
        # All three checks below are stated as requirements in
        # CLASSIFICATION.md and were, until now, enforced nowhere -- which is
        # the exact defect (a rule living only in prose) that the faceted
        # scheme was written to end. A doc that claims a guarantee the code
        # does not make is worse than one that claims nothing.
        about = op.get("about") or []
        if isinstance(about, str):
            about = [about]
        if not all(isinstance(x, str) and re.fullmatch(r"[a-z0-9-]+", x) for x in about):
            raise Refused(f"about: must be lowercase slugs, not {about!r}")
        # Resolvers are the Library's own furniture -- they are about the
        # Library, not about a subject in it.
        if not about and t != "resolver":
            raise Refused(f"{rel} needs about: — the topic facet is the tie "
                          "that replaced the shelf (brain/CLASSIFICATION.md)")
        vocab = about_terms(BRAIN)
        unknown = sorted(set(about) - vocab)
        if unknown:
            raise Refused(f"about: {unknown} not in the controlled list. Add the "
                          "term to brain/CLASSIFICATION.md first, then use it")
        if (shelf in VAULT_SHELVES or t == "person"
                or set(about) & person_subjects(BRAIN)) and vis != "vault":
            raise Refused(f"{rel} is about a person; it needs visibility: vault "
                          "(RESOLVER Test 0)")
        front = {"title": title, "type": t, "created": today}
        if about:
            front["about"] = about
        if vis:
            front["visibility"] = vis
        body = ("---\n"
                + yaml.safe_dump(front, sort_keys=False, allow_unicode=True)
                + "---\n\n"
                + f"# {title}\n\n{text}\n")
        if not dry:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body, encoding="utf-8")
        created.add(slug)
        return rel

    if kind in ("trail_file", "inquiry"):     # "inquiry" kept: older receipts use it
        if not slug.startswith("trails/"):
            raise Refused(f"whole-file writes are only for trails/: {rel!r}")
        body = op.get("body") or ""
        if len(body.strip()) < 80:
            raise Refused("refusing to write an empty Inquiry")
        # Whole-file writes are the one place a Book's frontmatter is replaced
        # wholesale, so a vault Inquiry could be rewritten public by omission.
        # (codex review, 2026-09-07)
        if path.exists():
            was = path.read_text(encoding="utf-8")
            if _visibility(was) == "vault" and _visibility(body) != "vault":
                raise Refused(f"{slug} is vault; the replacement drops the label")
        if not dry:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(body.rstrip("\n") + "\n", encoding="utf-8")
        return rel

    if not path.exists():
        if dry and slug in created:
            # A dry run does not create the file, so an op that legitimately
            # follows a `new` in the same batch would otherwise be reported as
            # refused. It would apply for real.
            return rel
        raise Refused(f"{rel} does not exist — use op 'new'")
    before = path.read_text(encoding="utf-8")
    fm, above, below = split_book(before)
    text = (op.get("text") or "").strip()
    if not text:
        raise Refused("empty text")

    if kind == "fact":
        # A Book holds fact. Not an agent's notice, not a candidate, not a
        # queue. The owner, 2026-09-08: "Memex should be a base of fact, not a
        # knowledge queue stacking up from all the session." So EVERY write
        # above the line needs his word, whether it appends or supersedes.
        # Anything merely noticed goes to candidates.jsonl and waits.
        if actor == "scribe":
            raise Refused(BOOKS_ARE_OWNERS)
        if op.get("provenance") != "agreed":
            raise Refused("a Book holds fact; writing one requires provenance: "
                          "agreed (the owner's word). Queue it as a candidate instead.")
        old = op.get("replaces")
        if old:
            if old not in above:
                raise Refused("`replaces` does not appear above the line verbatim")
            above = above.replace(old, text, 1)
        else:
            # Never after `## See Also` — that closes the Book with its links,
            # and a fact stranded below it reads as an afterthought.
            above = _append_fact(above, text)
    elif kind in ("trail", "timeline"):
        # Only here: the code supplies the date for trail/timeline entries, so a
        # date the model also wrote would render twice. A FACT that legitimately
        # opens with a date must keep it. (codex structured review, 2026-09-07)
        text = _undate(text)
        date = op.get("date") or today
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            raise Refused(f"bad date {date!r}")
        entry = f"{date} — {text}" if kind == "timeline" else \
                f"**{date}** — {text}"
        below = _section(below, kind.capitalize(), entry,
                         newest_first=(kind == "timeline"))
    else:
        raise Refused(f"unknown op {kind!r}")

    after = join_book(fm, above, below)
    # The only sanctioned way to lose text is an exact `replaces`.
    if len(after) < len(before) and not op.get("replaces"):
        raise Refused("op would shorten the Book; refused")
    if not dry:
        path.write_text(after, encoding="utf-8")
    return rel


def apply_all(ops: list[dict], dry: bool = False,
              actor: str = "agent") -> tuple[list[str], list[str]]:
    """Apply in order. `new` must precede any op on the Book it creates."""
    written, refused, created = [], [], set()
    for op in sorted(ops, key=lambda o: o.get("op") != "new"):
        try:
            r = apply_op(op, dry=dry, created=created, actor=actor)
            if r not in written:
                written.append(r)
        except (Refused, OSError) as e:
            refused.append(f"{op.get('op')} {op.get('book')}: {e}")
    return written, refused


def parse_ops(answer: str) -> list[dict]:
    """Pull the ops out of the model's answer: one JSON object per line."""
    ops = []
    for m in re.finditer(r"^\s*(\{.*\})\s*$", answer, re.M):
        try:
            o = json.loads(m.group(1))
        except json.JSONDecodeError:
            continue
        if isinstance(o, dict) and "op" in o and "book" in o:
            ops.append(o)
    return ops
