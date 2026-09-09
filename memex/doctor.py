"""One command that checks the whole structure.

Every check here exists because the thing it looks for actually went wrong:
a stale index that made a Book unfindable, a broken link left by a rename, a
candidate queue nobody looked at for a day, an op the prompt offered that the
code refused. None of it is hypothetical.
"""
from __future__ import annotations

import re
import subprocess
import sys

from .library import BRAIN, ROOT, books, shelves


def _check(name: str, ok: bool, detail: str = "") -> tuple[str, bool]:
    mark = "ok  " if ok else "BAD "
    return (f"  {mark} {name}" + (f"  — {detail}" if detail else ""), ok)


def report(brief: bool = False) -> tuple[str, bool]:
    lines, bad = [], False
    bs = books()
    slugs = {b.slug for b in books(include_resolvers=True)}

    # 1. broken links — a rename leaves these behind and nothing else notices.
    # EVERY markdown file, not only the ones that parse as Books: the first
    # version walked books() and so could not see the two dead links sitting
    # in RESOLVER.md and trails/README.md, which are the files a lost agent
    # reads first.
    broken = []
    for p in sorted(BRAIN.rglob("*.md")):
        rel = p.relative_to(BRAIN).with_suffix("").as_posix()
        body = p.read_text(encoding="utf-8", errors="replace")
        # A link inside a fence is an EXAMPLE of the syntax -- schema.md
        # shows the shape of a trail step -- and reporting it as broken
        # trains the reader to ignore this check.
        body = re.sub(r"^```.*?^```", "", body, flags=re.S | re.M)
        for t in re.findall(r"\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]", body):
            if t not in slugs:
                broken.append((rel, t))
    l, ok = _check("links all resolve", not broken,
                   f"{len(broken)} broken: {broken[:3]}" if broken else "")
    lines.append(l); bad |= not ok

    # 2. frontmatter — a Book without it is invisible to everything
    from .library import read_book
    unreadable = [str(p.relative_to(BRAIN)) for p in BRAIN.rglob("*.md")
                  if read_book(p) is None]
    l, ok = _check("every Book parses", not unreadable, ", ".join(unreadable[:3]))
    lines.append(l); bad |= not ok

    # 3. the index — a Book written and not reindexed cannot be found
    from .recall import INDEX, INDEX_VERSION, _load
    idx = _load()
    stale = [b.slug for b in bs if b.slug not in idx]
    l, ok = _check("search index current",
                   idx.get("__version__") == INDEX_VERSION and not stale,
                   f"{len(stale)} unindexed; run `memex reindex`" if stale else
                   ("index format is old; run `memex reindex`"
                    if idx.get("__version__") != INDEX_VERSION else ""))
    lines.append(l); bad |= not ok

    # 4. nothing unagreed sitting in a Book
    layered = [b.slug for b in bs if "## Observed" in b.body]
    l, ok = _check("Books hold fact only", not layered, ", ".join(layered[:3]))
    lines.append(l); bad |= not ok

    # 5. the prompt must offer only ops something handles
    prompt = set(re.findall(r'\{"op":"(\w+)"',
                            (ROOT / "scribe" / "PROMPT.md").read_text()))
    handled = set(re.findall(r'kind (?:==|in \()\s*[("]([a-z_]+)',
                             (ROOT / "memex" / "edits.py").read_text()))
    handled |= {"trail", "timeline", "observe"}
    orphan = sorted(prompt - handled)
    l, ok = _check("prompt offers only ops we accept", not orphan, ", ".join(orphan))
    lines.append(l); bad |= not ok

    if brief:
        return "\n".join(lines), bad

    # ── informational: not failures, but the shape of the Library ──
    from .candidates import pending
    from .pending import waiting
    from .trails import all_trails, orphans, unexplained
    ts = all_trails()
    q, w = pending(), waiting()
    lines += ["", "  " + "-" * 52, f"  {len(bs)} Books on {len(shelves())} shelves, "
              f"{sum(1 for b in bs if b.vault)} vault",
              f"  {len(ts)} trails; {len(orphans())} Books on no route",
              f"  {len(unexplained())} ties no trail explains",
              f"  {len(q)} candidates waiting on the owner"
              + ("  ← ask him" if q else ""),
              f"  {len(w)} unanswered proposals" + ("  ← `memex open`" if w else "")]
    return "\n".join(lines), bad
