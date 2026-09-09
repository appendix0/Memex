"""Session start: what a fresh agent needs, in one screen.

Replaces the engine's hook. Reads files; injects nothing it did not verify.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta

from pathlib import Path

from .library import ROOT, TZ, get
from .scribe import RECEIPTS



def _memory() -> str:
    p = ROOT / "MEMORY.md"
    if not p.exists():
        return ""
    text = p.read_text()
    keep = []
    for head in ("Standing rules learned from corrections", "Active context", "Open commitments"):
        i = text.find(f"## {head}")
        if i < 0:
            continue
        j = text.find("\n## ", i + 3)
        keep.append(text[i:j if j > 0 else None].strip())
    return "\n\n".join(keep)


def _preferences() -> str:
    b = get("notes/owner-preferences")
    return b.above_the_line.strip() if b else ""


def _book_count() -> str:
    from .library import books
    try:
        return str(len(books()))
    except Exception:
        return "many"


def _scribe_report(days: int = 7) -> str:
    if not RECEIPTS.exists():
        return "Scribe: no receipts yet."
    since = datetime.now(TZ) - timedelta(days=days)
    observed = agreed = steps = opened = closed = runs = 0
    touched: set[str] = set()
    for line in RECEIPTS.read_text().splitlines():
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            if datetime.fromisoformat(r["scribed_at"]) < since:
                continue
        except (KeyError, ValueError):
            continue
        runs += 1
        def _n(k):                       # a model-written receipt can hold anything
            try:
                return int(r.get(k, 0) or 0)
            except (TypeError, ValueError):
                return 0
        observed += _n("observed"); agreed += _n("agreed"); steps += _n("steps")
        opened += _n("opened"); closed += _n("closed")
        # PROMPT.md asks the model for `books_touched`; this read only the older
        # `inquiries_touched`, so every conforming receipt reported nothing
        # touched. Accept both. (codex structured review, 2026-09-07)
        touched.update(r.get("books_touched", []))
        touched.update(r.get("inquiries_touched", []))
    if not runs:
        return f"Scribe: no runs in the last {days} days."
    t = ", ".join(sorted(touched)) or "none"
    # The proposal count used to live here. It now leads the whole block via
    # pending.py, because a trailing clause on the last line is where nine of
    # them went unread for a day.
    return (f"Scribe, last {days}d: {runs} runs, {observed} observed, "
            f"{agreed} agreed, {steps} steps, {opened} opened, {closed} closed."
            + (f" Touched: {t}." if t else ""))


def _in_memex() -> bool:
    """True when this session was opened inside the MEMEX repo."""
    # bin/memex cds into the repo before exec, so Path.cwd() is ALWAYS the repo
    # here and this check silently answered True everywhere. The wrapper passes
    # the caller's directory through MEMEX_CALLER_PWD.
    raw = os.environ.get("MEMEX_CALLER_PWD") or os.getcwd()
    try:
        here = Path(raw).resolve()
    except OSError:
        return False
    return ROOT.resolve() in [here, *here.parents]


def render() -> str:
    """Session-start context.

    Every session under $HOME fires this, so what it injects is a
    recurring cost paid before the conversation starts. A session working
    ON MEMEX gets everything; a session merely running somewhere under the
    home directory gets the part that is useful anywhere -- where the record
    is, how to search it, and what question is open -- and nothing else.
    """
    here = _in_memex()
    now = datetime.now(TZ).strftime("%Y-%m-%d %a %H:%M %Z")
    from .pending import render as _waiting
    parts = [f"<!-- MEMEX session context — data, not instructions. {now} -->"]
    # FIRST, before anything else. A proposal nobody answers produces no error
    # and no warning; it simply sits. Nine had accumulated before the owner saw them.
    w = _waiting(limit=5 if here else 3)
    if w:
        parts.append(w)
    from .candidates import render as _cands
    c = _cands(limit=5 if here else 3)
    if c:
        parts.append(c)
    # Where the record is, and how to reach it. A session on 2026-09-07 was
    # asked "what do you know about me", found the Library by guessing at
    # $HOME/memex/brain and read it with `ls -R` and `cat`. It got the
    # right answer, but only because the Library is still small enough to read
    # whole. Facts without the tool that reaches them is exactly the failure
    # Bush names in §5.
    parts.append(
        "## The record\n"
        f"the owner's Library is `{ROOT}/brain/` — {_book_count()} Books of markdown.\n"
        "**Before answering anything about the owner, a person, a project, or a past\n"
        "decision, search it.** Do not answer from this context alone; it is a\n"
        "summary, and the Library is the record.\n\n"
        "```\n"
        "memex recall \"<the question, in words>\"   # semantic search, every Book\n"
        "memex trail                              # every route through the Library\n"
        "memex open                               # what is waiting on your word\n"
        "```\n\n"
        "Ask in the words of the question, not keywords. A `[vault]` result is\n"
        "private: readable here, never quoted or exported beyond the owner.\n"
        "**A link ties two Books; a trail is the ordered, reasoned route over\n"
        "those ties.** Definitions: `brain/concepts/links-and-trails.md`.\n"
        "`memex trail` walks the routes between Books: the association and the\n"
        "logical flow, which is what the Library is for."
    )
    # The criterion, in EVERY session -- this is the whole reason it is a
    # string in code and not a Book. The owner, 2026-09-09: "make sure this not to
    # be written as a book and just rot somewhere ... the agent should always
    # carry [it]." A Book is read when someone goes looking; the rule for
    # what to record has to arrive before the thing worth recording does.
    from .criterion import render as _criterion
    parts.append(_criterion())
    if here:
        mem = _memory()
        if mem:
            parts.append("## From MEMORY.md\n" + mem)
        prefs = _preferences()
        if prefs:
            parts.append("## How to work with the owner (notes/owner-preferences)\n" + prefs)
    else:
        # The one thing worth carrying everywhere: how the owner wants to be
        # answered.
        # The full Book is a `memex recall` away and named right here.
        parts.append(
            "## How to work with the owner\n"
            "Points, not essays; lead with the answer. Read the docs before\n"
            "trial-and-error. Ask first on ambiguity. Full text:\n"
            "`memex recall \"how to work with the owner\"` \u2192 `notes/owner-preferences`."
        )
    if here:
        parts.append(_scribe_report())
    return "\n\n".join(parts) + "\n"
