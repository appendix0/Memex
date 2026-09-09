---
title: "trails/ — the shelf"
type: resolver
created: 2026-09-09
---

# trails

> "The process of tying two items together is the important thing …
>  any item can be joined into numerous trails."
> — Bush, §7

A **trail** is a named route through the Library: an ordered path over links
that already exist, with a reason at each turn. It answers *"what path through
knowledge is useful?"* — Bush's fourth operation, the one that separates a memex
from a large private archive.

## The ladder

```
link            →   trail
a tie               an ordered, reasoned route over those ties
made freely         open   = still being walked (this is the "inquiry")
                    closed = the Learned line says where it arrived
```

Two rungs, not three. Bush names links and trails; §8's *"trails can become
shared knowledge artifacts"* makes sharing a property of every trail, not a tier
above it. An open trail **is** the inquiry, so the two need no separate
machinery.

## What a trail is not

- **Not a link.** A link ties two items. A trail is the route through many.
- **Not a question.** A trail need carry no Question and no Learned line.
  Demanding one of every route is why, for a long time, there was only ever one.
- **Not a log.** Every step says *why the turn was taken*. If a step could be
  written from a diff or a commit message, it is not a step.

## Rules

- A step's reason is **never invented**. Recovered trails take their reasons from
  the dated entries already in the Books; where the record holds none, the step
  is **dropped, not guessed**. `memex/trails.py` enforces this by quoting the
  prose that holds the link, and proposing nothing when there is none.
- Steps are append-only. A wrong step is answered by a later one.
- A Book does not hold a copy of any route. It is *reached* by them, and
  `memex trail --through <book>` says which. Bush §7: the item stays where it
  is; what changes is the path through it.

## Open and closed

`**Status:** open` means someone is still walking it, and it can be picked up
across sessions and agents without friction. `closed` means the `## Learned`
line says where it arrived — **and that line is the owner's.** The agent may
propose it; it is never written on an agent's word alone.

## See Also

[[concepts/links-and-trails]] · [[sources/as-we-may-think]]
