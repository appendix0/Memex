# MEMEX

A file-based associative memory for an AI agent, built directly on Vannevar
Bush's *As We May Think* (1945).

**3,439 lines of Python across 13 modules. 12 commands. No database, no
framework, no server, no remote.** The record is markdown you own; the index is
a cache you can delete and rebuild.

> The model is rented. The Library is the asset.

---

## Why this exists

Every session with an agent ends and takes its context with it. The next one
starts blind, so **you** become the memory — re-explaining the same decisions,
re-deriving the same constraints, and slowly discovering that the most valuable
thing in the work is the part nobody wrote down.

The usual fix is to pour transcripts into a vector store. That makes it worse.
Measured across the agent-memory literature: adding everything scores **13.05%**,
a frozen hand-picked shelf **16.75%**, and strict curation **38.50%**. Storing
more is not knowing more.

And volume is not even the real loss. What actually goes missing is **why**. A
year from now the code still says what it does, git still says what changed —
but nothing says why that turn was taken instead of the obvious one, or what
was tried first and abandoned, or which of two contradictory results superseded
the other. That reasoning is the expensive part, it exists only in someone's
head, and it evaporates first.

MEMEX is built to keep that. Not a log, not a summary, not a search index over
your chat history: **an ordered record of what is known and how it came to be
known**, in plain markdown, on your own disk.

## Why not your agent's built-in memory?

Most coding agents now ship one: the agent writes notes about you to a file, and
an index of them is loaded at the start of every session. It is genuinely useful,
and it is a different thing from this. Three differences decide it.

**1. Nothing retires.** Built-in memory has no supersession mechanism. When a
fact stops being true, there is no way to say so — the entry sits there being
injected into every session, and nothing records that it was ever wrong. This is
not hypothetical: on the machine this was built for, the memory index carried two
entries flagged at its highest priority, one instructing every session to run a
linter that had been uninstalled weeks earlier, and one asserting the search
index held zero embeddings when every chunk in it had a vector.

A MEMEX Book has two layers for exactly this. A correction replaces the claim
above the line by quoting it exactly, and *why it was replaced* stays below the
line, append-only. The old claim remains legible as history instead of vanishing
or, worse, persisting as an instruction.

**2. The cost grows without bound.** An index loaded every session is a tax you
pay per session, and it grows linearly with everything you have ever recorded.
MEMEX separates the two: the Library is *meant* to grow — Bush's §2 is explicit
that storage stops being the bottleneck — while what a session pays should be
capped and the rest retrieved **on demand**, by meaning.

Stated honestly, this repo has not finished that job. The retrieval half is
real. The injection half is not: the session block is part fixed and part whole
files pasted in, and those files grow. Measured on the Library it was built for,
about a third of the injection was genuinely fixed and the rest was not. Capping
it behind a single asserted constant is the next piece of work, not a property
to claim today.

**3. It stores conclusions; this stores reasoning.** Built-in memory is a flat
set of facts. There is no way to ask it *why* something is the way it is, because
the route was never recorded — only the destination. That is what `trails/` is,
and it has no equivalent in a notes file.

There is a fourth, and it is the one people argue about: **who writes.** Built-in
memory is written by the agent, on its own judgement, with nobody saying yes. That
is the add-everything regime, and it is the one the numbers above rank last.

Built-in memory is the agent's working notes about you. This is your record —
which is why it is plain markdown on your own disk, and why it outlives the
agent that helped you write it.

## What Bush actually proposed

Bush names four operations in §7. Almost every "agent memory" system implements
the first two and stops.

| §7 operation | the question | here |
|---|---|---|
| **SEARCH** | what matches this query? | `memex recall` — local embeddings, layer-weighted |
| **INDEX** | where is this stored? | the shelf **is** the Book's `type:`; everything else is a facet |
| **LINK** | what else is related? | `[[slug]]` anywhere in a Book. Free, no ceremony |
| **TRAIL** | **what path through knowledge is useful?** | `brain/trails/*.md` — ordered, reasoned routes |

> "The process of tying two items together is the important thing."
> — Bush, §7

The fourth is the one that makes a memex a memex rather than a large private
library, and it is the one that gets skipped.

---

## Trails — the point of the whole thing

A **link** says two Books are related. A **trail** is an ordered route over
those links where **every step says why that turn was taken**. Links are cheap
and made freely. A trail is the reasoning, made explicit and kept.

A trail is a file. This is the record itself — four steps, each naming what the
step before it forced:

```markdown
## Route

1. **A greenhouse needs a decision, not a clock.** — 2026-09-09
   A fixed schedule waters on time rather than on need, and the pots that need
   it least get the same water as the pots that need it most.
   → [[projects/greenhouse]]

2. **So the decision needed a measurement it could not be fooled by.** — 2026-09-09
   A single sensor briefly touching dry air during a top-up fired the pump twice
   in four minutes. Deciding on the trailing-hour median makes a one-sample
   excursion unable to move the decision.
   → [[research/germination-trial]]

3. **And the measurement had to be trialled against the thing it replaced.** — 2026-09-06
   Germination reached 67.3% under the median against 29.4% under the latest
   reading, and water use did not rise with it.
   → [[writing/benchmark-report]]

4. **The trap that survives the project belongs to the machine.** — 2026-09-09
   The cron PATH and stale-binary traps are properties of the host, and the next
   project to run there will hit them identically.
   → [[infra/home-server]]
```

Read that and you have the whole argument, in the order each decision forced the
next. No commit log gives you this. No summary of a chat gives you this.

And you walk it from the terminal:

```
$ memex trail building-the-greenhouse

trails/building-the-greenhouse — Why the greenhouse controller is shaped the way it is

  1. A greenhouse needs a decision, not a clock.   — 2026-09-09
     A fixed schedule waters on time rather than on need, and the pots that need i…
     → projects/greenhouse
     │
  2. So the decision needed a measurement it could not be fooled by.   — 2026-09-09
     A single sensor briefly touching dry air during a top-up fired the pump twice…
     → research/germination-trial
     │
  3. And the measurement had to be trialled against the thing it replaced.   — 2026-09-06
     Germination reached 67.3% under the median against 29.4% under the latest rea…
     → writing/benchmark-report
     │
  4. The trap that survives the project belongs to the machine.   — 2026-09-09
     The cron PATH and the stale-binary traps are properties of the host, and the …
     → infra/home-server
```

(The walk view truncates each reason at 78 characters — the file is the record,
the walk is an index of it.)

Four properties make it work:

- **Order is logical, not chronological.** Note step 3 is dated *earlier* than
  step 2. Dates ride along; they do not decide the sequence. A trail sorted by
  date is a chronology wearing a trail's clothes.
- **A reason is never invented.** Steps are quoted from prose already written in
  the Books. Where the record holds no reason, the step is **dropped, not
  guessed** — a plausible-sounding reason a model made up is worse than no step.
- **Steps are append-only.** A wrong step is answered by a later one, never
  rewritten. You can see how the thinking changed.
- **A Book holds no route.** It is *reached* by them. Bush §7: the item stays
  where it is; what changes is the path through it.

```
$ memex trail --through infra/home-server
1 trail(s) through infra/home-server:
  trails/building-the-greenhouse  step 4: The trap that survives the project belongs to the machine.

$ memex trail --orphans          # Books no route reaches — the real backlog
$ memex trail --unexplained      # ties nobody has given a reason yet
```

Those last two are the honest metric. Counting Books tells you nothing: a Book
can sit in the Library, perfectly indexed, and be on nobody's path.

---

## The record keeps itself

A record you have to remember to maintain is a record you will stop
maintaining. Four things run without being asked.

**At session start** — the Library announces itself: where it is, how to search
it, what is unresolved, and the rule for what is worth writing down. The agent
never has to be told the record exists.

**At session end** — a background reader (the *Scribe*) reads the finished
transcript and extracts checkable statements. It **cannot write a Book** — that
is refused at the function level, not merely discouraged — so it queues what it
found and waits.

**Every 24 hours** — a pass over the whole Library looks for links with one end
already on a trail and the other not, and proposes the step that would join
them. It reads only the Library, **calls no model**, and costs nothing to run.
It proposes; it never writes.

**At the end of every turn** — anything queued and unanswered **refuses to let
the turn end**. This is the load-bearing one. A queue nobody is forced to look
at is a backlog, and a backlog is how a dozen unread proposals accumulate in a
day.

```
$ memex doctor
  ok   links all resolve
  ok   every Book parses
  ok   search index current
  ok   Books hold fact only
  ok   prompt offers only ops we accept
  ----------------------------------------------------
  10 Books on 9 shelves, 2 vault
  1 trails; 6 Books on no route
  14 ties no trail explains
  0 candidates waiting
```

Every one of those checks exists because the thing it looks for actually went
wrong: a rename that left dead links, a Book written and never reindexed, a
prompt that drifted from what the code accepts.

---

## What gets in, and who decides

Capture is profligate; **admission is strict**. That asymmetry is the design.
Transcripts keep everything and live outside the Library. What enters a Book is
decided one sentence at a time.

"Above the line" is the whole of it in practice, and the qualifier is not a
loophole: a Book's **facts** are the Button's, and the appendices below them —
`## Trail` and `## Timeline` — are append-only and may be written by the
background Scribe without asking. `edits.py` refuses `fact` and `new` from the
Scribe in code, not in prose. A trail file is append-only too: a rewrite that
drops an existing step is refused rather than merged.

**Nothing enters a Book above the line except through the Button** — the moment
the owner is shown one exact sentence and one exact destination, and says yes:

```
Should I write "The scheduler waters on a trailing-hour median, not the
latest reading" on projects/greenhouse?

  Yes  ·  Reword  ·  Different Book  ·  No
```

Not an abstract card saying "watering logic". Nobody can agree to a summary of
a fact they have not read.

A **TIE** Button — a Book and the route it would join — is asked before any
fact, because a fact with no route is in the Library but on nobody's path.

And *what may be put in front of you* is not the agent's taste either. A closed
list of six triggers lives in `memex/criterion.py` and is injected into every
session and into the Scribe's prompt: a rule stated, a measurement taken, a
cause established, a source that changed a decision, a capability boundary
moved, a recorded claim contradicted. Nothing else qualifies. Expected rate is
2–5 a session — **zero when six things were established is a miss, and a dozen
is drift**, and both are visible.

Bush got the human decision for free; his machine could not author anything.
Ours can, so the rule had to be written down and put in code.

---

## How a Book is shaped

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

## What is in this repository

```
memex/          the system — 13 modules; PyYAML, and two more for `library`
bin/            memex, memex-daily, library
brain/          an EXAMPLE Library: 10 Books on 9 shelves, plus the rules
skills/         the write-path an agent follows
scribe/         the prompt the background reader runs under
tests/          1,702 lines, ~301 checks, no network required
```

The rules in `brain/` are the transferable part: **`RESOLVER.md`** (the decision
tree), **`CLASSIFICATION.md`** (one shelf per Book, many facets per Book, and
why faceted classification rather than enumerative), and **`schema.md`** (the
Book contract, with an honest list of what a machine actually checks versus what
is merely followed).

`DESIGN.md` goes deeper: the retrieval pipeline and how to verify it, the
Scribe's five recursion guards, and the durability pattern that replaces a
remote. `CONNECTORS.md` is a design note, **not a feature** — what it would take
to feed the Library from a source outside the conversation, and the constraints
that decide it.

## Quickstart

Python 3.11+ and PyYAML. Semantic recall additionally wants a local
[Ollama](https://ollama.com); without it, recall falls back to keyword matching
and says so on stderr. `bin/library`, the browser view, additionally needs
`markdown` and `cryptography` — the rest of the system runs without them.

```bash
git clone <this repo> memex && cd memex
pip install pyyaml
pip install markdown cryptography   # only for ./bin/library
ollama pull bge-m3            # optional, for semantic recall

export MEMEX_TZ=Europe/Berlin # dates in Books use the owner's day
./bin/memex reindex
./bin/memex recall "why does the controller use a median"
./bin/memex trail building-the-greenhouse
./bin/memex doctor
```

`memex daily` on the shipped example proposes **nothing** and reports a backlog
instead. That is the rule working: a step's reason is quoted from prose already
written, and where none exists the step is dropped rather than guessed. Write a
sentence saying *why* two Books belong together and the next pass will offer it.

Then make it yours: empty `brain/`, rewrite `CLASSIFICATION.md`'s controlled
vocabulary between the `about-terms` markers, and write your first Book.

### The commands

| | |
|---|---|
| `memex recall "<question>"` | semantic search over every Book |
| `memex trail [name]` | every route, or walk one with its reasons |
| `memex trail --through <book>` | which routes reach this Book |
| `memex trail --orphans` / `--unexplained` | the backlog that actually matters |
| `memex open` | what is waiting on your word |
| `memex note <book> "<text>" --agreed` | write a fact — after a Button |
| `memex tie <trail> <book> --why "…"` | add a step to a route |
| `memex daily` | the 24-hour pass. Calls no model |
| `memex doctor` | links, parsing, index, queue depth |

### Hooks (optional)

MEMEX runs standalone. Wired into a harness that supports hooks, three events
make it self-maintaining — see `hooks.example.json`.

| event | command |
|---|---|
| session start | `memex start` |
| session end | `memex scribe --pending` |
| turn end | `memex pending --nudge` — exits 2, refuses to end the turn |

## What is honestly weak

- **`vault` is policy, not a sandbox.** Two things are mechanically enforced:
  whole-file writes refused outside `trails/`, paths escaping `brain/` refused.
  Everything else holds because the agent follows it.
- **Recall degrades silently.** If the embedder is unreachable, search falls
  back to keyword matching without saying so.
- **`doctor` checks the index for presence, not freshness.** A Book edited
  without a reindex still reads green.
- **No hybrid lexical channel.** Exact identifiers are hard to retrieve by
  meaning alone.
- **The transcript store has no retrieval.** Bush's store is consultable; this
  one is not. Fixing it by bulk-indexing would contradict the 38.50% result
  above, so it stays open on purpose.

## What this repo is not

**It is not anybody's Library.** The Books under `brain/` are worked examples
written for publication, about a fictional greenhouse controller.

A real Library holds identity, relationships, health, finances and third-party
material about people who never agreed to leave the machine that holds it. That
belongs on one machine, backed up encrypted, with no code-host remote — the
`vault` label exists to mark what the exits must refuse, and a public repository
is an exit.

Durability without a remote is a solved problem, and it is not a private repo:
nightly asymmetric `gpg` to two independent object stores, private key off the
machine. `DESIGN.md` §7 has the pattern and the three checks that prove it works.

This repository was **written fresh for publication rather than exported and
filtered.** Filtering only has to fail once.

## License

MIT. See `LICENSE`.

## Credit

Vannevar Bush, "As We May Think", *The Atlantic*, July 1945. Every design rule
here is traced to a numbered section of it; see
`brain/sources/as-we-may-think.md`.
