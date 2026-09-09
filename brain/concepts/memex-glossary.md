---
title: "MEMEX glossary — the canonical terms"
type: concept
created: 2026-09-09
about: [memex]
---

# MEMEX glossary

One name per thing. A term that drifts is a term the next agent reinvents, and
two names for one thing is how a system ends up with two implementations of it.

**If a term is missing, add it here before using it anywhere else.**

---

## The parts

| Term | Means | Not to be called |
|---|---|---|
| **MEMEX** | the whole system: the Library, the code, the rules, the agent contract | "the brain", "the database" |
| **the Library** | the markdown files under `brain/`. One collection, one index. | "the vault" (that is a label), "the corpus" |
| **a Book** | one markdown file in the Library | "a page", "a note", "a doc", "an entry" |
| **a Shelf** | one directory of the Library, named by a `type:` | "a category", "a folder" |
| **a facet** | a frontmatter descriptor — `about:`, `status:`, `kind:`, `domain:` | "a tag" |
| **the index** | `state/recall-index.json`, behind `memex recall`. A cache; delete and rebuild. | "the database" — it is never the record |
| **the store** | the session transcripts, kept whole and outside the Library | "the archive" |

## The acts

| Term | Means | Not to be called |
|---|---|---|
| **the Button** | the moment the owner is shown one exact sentence and one exact destination, and says yes. **The only way anything enters a Book.** | "the prompt", "the confirmation", "AskUserQuestion" — that is today's widget, not the thing |
| **a candidate** | something noticed, queued **outside** the Library, waiting for a Button | "a proposal", "a pending fact" — it is not in a Book at all |
| **a fact** | one standing statement above the line in a Book, independently true and independently checkable | "a claim", "a memory" |
| **an observation** | a checkable statement nobody had to assent to | "a finding" |
| **a link** | a tie between two Books, made freely | "a reference", "a backlink" |
| **a trail** | the ordered, reasoned route over links. `trails/`. | "a path", "a chain", "an inquiry" — an open trail *is* the inquiry |
| **a step** | one move on a trail: the move, the date, and why that turn was taken | "an entry" |
| **the Scribe** | `memex scribe` — reads a finished session and queues what is checkable. It **cannot** write a Book. | "the librarian", "the summarizer" |
| **the daily pass** | `memex daily` — reads the Library, proposes trail steps, calls no model | "the cron job", "the sweep" |

## The labels

| Term | Means |
|---|---|
| **vault** | `visibility: vault` in frontmatter. The agent reads it; the **exits** refuse it. Not a wall, a mark. |
| **agreed** | provenance: the owner said yes in a live session. The only provenance that may overwrite. |
| **observed** | provenance: checkable, nobody assented. Append-only, always. |
| **archived** | `status: archived` — retired. **Never a synonym for private.** |

## Two things that share a word

- **A Book's `## Trail`** is an appendix section inside one Book: *why it went
  this way*. **A trail** is a file under `trails/`: a route between Books. They
  share a word and nothing else. When it matters, say "the trail file" or "the
  Book's Trail section".
- **`## Timeline`** is *what happened*; **`## Trail`** is *why*. If it could be
  written from a diff or a commit message, it is a Timeline entry.

## Words this project does not use

- **"memory"** for the Library. A Library is curated; memory is what a session
  loses. Saying "memory" invites the assumption that writing is automatic.
- **"knowledge base"**. It is a base of **fact**, and the distinction is the
  whole design: *"MEMEX should be a base of fact, not a knowledge queue stacking
  up from all the sessions."*
- **"ingest"**. Nothing is ingested. Things are agreed, one at a time.

## See Also

[[concepts/links-and-trails]] · [[RESOLVER]] · [[CLASSIFICATION]] · [[schema]]
