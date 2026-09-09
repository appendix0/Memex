"""Candidate facts, waiting on the owner — a queue, not a layer of the Library.

The owner, 2026-09-08: "there should be no observed being kept. It might be used as
temporary queue before being recorded ... Memex should be a base of fact, not a
knowledge queue stacking up from all the session."

So a Book contains agreed fact and nothing else. Anything an agent noticed but
The owner has not confirmed lives HERE, in `state/`, which is machine state: delete it
and the Library is unchanged. It is transient by construction.

The route in is cheap; the route out is a person:

    noticed  →  candidates.jsonl  →  the owner says yes  →  a fact in the Book
                                  →  the owner says no   →  gone

The route out is the Button: the owner is shown one exact sentence and one exact
destination, in the session, and says yes. An agent never writes to a Book on
its own, and never waits for a sweep at the end.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, asdict
from datetime import datetime

from .library import STATE, TZ

QUEUE = STATE / "candidates.jsonl"
STALE_DAYS = 14      # older than this and nobody was ever going to answer it
MAX_PER_SESSION = 3  # what one scribe run may add. The owner, 2026-09-08: the queue
                     # is a buffer, not a backlog -- 17 unanswered questions
                     # he never saw is the failure this number prevents.

# The ceiling on the WHOLE queue, which the per-run cap is not.
#
# A per-run cap only bounds the backlog while runs are rare. The Scribe used to
# run at session end, and the always-on session ends once a week. On a schedule
# it runs eight times a day, and 3-per-run silently becomes 24-per-day into a
# queue whose named failure was seventeen items the owner never saw. So the ceiling
# has to be on the queue itself, not on the run.
#
# Ten: under the seventeen that failed, and three runs of headroom above the
# per-run cap. Full means REFUSE, never displace -- a queue that quietly drops
# its oldest entry to make room is the rot this is here to stop, and a full
# queue is loud anyway: the Stop hook raises it at the end of every turn.
MAX_PENDING = 10


@dataclass
class Candidate:
    """One thing waiting on the owner. Two kinds, because two different acts.

    kind="fact" -- a claim to be written into a Book. The owner reads the sentence
                   and says whether it is true and belongs there. Ratification.
    kind="step" -- a tie between two Books, to be written as a step on a route.
                   The owner reads the turn and the reason and says whether that is
                   what the turn was. Also ratification, and only because the
                   reason is QUOTED from the record; trails.py refuses to invent
                   one, so a tie whose reason is not already written down is
                   never queued. Otherwise a Button becomes a writing task.

    The extra fields carry defaults so every row written before this parses
    unchanged -- Candidate(**json.loads(line)) simply fills them in.
    """
    id: str
    book: str
    text: str
    seen: str
    source: str = "scribe"
    kind: str = "fact"
    trail: str = ""      # step only: the route it joins
    via: str = ""        # step only: the Book already on that route
    date: str = ""       # step only: the date the quoted reason carries

    @property
    def age_days(self) -> int:
        try:
            return (datetime.now(TZ) - datetime.fromisoformat(self.seen)).days
        except ValueError:
            return 0


def _read() -> list[Candidate]:
    if not QUEUE.exists():
        return []
    out = []
    for line in QUEUE.read_text().splitlines():
        if not line.strip():
            continue
        try:
            out.append(Candidate(**json.loads(line)))
        except (json.JSONDecodeError, TypeError):
            continue
    return out


def _write(items: list[Candidate]) -> None:
    STATE.mkdir(exist_ok=True)
    QUEUE.write_text("".join(json.dumps(asdict(c), ensure_ascii=False) + "\n"
                             for c in items))


def room() -> int:
    """How many more the queue will take. Zero means every add() will refuse."""
    return max(0, MAX_PENDING - len(pending()))


def add(book: str, text: str, source: str = "scribe") -> Candidate | None:
    """Queue something noticed.

    Returns None if it restates one already queued, or if the queue is full.
    Callers that need to tell those apart check room() first.
    """
    text = " ".join(text.split())
    if room() <= 0:
        return None
    items = _read()
    bag = lambda t: {w for w in t.lower().split() if len(w) > 3}
    new = bag(text)
    for c in items:
        if c.book != book:
            continue
        old = bag(c.text)
        if old and len(new & old) / max(len(new | old), 1) >= 0.6:
            return None
    c = Candidate(uuid.uuid4().hex[:8], book, text,
                  datetime.now(TZ).isoformat(timespec="seconds"), source)
    items.append(c)
    _write(items)
    return c


def add_step(trail: str, book: str, via: str, date: str, why: str) -> Candidate | None:
    """Queue a tie for the Button. Deduped on (trail, book), not on wording.

    A step is identified by WHICH Book joins WHICH route -- two different
    reasons for the same join are the same proposal, so word-overlap dedupe
    would be the wrong test here.
    """
    if room() <= 0:
        return None
    items = _read()
    for c in items:
        if c.kind == "step" and c.trail == trail and c.book == book:
            return None
    c = Candidate(uuid.uuid4().hex[:8], book, " ".join(why.split()),
                  datetime.now(TZ).isoformat(timespec="seconds"),
                  source="daily", kind="step", trail=trail, via=via, date=date)
    items.append(c)
    _write(items)
    return c


def steps_first(items: list[Candidate]) -> list[Candidate]:
    """the owner asked for the trail Buttons first, everywhere they are shown.

    A trail is the thing Bush calls the important act; a fact is the thing we
    have plenty of. When both are waiting, the tie is the one to press.
    """
    return [c for c in items if c.kind == "step"] + \
           [c for c in items if c.kind != "step"]


def prune() -> int:
    """Drop what nobody was ever going to answer. Returns how many went.

    A prompt that repeats forever stops being read. Anything unanswered after
    STALE_DAYS is gone -- silently, because a notice about dropped notices is
    the same nag by another name. Nothing is lost that was ever a fact: the
    Library is unchanged either way.
    """
    items = _read()
    keep = [c for c in items if c.age_days < STALE_DAYS]
    if len(keep) != len(items):
        _write(keep)
    return len(items) - len(keep)


def pending(include_stale: bool = False) -> list[Candidate]:
    items = _read()
    return items if include_stale else [c for c in items if c.age_days < STALE_DAYS]


def take(cid: str) -> Candidate | None:
    """Remove and return one, by id or unique prefix."""
    items = _read()
    hit = [c for c in items if c.id == cid or c.id.startswith(cid)]
    if len(hit) != 1:
        return None
    _write([c for c in items if c.id != hit[0].id])
    return hit[0]


def accept(cid: str) -> str | None:
    """the owner said yes. Where it lands depends on which act he agreed to.

    A fact becomes an agreed claim in its Book. A step becomes a numbered step
    on a route in `trails/`, never inside a Book -- a route that lives in one
    Book cannot pass through another, so it would not be a route.
    """
    from .edits import apply_op
    c = take(cid)
    if c is None:
        return None
    if c.kind == "step":
        from .trails import append_step
        body = append_step(c.trail, c.book, c.text, c.text,
                           c.date or datetime.now(TZ).strftime("%Y-%m-%d"))
        apply_op({"op": "trail_file", "book": c.trail, "body": body})
        return c.trail
    apply_op({"op": "fact", "book": c.book, "text": c.text,
              "provenance": "agreed"})
    return c.book


def render(limit: int = 8) -> str:
    """Two kinds, shown as two different things, ties first.

    A tie is rendered with the arrow because that is what it IS -- one Book
    joining a route. A fact is rendered as a sentence and a destination. The owner
    should be able to tell which act he is being asked for without reading the
    words, so the shapes differ, not just the labels.
    """
    items = steps_first(pending())
    if not items:
        return ""
    n_step = sum(1 for c in items if c.kind == "step")
    head = f"## {len(items)} waiting on you"
    if n_step:
        head += f" — {n_step} tie(s) first"
    lines = [head, "",
             "Noticed but not yet agreed. Nothing enters the Library until you say so.", ""]
    for c in items[:limit]:
        stale = "  (stale)" if c.age_days >= STALE_DAYS else ""
        if c.kind == "step":
            lines.append(f"- `{c.id}` TIE  **{c.book}** → **{c.trail}**{stale}")
            lines.append(f"       because “{c.text[:150]}”")
        else:
            lines.append(f"- `{c.id}` FACT **{c.book}**{stale} — {c.text[:150]}")
    if len(items) > limit:
        lines.append(f"- …and {len(items) - limit} more. `memex pending`.")
    return "\n".join(lines)
