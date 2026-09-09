"""What is waiting on the owner.

The one thing in MEMEX that stalls in silence. A proposal nobody answers is not
an error, produces no warning, and sits in a Book's Timeline forever. On
2026-09-07 seventeen had accumulated over a single day and the owner learned of them
only because a review counted them.

The owner: "the agent should ask me about the open agreement more loudly. I did not
know there were 17 open questions in the queue until now."
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .library import BRAIN, books

# The Scribe has written these three shapes at different points today. New
# writes use one canonical form, but the Library already holds all three and a
# reader must see every one of them.
_MARKERS = [
    re.compile(r"proposed by (?P<who>[\w ]{1,24}?), unconfirmed:\s*(?P<text>.+)", re.I),
    re.compile(r"proposed \((?P<who>[\w ]{1,24}?)\):\s*(?P<text>.+)", re.I),
    re.compile(r"\*\*proposed\*\*[:\s]+(?P<text>.+)", re.I),
]
_ANSWERED = re.compile(r"\b(confirmed|agreed|rejected|struck|resolved)\b", re.I)
# "Not yet confirmed by the owner" CONTAINS "confirmed". Reading the resolution word
# alone marked nine open questions answered and emptied the queue silently,
# which is the precise failure this module exists to prevent.
_NEGATED = re.compile(r"\b(not yet|never|un)\s*(confirmed|agreed|resolved)", re.I)


# An explicit dated marker is authoritative. Without it, a line carrying both
# "Resolved 2026-09-07" and the original "Not yet confirmed by the owner" reads as
# unanswered forever, because the negation guard cannot tell which clause is
# current -- and it is the later one, always.
_RESOLVED = re.compile(r"\bResolved \d{4}-\d{2}-\d{2}\b")


def _is_answered(line: str) -> bool:
    if _RESOLVED.search(line):
        return True
    return bool(_ANSWERED.search(line)) and not _NEGATED.search(line)


@dataclass
class Waiting:
    slug: str          # the Book it sits in
    line: int          # 1-indexed line number
    text: str          # what is being asked
    where: str         # "timeline" | "open"

    def gist(self, width: int = 150) -> str:
        """First sentence, enough to decide whether to open it."""
        t = " ".join(self.text.split())
        cut = t.find(". ")
        if 40 < cut < width:
            t = t[: cut + 1]
        return t if len(t) <= width else t[: width - 1].rstrip() + "…"


def _from_timeline(path: Path, slug: str) -> list[Waiting]:
    out = []
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        # `A or B and C` binds as `A or (B and C)`, so a line carrying BOTH a
        # resolution word and "not yet confirmed" stayed in the queue forever.
        # A resolution word is enough on its own; "not yet confirmed" contains
        # none, so the exception was dead logic guarding a hole.
        if not line or _is_answered(line):
            continue
        for m in _MARKERS:
            g = m.search(line)
            if g:
                out.append(Waiting(slug, n, g.group("text").strip(), "timeline"))
                break
    return out


def _from_open_sections(path: Path, slug: str) -> list[Waiting]:
    """Bullet items under a trail's legacy `## Open`.

    `## Open` was cut from the trail shape on 2026-09-08 -- it is lifecycle,
    not association. One trail written before the cut still carries the
    heading, empty. This reader stays until that file is migrated.
    """
    text = path.read_text(encoding="utf-8")
    i = text.find("\n## Open\n")
    if i < 0:
        return []
    j = text.find("\n## ", i + 4)
    body = text[i:j if j > 0 else None]
    start = text[:i].count("\n") + 1
    out = []
    for n, raw in enumerate(body.splitlines(), start):
        line = raw.strip()
        if line.startswith(("- ", "* ")) and "none" not in line.lower():
            out.append(Waiting(slug, n, line[2:].strip(), "open"))
    return out


def waiting() -> list[Waiting]:
    """Every unanswered proposal in the Library, newest Book first."""
    out: list[Waiting] = []
    for b in books(include_resolvers=True):
        # Resolvers carry TEMPLATES showing how to write a proposal, not
        # proposals. schema.md's example line matched and looked like a real
        # question waiting on the owner.
        if b.type == "resolver":
            continue
        try:
            out += _from_timeline(b.path, b.slug)
            out += _from_open_sections(b.path, b.slug)
        except OSError:
            continue
    return out


def render(limit: int = 5, full: bool = False) -> str:
    """The block that goes at the TOP of session start."""
    items = waiting()
    if not items:
        return ""
    head = f"## ⚠ {len(items)} waiting on your word"
    lines = [head, ""]
    if not full:
        lines.append("Nothing else in MEMEX stalls silently. These do.\n")
    for w in items[: None if full else limit]:
        body = " ".join(w.text.split()) if full else w.gist()
        lines.append(f"- **{w.slug}** — {body}")
    if not full and len(items) > limit:
        lines.append(f"- …and {len(items) - limit} more. `memex open` for all of them.")
    return "\n".join(lines)
