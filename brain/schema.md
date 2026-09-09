---
title: "schema — the Book contract"
type: resolver
created: 2026-09-09
---

# The Book contract

**Most of this contract is not enforced.** There is no linter and no validator.
The contract below is still the contract — every Book follows it and `memex`
parses on the assumption — but it holds because whoever writes a Book follows
it. The section "What a machine actually checks" is the honest boundary.

Vocabulary: [[concepts/memex-glossary]]. A **Book** is one markdown file. The
`type:` values below are a closed set: `memex/edits.py` refuses any other value
when it creates a Book, and that is the one piece of this file a machine checks.

## Required frontmatter, every Book, no exceptions

```yaml
---
title: "Human-readable name"     # required
type: person|project|research|concept|writing|infra|source|resolver|note
created: 2026-09-09              # required, real date, never YYYY-MM-DD
about: [greenhouse, memex]       # topic facet, controlled list
status: active                   # active | archived | inbox — omit when active
visibility: vault                # vault or absent — the only privacy mechanism
kind: paper                      # sources/ only: paper | reference
domain: [I.2.6]                  # ACM CCS 2012 — sources/, research/, writing/
# NO slug field. The slug IS the path: brain/people/owner.md -> people/owner.
# A hand-written slug can only disagree with the path, never improve on it.
---
```

**`type:` is the shelf.** Not a description of the Book that happens to sit near
its directory — the two are the same fact, and a Book whose type changes is a
Book that moves. The keys below `created:` are the **facets**: the descriptors
that carry everything a directory name used to. Which ones a Book needs, and the
controlled values each accepts, are in [[CLASSIFICATION]].

A Book missing `title`, `type` or `created` still parses, but loses its title in
`memex recall` and sorts as untyped. A `created:` of `YYYY-MM-DD` is the one
failure worth naming twice: it is a placeholder someone forgot, and it reads as
a real date forever after.

## What a machine actually checks

Only what `memex/edits.py` enforces:

- `type:` must be one of the nine values above.
- `about:` terms must appear in [[CLASSIFICATION]]'s controlled list.
- A Book about a person cannot be created without `visibility: vault`.
- A whole-file write is refused anywhere but `trails/`.
- A path that escapes `brain/` is refused.
- An edit that would make a Book shorter is refused unless it quotes the removed
  text verbatim.

Everything else in this file is followed, not enforced. Say so plainly rather
than implying a gate exists.

## Book body — two layers, split by `---`

**Above the line: compiled truth.** Always current, rewritten when new
information arrives.

- One-paragraph summary. Read only this and you know the state of play.
- `## State` — structured fields, the things you would query.
- `## Open Threads` — active items. Removed when resolved (they move below).
- `## Rules` — where a project or person carries standing directives.
- `## See Also` — wiki-links in double brackets. These build the relationship graph.

**Below the line: the appendix.** Append-only, never rewritten. Two sections,
and the difference between them is the whole point:

- `## Trail` — **why it went this way.** One entry per agreed step: the date, the
  reasoning, and the Books it reached. Bush's trail, living in the Book it
  belongs to. A step says *why a turn was taken*, never *what changed* — if it
  could be written from a diff or a commit message, it is not a step.
- `## Timeline` — **what happened.** Events, dates, commits, quotes. Reverse
  chronological. When an open thread resolves it moves here with its resolution.

The owner's instruction that fixed this shape: *"trails should exist as an
appendix, just like timemark and commits in the books, below the ---- line."*

## Clear points, not prose

> *"The books should have clear points and clear trails that can be tracked."*

Above the line, a fact is **one standing statement that is independently true
and independently checkable.** Not a paragraph carrying four claims.

> Not: "The rig works well and raised germination a lot while keeping water use
> about the same, which answers the objection that it is just a timer."
>
> But:
> - Germination rose 29.4% → 67.3% with the controller on.
> - Water use did not rise with it: 74.5 L → 71.2 L per week.
> - Those two together answer the objection that it is just a timer.

This is not style. It is mechanical. A fact is superseded by `--replaces`, which
matches text **exactly** — so a claim buried inside a paragraph cannot be
corrected without rewriting three claims that were fine. Points make the
overwrite surgical, and surgical overwrite is the only reason the curated layer
can stay current without losing anything.

A Book's opening paragraph stays prose: it is the one-breath answer to "what is
this". Everything after it is points.

## Three kinds of record

Bush keeps the **store** and the **trail** apart, and so do we. §2: the record
"must be continuously extended." §6: the user should be **"profligate"** about
what enters it. §7: tying two items together is the deliberate act, the button.

| Kind | Where it lives | Who may write it | May it overwrite? |
|---|---|---|---|
| **candidate** | `state/candidates.jsonl` — OUTSIDE the Library | anyone | it is not in a Book at all |
| **agreed** | a Book's facts | **the owner's word, in a live session**, via `memex-input`. The Scribe is refused in code. | **yes** |
| **a step** | `## Route` in a trail, or a Book's `## Trail` | owner and agent converged | no — append-only (§7.6) |

**A candidate is the default.** A checkable statement about the world needs
nobody's assent. "The README links to a directory deleted in commit a1b2c3d" is
a fact, not a proposal, and filing it as a question is how a queue of them goes
unread.

**Promotion is the Button.** A candidate the owner confirms graduates into the
facts and becomes agreed. That is the only route from the store into the curated
layer, and the only way anything auto-captured can ever overwrite anything:
*"append only for observed, overwrite only for agreed."*

Measured, on one real transcript during development: the old single-bar prompt
produced 0 records and 5 questions; the three-kind prompt produced 10
observations and 0 questions.

## The Book is the facts; the trail is the appendix

> "The process of tying two items together is the important thing."
> — Bush, §7

## See Also

[[RESOLVER]] · [[CLASSIFICATION]] · [[concepts/links-and-trails]]
