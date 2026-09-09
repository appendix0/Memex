# MEMEX skills

Each fires at one unmistakable moment. If you cannot tell which one applies,
none of them does — do the work directly.

The owner, 2026-09-07: *"I hate when there are multiple skills that I do not even
know when to use them."* The count is the feature.

## Built

| The moment | Skill |
|---|---|
| Something should go into the Library — a fact, a new Book, a correction | `memex-input` |

## Not built yet

Named here so nobody invents a fifth one, and so this file never again
advertises something that does not exist.

| The moment | Skill |
|---|---|
| About to answer from memory about a person, project, or past decision | `memex-recall` |
| The Library needs a maintenance pass — broken links, orphans, stale index | `memex-hygiene` |

`memex-recall` is the more urgent of the two: answering from context instead of
from the record is how the Library's founding document went missing for a month.
Until it exists, run `memex recall "<the question, in words>"` by hand.

## Why input and append are one skill

The owner first asked for both. They collapse: the procedure is identical — compose
the sentence, show it to the owner with its destination, write on yes — and the only
difference is whether the Book already exists, which `memex recall` answers in
the first step. Two skills for one procedure is the thing he said he hates.

## Where writes actually come from

Nothing else can put a fact in a Book. The Scribe is refused in code
(`edits.py`, `BOOKS_ARE_OWNERS`): it runs after the session with nobody to ask, so
it queues candidates and nothing more. `memex-input` is the only door.

The owner, 2026-09-08: *"Memex should be a base of fact, not a knowledge queue
stacking up from all the session."*

Authored here, and symlinked into wherever your harness looks for skills. The repo is the record.
