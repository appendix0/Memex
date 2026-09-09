# MEMEX

A file-based associative memory for an AI agent, built directly on Vannevar
Bush's *As We May Think* (1945).

**3,439 lines of Python across 13 modules. 12 commands. No database, no
framework, no server, no remote.** The record is markdown you own; the index is
a cache you can delete and rebuild.

> The model is rented. The Library is the asset.

---

## The problem

An agent that forgets everything between sessions makes its user the memory.
The usual fix — write the conversation into a vector store and retrieve it
later — makes that worse, not better. Storing more is not knowing more.

The measured result across the agent-memory literature is consistent: adding
everything to memory scores *worse* than a frozen, hand-picked shelf, and both
lose badly to strict curation. Volume is not the win. **Admission is.**

So MEMEX inverts the usual design. Capture is profligate and lives outside the
Library. What enters the Library is decided one sentence at a time, by a human,
and nothing else can put it there.

## The core rule

**Nothing enters a Book except through the Button.**

The Button is the moment the owner is shown *one exact sentence* and *one exact
destination*, and says yes:

```
Should I write "The scheduler waters on a trailing-hour median, not the
latest reading" on projects/greenhouse?

  Yes  ·  Reword  ·  Different Book  ·  No
```

Not an abstract card saying "watering logic". Nobody can agree to a summary of a
fact they have not read.

This comes straight from Bush §7 — the memex ties two items together *when the
researcher presses a button*. Nothing ties itself. Bush got the human decision
for free, because his machine could not author anything. Ours can, so the rule
has to be stated and enforced in code: the background writer is **refused at the
function level** from creating a Book or writing a fact. It can only queue.

## Bush's four operations, and what implements each

| §7 operation | the question it answers | here |
|---|---|---|
| **SEARCH** | what matches this query? | `memex recall` — local embeddings, cosine over every chunk, layer-weighted |
| **INDEX** | where is this stored? | `brain/CLASSIFICATION.md` — the shelf **is** the Book's `type:`; everything else is a facet |
| **LINK** | what else is related? | `[[slug]]` anywhere in a Book. Free, no permission, no ceremony |
| **TRAIL** | what path is useful? | `brain/trails/*.md` — ordered steps, each naming what the step before it forced |

The fourth is the one that makes this a memex rather than a large private
library, and it is the one almost every "agent memory" system skips.

## What is in this repository

```
memex/          the system — 13 modules, no dependencies beyond PyYAML
bin/            memex, memex-daily, library
brain/          an EXAMPLE Library: 10 Books on 9 shelves, plus the rules
skills/         the write-path skill an agent follows to press the Button
scribe/         the prompt the background reader runs under
tests/          1,349 lines, ~270 checks, no network required
```

**`brain/` here is a worked example, about a fictional greenhouse controller.**
It is not anybody's Library. See "What this repo is not", below.

The rules are the interesting part of `brain/`:

- **`RESOLVER.md`** — the decision tree. Which visibility, then which type.
- **`CLASSIFICATION.md`** — one shelf per Book, many facets per Book, and why
  faceted classification (Ranganathan) rather than enumerative (Dewey).
- **`schema.md`** — the Book contract, and the honest list of what a machine
  actually checks versus what is merely followed.

## How a Book is shaped

Two layers, split by a horizontal rule:

```markdown
---
title: "Greenhouse controller"
type: project          # = the shelf. Always. No judgment call.
created: 2026-09-09
about: [greenhouse]    # topic facet, from a controlled list
---

Compiled truth. Rewritten as understanding changes.
One fact per line, each independently checkable.

---

## Trail      ← WHY it went this way. Append-only.
## Timeline   ← WHAT happened. Append-only.
```

Above the line is overwritable because a correction quotes the exact text it
replaces. That only works if facts are **points, not paragraphs** — a claim
buried in prose cannot be corrected without rewriting three claims that were
fine.

## Quickstart

Requires Python 3.11+ and PyYAML. Semantic recall additionally wants a local
[Ollama](https://ollama.com) with an embedding model; without it, recall falls
back to keyword matching.

```bash
git clone <this repo> memex && cd memex
pip install pyyaml
ollama pull bge-m3            # optional, for semantic recall

export MEMEX_TZ=Europe/Berlin # dates in Books use the owner's day
./bin/memex reindex
./bin/memex recall "why does the controller use a median"
./bin/memex trail building-the-greenhouse
./bin/memex doctor
```

`memex daily` on the shipped example proposes **nothing**, and reports a
backlog of ties instead. That is the rule working: a step's reason is quoted
from prose already written, and where the record holds none the step is dropped
rather than guessed. Write a sentence that says *why* two Books belong together
and the next pass will offer it.

Then make it yours: empty `brain/`, rewrite `CLASSIFICATION.md`'s controlled
vocabulary between the `about-terms` markers, and write your first Book.

### The commands

| | |
|---|---|
| `memex recall "<question>"` | semantic search over every Book |
| `memex trail [name]` | every route, or walk one in order with reasons |
| `memex trail --through <book>` | which routes reach this Book |
| `memex trail --orphans` | Books no route reaches |
| `memex open` | what is waiting on the owner's word |
| `memex note <book> "<text>" --agreed` | write a fact — **only after a Button** |
| `memex tie <trail> <book> --why "…"` | add a step to a route |
| `memex new <shelf/slug> …` | create a Book |
| `memex daily` | the 24-hour pass: propose trail steps. **Calls no model.** |
| `memex doctor` | broken links, orphans, index freshness, queue depth |
| `memex reindex` | rebuild the recall index |

### Hooks (optional)

MEMEX runs standalone. Wired into a harness that supports hooks, three events
make it self-maintaining:

| event | command | what it does |
|---|---|---|
| session start | `memex start` | injects the rules, the owner's preferences, and what is open |
| session end | `memex scribe --pending` | reads the finished transcript, queues candidates |
| turn end | `memex pending --nudge` | **exits 2** and refuses to end the turn while something queued is unasked |

The third one is the load-bearing one. A queue nobody is forced to look at is a
backlog, and a backlog is how nine unread proposals accumulate in a day.

## Two Buttons, because there are two acts

| | **FACT** | **TIE** |
|---|---|---|
| offers | a sentence and a destination | a Book and the route it would join |
| the question | *Should I write "…" on `shelf/book`?* | *Add `book` to `trail` as a step, because "…"?* |
| the reason is | composed from what was established | **quoted, never composed** |
| asked | when it is noticed | **first** — before any fact |

Ties are asked first because a fact with no route is in the Library but on
nobody's path. And a tie's reason is quoted from prose already written: where
the record holds no reason, the step is **dropped rather than guessed**.

## What is honestly weak

Stated here rather than discovered later:

- **`vault` is policy, not a sandbox.** Two things are mechanically enforced:
  whole-file writes are refused outside `trails/`, and paths escaping `brain/`
  are refused. Everything else holds because the agent follows it.
- **Recall degrades silently.** If the embedder is unreachable, search falls
  back to keyword matching without saying so. If results suddenly feel literal,
  check the embedder first.
- **`doctor`'s index check verifies presence, not freshness.** A Book edited
  without a reindex still reads green.
- **No hybrid lexical channel.** Exact identifiers — a flag name, a symbol —
  are hard to retrieve by meaning alone.
- **The daily pass proposes; it never writes.** By design, but it means an
  unattended machine accumulates a backlog rather than a Library.

## What this repo is not

**It is not anybody's Library.** The Books under `brain/` are worked examples
written for publication, about a fictional greenhouse.

A real Library holds identity, relationships, health, finances and third-party
material about people who never agreed to leave the machine that holds it. That
belongs on one machine, backed up encrypted, with no code-host remote — the
`vault` label exists precisely to mark what the exits must refuse, and a public
repository is an exit.

This repository was therefore **written fresh for publication rather than
exported and filtered.** Filtering only has to fail once.

## License

MIT. See `LICENSE`.

## Credit

Vannevar Bush, "As We May Think", *The Atlantic*, July 1945. Every design rule
here is traced to a numbered section of it; see
`brain/sources/as-we-may-think.md`.
