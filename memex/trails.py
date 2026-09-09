"""Trails: the association and logical relationship between Books.

    "The process of tying two items together is the important thing ...
     any item can be joined into numerous trails."
                                    — Bush, As We May Think, §7

A trail records how knowledge connects and why, so it can be handed to another
agent, or to the same agent later, as a clue. The owner, 2026-09-08: "This is all we
need. Nothing else."

What a trail carries, and nothing more:

    a name          so a reader knows what route this is
    ordered steps   the logical flow -- each step names what the one before forced
    → [[links]]     the association: which Books the step ties
    a date          the timemark

Status, Question, Learned and Open were all cut on 2026-09-08. They are
lifecycle and conclusions, not associations, and a trail that demands them is
a trail nobody writes. Add back only what proves necessary.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .library import BRAIN, books

# "3. **The order is the priority.** — 2026-06"   (a trailing "· mark" is tolerated
# so trails written under the older shape still parse)
_STEP = re.compile(
    r"^\s*(?P<n>\d+)\.\s+\*\*(?P<move>.+?)\*\*\s*(?:—|--)\s*"
    r"(?P<date>[\d-]+)\s*(?:·.*)?$")
_LINK = re.compile(r"\[\[([^\]|]+?)(?:\|[^\]]*)?\]\]")


@dataclass
class Step:
    n: int
    move: str
    date: str
    why: str = ""
    reaches: list[str] = field(default_factory=list)


@dataclass
class Trail:
    slug: str
    title: str
    steps: list[Step]

    @property
    def books(self) -> list[str]:
        seen: list[str] = []
        for s in self.steps:
            for b in s.reaches:
                if b not in seen:
                    seen.append(b)
        return seen


def _route(text: str) -> str:
    m = re.search(r"^## Route\s*$", text, re.M)
    if not m:
        return ""
    j = re.search(r"^## ", text[m.end():], re.M)
    return text[m.end(): m.end() + j.start()] if j else text[m.end():]


def parse(path: Path) -> Trail | None:
    text = path.read_text(encoding="utf-8")
    slug = path.relative_to(BRAIN).with_suffix("").as_posix()
    title = ""
    t = re.search(r'^title:\s*"?(.+?)"?\s*$', text, re.M)
    if t:
        title = t.group(1)
    steps: list[Step] = []
    cur: Step | None = None
    for line in _route(text).splitlines():
        m = _STEP.match(line)
        if m:
            cur = Step(int(m["n"]), m["move"].strip(), m["date"])
            steps.append(cur)
            continue
        if cur is None:
            continue
        cur.reaches += [b for b in _LINK.findall(line) if b not in cur.reaches]
        s = line.strip()
        if s and not s.startswith("→"):
            cur.why = (cur.why + " " + s).strip()
    return Trail(slug, title or slug, steps)


def all_trails() -> list[Trail]:
    d = BRAIN / "trails"
    out: list[Trail] = []
    if not d.is_dir():
        return out
    for f in sorted(d.glob("*.md")):
        if f.stem == "README":
            continue
        t = parse(f)
        if t and t.steps:
            out.append(t)
    return out


def through(book: str) -> list[tuple[Trail, Step]]:
    """Every trail that reaches this Book, and where. Bush §7: numerous trails."""
    return [(t, s) for t in all_trails() for s in t.steps if book in s.reaches]


def walk(trail: Trail, width: int = 78) -> str:
    out = [f"{trail.slug} — {trail.title}", ""]
    for i, s in enumerate(trail.steps):
        out.append(f"  {s.n}. {s.move}   — {s.date}")
        if s.why:
            why = s.why if len(s.why) <= width else s.why[: width - 1] + "…"
            out.append(f"     {why}")
        if s.reaches:
            out.append("     → " + " → ".join(s.reaches))
        if i < len(trail.steps) - 1:
            out.append("     │")
    return "\n".join(out)


def unexplained() -> list[tuple[str, str]]:
    """Ties no trail has given a reason for — the real trail backlog.

    A link says "these belong together". A trail says "and here is what that
    forced". A tie counts as explained once both Books sit on the same route,
    because being on one route means the relationship has been reasoned about.

    This is the association half of the observed/agreed split: a link is cheap
    capture, a trail step is the deliberate version. 105 of 206 ties had no
    reason anywhere when this was first measured.
    """
    explained = set()
    for t in all_trails():
        bs = t.books
        for a in bs:
            for b in bs:
                if a != b:
                    explained.add((a, b))
    out = []
    for b in books():
        # A trail's own links ARE the explanation. Counting them as unexplained
        # made the trails themselves the top of the backlog and pushed the total
        # above the number of links in the Library.
        if b.slug.startswith("trails/"):
            continue
        for tgt in _LINK.findall(b.body):
            if tgt == b.slug:
                continue
            if (b.slug, tgt) in explained or (tgt, b.slug) in explained:
                continue
            if (b.slug, tgt) not in out:
                out.append((b.slug, tgt))
    return out


def orphans() -> list[str]:
    """Books no trail reaches: present in the Library, on nobody's route."""
    reached = {b for t in all_trails() for b in t.books}
    return sorted(b.slug for b in books() if b.slug not in reached)


# ── Recovering a route from Books that already exist ────────────────────────
# The walk already happened and left evidence: links, and dated entries saying
# when each Book entered the record. What cannot be recovered is the ORDER,
# because the order is logical, not chronological -- that judgement is a
# person's. A reason is never invented; where the record holds none, the gap is
# reported so the step can be dropped.

_DATED = re.compile(r"^(\d{4}-\d{2}(?:-\d{2})?)\s*[—-]", re.M)


def _earliest_entry(b) -> tuple[str, str]:
    best_date, best_line = "9999", ""
    for m in _DATED.finditer(b.body):
        if m.group(1) >= best_date:
            continue
        end = b.body.find("\n\n", m.start())
        line = b.body[m.start(): end if end > 0 else len(b.body)]
        best_date, best_line = m.group(1), " ".join(line.split())[:200]
    return best_date, best_line


def _graph() -> dict[str, set[str]]:
    bs = books()
    slugs = {b.slug for b in bs}
    g: dict[str, set[str]] = {b.slug: set() for b in bs}
    for b in bs:
        for t in _LINK.findall(b.body):
            if t in slugs and t != b.slug:
                g[b.slug].add(t); g[t].add(b.slug)
    return g


def suggest(seed: str, depth: int = 1, limit: int = 12) -> list[dict]:
    from .library import get
    g = _graph()
    if seed not in g:
        return []
    seen, frontier = {seed}, {seed}
    for _ in range(depth):
        nxt = {n for s in frontier for n in g[s]} - seen
        seen |= nxt
        frontier = nxt
    rows = []
    for slug in seen:
        b = get(slug)
        if not b:
            continue
        when, reason = _earliest_entry(b)
        rows.append({"book": slug, "date": when, "reason": reason,
                     "links": sorted(g[slug] & seen)})
    rows.sort(key=lambda r: (r["date"], r["book"]))
    return rows[:limit]


def render_suggestion(seed: str, rows: list[dict]) -> str:
    out = [f"Raw material for a trail rooted at {seed} — {len(rows)} Books.",
           "Listed by date, which is NOT the order of the trail: a route is the",
           "logical flow, and that ordering is yours.", ""]
    for i, r in enumerate(rows, 1):
        out.append(f"  {i}. {r['book']}   — {r['date'] if r['date'] != '9999' else 'undated'}")
        out.append(f"     {r['reason'] or '*** no reason in the record — do not invent one'}")
        if r["links"]:
            out.append("     → " + " → ".join(r["links"][:4]))
        out.append("")
    return "\n".join(out)


# ── What the daily pass proposes ────────────────────────────────────────────
# The owner, 2026-09-09: "Every 24h the system looks for the whole memex and checks if
# any other change is made. If the agent founds something that could be recorded
# on the trail, it put it on the queue."
#
# This reads the LIBRARY, never a transcript, and calls no model -- it is file
# reads, so a daily pass costs nothing. That is the §4 division: scanning for
# the shape is mechanical, deciding what the tie MEANS is the owner's.
#
# The hard rule is the one already stated above and in
# concepts/links-and-trails: a step's reason is never invented. So a tie is only
# proposed when the joining Book already carries a dated entry that can be
# QUOTED as the reason. Where the record holds none, the tie is left in the
# backlog rather than turned into a writing assignment for the owner.

# A key, a token, an OCID, a UUID, an IP. The rule is old -- scribe/PROMPT.md:
# "Never write an identifier ... Drop it" -- but it had never been enforced in
# code, and the first version of the daily scan proposed a step whose quoted
# reason carried a Mojang UUID. A proposal is a route INTO a Book, so the guard
# belongs here, before the Button, not after it.
_META = re.compile(r"^[A-Za-z][A-Za-z /-]{0,24}:\s")   # "phase: ...", "in-game name: ..."
_IDENT = re.compile(r"\b(?:[0-9a-f]{16,}|ocid1\.[a-z0-9.]+|(?:\d{1,3}\.){3}\d{1,3})\b", re.I)


def _tie_sentence(src, target: str) -> tuple[str, str]:
    """The prose in `src` that ties it to `target` — the reason, already written.

    WHERE THE REASON LIVES. concepts/links-and-trails measured it: 164 links sit
    inline in prose and carry the context of the sentence around them; 119 sit
    under `## See Also` and carry relatedness and nothing else. So the sentence
    holding the link IS the record's explanation of the tie, and a `## See Also`
    entry is not an explanation at all.

    The first version of this quoted the Book's EARLIEST dated entry instead --
    which is when the Book entered the record, not why this tie exists. It
    produced "canonical-terminology joins building-memex because 'frozen
    documents are renamed'". Quoting an unrelated line as evidence is worse than
    inventing one: it is a misattribution wearing a citation. Dropped.

    Returns ("", "") when the record holds no reason, and the tie is then left
    in the backlog rather than made into a writing assignment.
    """
    body = src.body
    cut = re.search(r"^## See Also\s*$", body, re.M)   # links only, no reason
    if cut:
        body = body[:cut.start()]
    m = re.search(r"\[\[" + re.escape(target) + r"(?:\|[^\]]*)?\]\]", body)
    if not m:
        return "", ""
    # the paragraph around it: what a reader would quote
    a = body.rfind("\n\n", 0, m.start())
    b = body.find("\n\n", m.end())
    para = body[(a + 2 if a >= 0 else 0): b if b > 0 else len(body)]
    para = " ".join(para.split())
    if para.startswith(("#", "|", "-", "*", ">")) or len(para) < 40:
        return "", ""                       # a heading, a table row, a list item
    # It has to READ as reasoning, not as metadata. Without this the scan offered
    # a Book's identity block -- gamertag, purchase date and a Mojang UUID -- as
    # the reason for a tie, and a `phase:` line as another. Two cheap shape
    # tests do it: a `key: value` opening is metadata, and a paragraph that does
    # not end in terminal punctuation is a fragment, not a claim.
    #
    # Measured 2026-09-09 over the whole Library: 103 unexplained ties, 51 with
    # one end already on a route, 27 whose link sits inline in prose, 3 that
    # survive here. That ratio is the point, not a defect -- links-and-trails
    # records that 68% of ties have no reason anywhere, and a tie whose reason
    # was never written down must stay in the backlog rather than become a
    # writing assignment wearing a Button.
    if _META.match(para) or not para.rstrip().endswith((".", "?", "!")):
        return "", ""
    # And never carry an identifier out of a Book, whatever it is attached to.
    if _IDENT.search(para):
        return "", ""
    d = re.match(r"\**(\d{4}-\d{2}(?:-\d{2})?)\**\s*[—-]", para)
    return (d.group(1) if d else ""), para[:400]


def propose_steps(limit: int = 5) -> list[dict]:
    """Ties a route could explain, where the reason is already in the record.

    One end already sits on a trail and the other does not: that is a route
    reaching a Book it never reasoned about. The reason is quoted from the
    prose holding the link, never composed.
    """
    on_trail: dict[str, list[str]] = {}
    for tr in all_trails():
        for b in tr.books:
            on_trail.setdefault(b, []).append(tr.slug)
    by_slug = {b.slug: b for b in books()}

    out: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for src, tgt in unexplained():          # src is the Book holding the link
        if src.startswith("trails/") or tgt.startswith("trails/"):
            continue
        for near, far in ((src, tgt), (tgt, src)):
            if near not in on_trail or far in on_trail:
                continue
            holder = by_slug.get(src)
            if holder is None or by_slug.get(far) is None:
                continue
            date, why = _tie_sentence(holder, tgt)
            if not why:                     # the record holds no reason
                continue
            trail = on_trail[near][0]
            if (trail, far) in seen:
                continue
            seen.add((trail, far))
            out.append({"trail": trail, "book": far, "via": near,
                        "date": date or _earliest_entry(by_slug[far])[0],
                        "why": why})
    return out[:limit]


def _split_quote(text: str) -> tuple[str, str]:
    """A quoted reason into the step's two halves: the move, then the reason.

    Every step in the Library reads `**a short move.** — DATE` and then the
    reasoning underneath. Handing the whole quotation to both halves produced

        6. **2026-07-13 — Superseded by the v1 publish pivot: ... .** — 2026-07-13

    -- the date printed twice and a whole paragraph in bold. So: drop the
    leading date, which the step already carries in its own field, and let the
    first sentence be the move with the rest as the reason. Nothing is composed;
    the words are the record's.
    """
    s = " ".join(text.split())
    s = re.sub(r"^\**\d{4}-\d{2}(?:-\d{2})?\**\s*[—-]\s*", "", s)
    m = re.search(r"(?<=[.!?])\s+(?=[A-Z“\"\[])", s)
    return (s[:m.start()], s[m.end():]) if m else (s, "")


def append_step(trail_slug: str, book: str, move: str, why: str,
                date: str) -> str:
    """The whole trail file with one step appended to its Route. Never writes.

    Append-only, and numbered from what is already there. Order is logical, not
    chronological -- a recovered step goes on the END because the machine has no
    standing to insert one into the middle of somebody's reasoning.
    """
    path = BRAIN / f"{trail_slug}.md"
    if not path.exists():
        raise ValueError(f"no such trail: {trail_slug}")
    body = path.read_text(encoding="utf-8")
    tr = parse(path)
    n = (max((s.n for s in tr.steps), default=0) + 1) if tr else 1

    move, why = _split_quote(move) if move == why else \
                (" ".join(move.split()), " ".join(why.split()))
    # The arrow below already says where the step reaches. A trailing "See
    # [[that same Book]]." is the record repeating itself, and a step is
    # append-only -- a wrong one is answered by a later step, never rewritten --
    # so it is worth not writing twice in the first place.
    why = re.sub(r"\s*\bSee \[\[" + re.escape(book) + r"(?:\|[^\]]*)?\]\]\.?$",
                 "", why, flags=re.I).strip()
    lines = [f"{n}. **{move}** — {date}"]
    if why and why != move:
        lines.append(f"   {why}")
    lines.append(f"   → [[{book}]]")
    step = "\n".join(lines)

    m = re.search(r"^## Route\s*$", body, re.M)
    if not m:
        raise ValueError(f"{trail_slug} has no ## Route")
    j = re.search(r"^## ", body[m.end():], re.M)
    end = m.end() + j.start() if j else len(body)
    head, tail = body[:end].rstrip("\n"), body[end:]
    return f"{head}\n\n{step}\n" + (f"\n{tail}" if tail else "")


# ── The other direction ─────────────────────────────────────────────────────
# A route links to its Books; without the reverse a reader in a Book cannot see
# which routes cross it, and Bush's "numerous trails" is unreachable from the
# item. This section is DERIVED, so rewriting it is safe.

BACKREF_HEADING = "Trails through this Book"
_LEGACY_HEADING = "Trail"
_BACKREF_NOTE = ("Routes through this Book. The steps live in the trail, not "
                 "here — a step has one home.")


def backrefs(book: str) -> str:
    hits = through(book)
    if not hits:
        return ""
    lines = [f"## {BACKREF_HEADING}", "", _BACKREF_NOTE, ""]
    for t, st in sorted(hits, key=lambda h: (h[0].slug, h[1].n)):
        lines.append(f"- [[{t.slug}]] step {st.n} — {st.move}")
    return "\n".join(lines) + "\n"


def sync_backrefs(dry: bool = False) -> tuple[list[str], list[str]]:
    """Rewrite every reached Book's back-reference section.

    A Book carrying such a section that NO trail reaches has it removed only if
    it is ours (it carries the generated note). Anything else is prose and is
    reported, never emptied.
    """
    from .edits import join_book, split_book
    written, skipped = [], []
    for b in books():
        text = b.path.read_text(encoding="utf-8")
        fm, above, below = split_book(text)
        want = backrefs(b.slug)
        has = re.search(rf"^## {re.escape(BACKREF_HEADING)}\s*$", below, re.M)
        if not has and _BACKREF_NOTE in below:
            has = re.search(rf"^## {_LEGACY_HEADING}\s*$", below, re.M)
        if not want:
            if not has:
                continue
            j = re.search(r"^## ", below[has.end():], re.M)
            end = has.end() + j.start() if j else len(below)
            if _BACKREF_NOTE not in below[has.start():end]:
                skipped.append(b.slug)
                continue
            new_below = below[: has.start()].rstrip("\n") + "\n\n" + below[end:].lstrip("\n")
        elif has:
            j = re.search(r"^## ", below[has.end():], re.M)
            end = has.end() + j.start() if j else len(below)
            new_below = below[: has.start()] + want + "\n" + below[end:]
        else:
            new_below = below.rstrip("\n") + "\n\n" + want
        out = join_book(fm, above, new_below)
        if out != text:
            if not dry:
                b.path.write_text(out, encoding="utf-8")
            written.append(b.slug)
    return written, skipped
