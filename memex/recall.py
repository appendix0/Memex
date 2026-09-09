"""Recall: search over every Book. Embeddings via local Ollama; keyword fallback.

The index is a JSON file under state/ keyed by slug and content hash, so it
rebuilds only what changed and never disagrees with the files for long.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import urllib.request
from dataclasses import dataclass

from .library import STATE, Book, books

OLLAMA = "http://127.0.0.1:11434"
MODEL = "bge-m3"
INDEX = STATE / "recall-index.json"
CHUNK = 1200          # chars; a Book section is usually under this
STANDALONE = 200      # a paragraph this long is a claim, and gets its own vector


@dataclass
class Hit:
    slug: str
    title: str
    score: float
    excerpt: str
    vault: bool
    kind: str = "agreed"      # agreed | observed | appendix


def _embed(text: str) -> list[float] | None:
    req = urllib.request.Request(
        f"{OLLAMA}/api/embeddings",
        data=json.dumps({"model": MODEL, "prompt": text}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.load(r).get("embedding")
    except Exception:
        return None


def _kind_at(body: str, pos: int) -> str:
    """Which layer of the Book this offset falls in.

    Generous capture is only safe if selection can tell the layers apart. A
    curated fact and an auto-captured observation are different KINDS of claim,
    and a reader ranking them equally is reading a log, not a record.
    """
    head = body[:pos]
    last = None
    for m in re.finditer(r"^## (Observed|Trail|Timeline)\s*$", head, re.M):
        last = m.group(1)
    if last == "Observed":
        return "observed"
    if last in ("Trail", "Timeline"):
        return "appendix"
    return "agreed"


def _facets(b: Book) -> str:
    """The Book's descriptors, as text the index can match on.

    Layer 2 of brain/CLASSIFICATION.md. `about:` is what ties Books that no
    longer share a shelf -- six Books about the owner sat on six shelves and now sit
    on one -- so unless the facet is searchable the tie exists only on paper.
    The shelf goes in too: it used to be findable as a word in the path.
    """
    fm = b.frontmatter
    parts = [b.slug.split("/")[0]]
    for key in ("about", "kind", "status", "domain"):
        v = fm.get(key)
        if not v:
            continue
        parts.extend(v if isinstance(v, list) else [str(v)])
    return " ".join(str(p) for p in parts)


def _chunks(b: Book) -> list[tuple[str, str]]:
    """(text, kind) per chunk, kind being agreed | observed | appendix."""
    text = f"{b.title}\n\n{b.body}"
    offset = len(b.title) + 2
    parts: list[tuple[str, str]] = []
    cur, cur_at = "", offset
    for para in re.split(r"\n\s*\n", text):
        # A fact must never share a vector with an unrelated fact. Facts are
        # appended to a Book as separate paragraphs, and packing several into
        # one chunk gives them ONE vector that represents all of them, so each
        # is diluted by its neighbours and none of them ranks.
        #
        # Measured 2026-09-09: "the vault privacy guard was hardcoded to three
        # names" sat in a 1,044-char chunk that opened with an unrelated fact
        # about hook signatures. Asked "what was the vault privacy guard
        # hardcoded to before", that chunk scored 0.453 and lost to a Book that
        # does not contain the answer at all (0.493). The content was embedded;
        # it was simply unreachable.
        #
        # So a paragraph that is a claim in its own right gets its own vector.
        # Short fragments -- headings, list items, one-liners -- still pack, or
        # the index would triple for no gain.
        if len(para.strip()) >= STANDALONE and cur:
            parts.append((cur.strip(), _kind_at(b.body, max(cur_at - offset, 0))))
            cur, cur_at = "", offset + (text.find(para) if para in text else cur_at)
        if len(cur) + len(para) > CHUNK and cur:
            parts.append((cur.strip(), _kind_at(b.body, max(cur_at - offset, 0))))
            cur, cur_at = "", offset + text.index(para) if para in text else cur_at
        if not cur:
            cur_at = offset + (text.find(para) if para else 0)
        cur += para + "\n\n"
    if cur.strip():
        parts.append((cur.strip(), _kind_at(b.body, max(cur_at - offset, 0))))
    return parts


# Bumped whenever a chunk's SHAPE changes. The content hash cannot notice that:
# adding `kind` to every chunk left 49 Books "unchanged" and every observation
# still labelled agreed, which is worse than no label at all.
INDEX_VERSION = 4


def _load() -> dict:
    if INDEX.exists():
        try:
            return json.loads(INDEX.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def reindex(verbose: bool = False) -> tuple[int, int]:
    """Embed changed Books. Returns (books_indexed, books_unchanged)."""
    STATE.mkdir(exist_ok=True)
    idx = _load()
    if idx.get("__version__") != INDEX_VERSION:
        idx = {"__version__": INDEX_VERSION}      # format changed: rebuild all
    seen, changed, same = set(), 0, 0
    for b in books():
        seen.add(b.slug)
        # Frontmatter is part of the key. Keyed on the body alone, flipping a
        # Book to `visibility: vault` left the cached vault=False in place and
        # `recall --no-vault` kept returning it. (codex review, 2026-09-07)
        # The facets join it for the same reason: they are indexed text now, so
        # retagging a Book's `about:` has to invalidate its chunks or the new
        # tie is unsearchable until something else edits the body.
        h = hashlib.sha256(
            f"{b.body}\x00{b.visibility}\x00{b.title}\x00{_facets(b)}"
            .encode()).hexdigest()[:16]
        if idx.get(b.slug, {}).get("hash") == h:
            same += 1
            continue
        vecs = []
        for c, kind in _chunks(b):
            v = _embed(c)
            vecs.append({"text": c, "vec": v, "kind": kind})
        # The facets are scored, never shown. Folded into a chunk instead they
        # matched fine but every excerpt then opened with "notes owner", which is
        # index plumbing leaking into what a reader sees.
        ftext = _facets(b)
        idx[b.slug] = {"hash": h, "title": b.title, "vault": b.vault,
                       "chunks": vecs, "facets": ftext,
                       "fvec": _embed(f"{b.title}\n{ftext}")}
        changed += 1
        if verbose:
            print(f"  indexed {b.slug} ({len(vecs)} chunks)")
    for slug in list(idx):
        if slug != "__version__" and slug not in seen:
            del idx[slug]
    idx["__version__"] = INDEX_VERSION
    INDEX.write_text(json.dumps(idx))
    return changed, same


def _cos(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)); nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def _keyword(q: str, text: str) -> float:
    words = [w for w in re.findall(r"\w+", q.lower()) if len(w) > 2]
    if not words:
        return 0.0
    t = text.lower()
    return sum(t.count(w) for w in words) / (len(words) * (1 + len(t) / 2000))


# A curated fact outranks an observation at equal similarity. Not a filter --
# the observation is still findable, it just does not outrank what the owner approved.
_WEIGHT = {"agreed": 1.0, "observed": 0.92, "appendix": 0.88}


def search(query: str, limit: int = 5, include_vault: bool = True,
           kinds: set[str] | None = None) -> list[Hit]:
    idx = _load()
    if not idx:
        reindex()
        idx = _load()
    qv = _embed(query)
    hits: list[Hit] = []
    for slug, rec in idx.items():
        if slug == "__version__" or not isinstance(rec, dict):
            continue
        if rec["vault"] and not include_vault:
            continue
        best, best_text, best_kind = 0.0, "", "agreed"
        for c in rec["chunks"]:
            kind = c.get("kind", "agreed")
            if kinds and kind not in kinds:
                continue
            raw = _cos(qv, c["vec"]) if (qv and c.get("vec")) else _keyword(query, c["text"])
            s = raw * _WEIGHT.get(kind, 1.0)
            if s > best:
                best, best_text, best_kind = s, c["text"], kind
        # A facet match says the Book is ON the subject, which the body may
        # never state -- notes/owner-routine never says "owner". Discounted below a
        # real body match so it surfaces a Book without outranking one that
        # actually discusses the query.
        # Not applied under an explicit `kinds` filter: the facets belong to
        # no layer, so letting them score would quietly defeat the filter.
        fraw = 0.0 if kinds else (_cos(qv, rec["fvec"]) if (qv and rec.get("fvec"))
                                  else _keyword(query, rec.get("facets", "")))
        if fraw * 0.95 > best:
            best = fraw * 0.95
            if not best_text:
                best_text = rec["chunks"][0]["text"] if rec["chunks"] else rec["title"]
        if best > 0:
            hits.append(Hit(slug, rec["title"], round(best, 3),
                            best_text[:240].replace("\n", " "), rec["vault"], best_kind))
    hits.sort(key=lambda h: -h.score)
    return hits[:limit]
