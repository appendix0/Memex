# memex/ — the system

> "A memex is a device in which an individual stores all his books, records,
> and communications … an enlarged intimate supplement to his memory."
> — Bush, *As We May Think*, §6

No engine, no database, no scaffold, no server. **The markdown under `brain/`
is the record**; this package reads it directly, so nothing can disagree with
the files.

## The commands

| Command | What it does |
|---|---|
| `memex start` | session-start context: what is waiting, where the record is, the criterion, the owner's preferences |
| `memex recall "<q>"` | search every Book by meaning; `[vault]` tag on sensitive hits; `--no-vault` to exclude them |
| `memex reindex` | re-embed changed Books (local Ollama, keyword fallback if it is down) |
| `memex trail [name]` | every route through the Library, or walk one in order with its reasons |
| `memex tie <trail> <book> --why` | add a step to a route — **after a Button** |
| `memex note <book> "<text>"` | queue a candidate; `--agreed` writes it as fact — **after a Button** |
| `memex new <shelf/slug> …` | create a Book — **after a Button** |
| `memex open` | everything waiting on the owner's word |
| `memex pending [--accept ID\|--drop ID]` | the candidate queue; `--nudge` is the Stop hook |
| `memex daily` | the 24-hour pass: propose trail steps from the Library. **Calls no model** |
| `memex doctor` | broken links, unparseable Books, index state, queue depth |
| `memex scribe <transcript>` / `--pending` | run `scribe/PROMPT.md` over a finished session; `--dry` shows without writing |

## How the pieces fit

```
   a session
      ├─ SessionStart ─►  memex start   ──►  context injected
      ├─ Stop ─────────►  memex pending --nudge  ──►  exit 2 while anything is unasked
      └─ SessionEnd ───►  memex scribe --pending ─┐
                                                  ▼
                          the harness's transcript for that session
                                                  │  spoken lines only, capped
                                                  ▼
                         a headless model run  +  scribe/PROMPT.md  +  the criterion
                                                  │
                                                  ▼
                     state/candidates.jsonl   +   state/scribe-receipts.jsonl
                             │
                             └── the Button ──►  a fact in a Book
```

The model is reached through a CLI in headless mode, on the same login the
session uses. **No API key is read or stored by this code.**

## Files

- `library.py` — read Books: frontmatter, `visibility`, sections, links; the
  shelf↔type map; the controlled `about:` vocabulary; the timezone
- `edits.py` — apply ops to Books, and **refuse the ones that would damage one**
- `candidates.py` — the queue outside the Library; the two kinds of Button
- `criterion.py` — what earns a Button. One string, three readers
- `recall.py` — chunk, embed, score; index at `state/recall-index.json`
- `trails.py` — routes, the daily pass, and quoting a reason rather than inventing one
- `scribe.py` — transcript → spoken lines → prompt → ops → receipt, behind five guards
- `session.py` — the session-start screen
- `pending.py` — what is waiting on the owner, across Books and the queue
- `doctor.py` — the five checks
- `page.py` — the Library rendered for a browser, bound to loopback only
- `__main__.py` — the CLI; `bin/memex` wraps it

## What is deliberately absent

- **Auto-writing Books from transcripts.** The Scribe **cannot** create a Book
  or write a fact — that is a capability boundary in `edits.py`, not an
  instruction. It runs after the session with nobody to ask, so it queues.
- **A database.** The index is a cache of embeddings, rebuilt from the files.
  Delete `state/recall-index.json` and nothing is lost.
- **A server.** Nothing here pushes, exports, or serves to another agent. See
  `ACCESS_POLICY.md`.

## Receipts

Every Scribe run appends one JSON line to `state/scribe-receipts.jsonl`, zeros
included. A transcript with no receipt is a miss; a receipt with zeros is a
session where nothing qualified. `memex start` reports the week's totals — which
is how a Scribe that has silently stopped finding anything becomes visible.
