# DESIGN

How MEMEX actually works, at the level you need to change it. `README.md` is the
front door; this is the room behind it.

---

## 1. The two halves

```
        THE STORE                          THE LIBRARY
  session transcripts, kept whole      brain/**.md, curated
  outside the Library, pruned          the abstract of the facts
  on a schedule
        ↑ profligate (§2, §6)              ↑ strict (§7)
        │                                  │
        └──────── the Button ──────────────┘
                one sentence, one destination,
                     the owner's yes
```

Bush keeps these apart and so does this. Applying the Button's bar to the store
means recording nothing; applying the store's bar to the Library means recording
everything. Both failures were observed during development — an early prompt
that demanded agreement for everything recorded nothing in 37 of 46 runs.

## 2. Recall — how retrieval actually works

**This is the part to distrust, so here is exactly how it is checked.**

### The pipeline

```
question in words
   → embedding (local Ollama, bge-m3, 1024 dims)
   → cosine against every chunk of every Book
   → × layer weight   (agreed 1.0 · observed 0.92 · appendix 0.88)
   → + facet vector   (discounted: says the Book is ON the subject,
                       even when its body never says the word)
   → ranked Books, with the matching excerpt
```

The facet vector matters more than it looks. A Book about someone's daily
routine may never contain their name; only its `about:` facet says so. Folded
into the body text it also leaked "notes owner" into the front of every excerpt,
so it is embedded and scored **from its own field** instead of being concatenated
into the prose.

### Verifying the embedder is doing its job

Three checks, in order.

```bash
# 1. is the embedder alive and returning real vectors?
curl -s http://127.0.0.1:11434/api/embed \
     -d '{"model":"bge-m3","input":"probe"}' | head -c 200
#    expect: 1024 floats, non-zero

# 2. is every chunk of every Book embedded?
python3 -c "
import json; d=json.load(open('state/recall-index.json'))
tot=sum(len(v['chunks']) for k,v in d.items() if k!='__version__')
emb=sum(1 for k,v in d.items() if k!='__version__' for c in v['chunks'] if c.get('vec'))
print(tot, emb)"
#    expect: equal numbers

# 3. can it FIND something written minutes ago?
memex recall "<a question only the new fact answers>"
```

**Only check 3 proves anything.** During development checks 1 and 2 passed while
check 3 failed — the content was embedded and simply unreachable. Checking that
the embedder is alive and that every chunk has a vector tells you nothing about
whether recall can find an answer.

### The silent-failure mode, named

`_embed()` returns `None` when the embedder is unreachable, and `search()` then
falls back to `_keyword()` **without saying so**. A dead embedder does not raise;
it quietly degrades to substring counting. If results suddenly feel literal,
check 1 first.

### The chunking defect, and why it is instructive

Asking *"what was the vault privacy guard hardcoded to before"* returned a Book
that does not contain the answer.

The fact sat in a 1,044-character chunk that **opened with an unrelated fact**.
Chunks were packed to a 1,200-character cap, so several unrelated claims shared
one vector, each diluted by its neighbours, and none of them ranked.

**Fix:** a paragraph that is a claim in its own right (≥200 chars) gets its own
vector. Short fragments still pack, or the index triples for no gain.

| | before | after |
|---|---|---|
| chunks | 201 | 415 |
| index size | 5.7 MB | 10.3 MB |
| the failing query | 0.453, **wrong Book** | **0.615, correct Book first** |

`INDEX_VERSION` was bumped 3 → 4 with the change. **A shape change must bump
it:** the per-Book content hash cannot notice that chunks are cut differently,
so without the bump every Book reads "unchanged" and keeps its stale vectors.

## 3. The Button — the three pressers

A Button is not a scheduled review. Three things can raise one:

1. **The owner asks.** Runs the `memex-input` skill: compose one standing
   statement, resolve the destination, ask, write on yes.
2. **The agent notices, mid-turn.** Bounded by the criterion in
   `memex/criterion.py` — six closed triggers, plus a two-part test. Asked *at
   the moment it happens*, never batched to the end of the session.
3. **The Stop hook forces it.** `memex pending --nudge` exits 2 and refuses to
   let the turn end while anything queued is unasked. This is the load-bearing
   one: a queue nobody is forced to look at is a backlog.

### The criterion, and why it is code rather than a Book

Six triggers. Nothing outside the list qualifies:

```
T1  the owner states a rule, preference, correction or decision
T2  a measurement — a number, count, rate or pass/fail from running something
T3  a cause established — "X is broken BECAUSE Y", with the evidence named
T4  an external source read that changed a decision
T5  a capability boundary moved — possible became impossible, or the reverse
T6  a recorded claim contradicted — a Book says X, we established not-X
```

Then, in one breath: **the future question it answers**, and **the thing a reader
would go look at**. Either missing, no Button.

Never: progress, plans, intentions, "it works now", restatements of a file, and
anything git or `--help` answers in under a minute.

It lives in `memex/criterion.py` — not in a Book — because a Book is read when
someone goes looking, and this has to be in front of the agent *before* it needs
it. One string, three readers (session start, the Scribe's prompt, the skill), no
copies to drift.

The expected rate is 2–5 per session. **Zero in a session that established six
things is a miss; a dozen is drift.** Both are visible, which is the point: the
owner's yes ratifies a sentence, but it cannot ratify a *selection* they never
saw.

### Two Buttons

A **FACT** Button offers a sentence and a destination. A **TIE** Button offers a
Book and the route it would join, with the reason **quoted from prose already
written**. Ties are rendered first everywhere they appear.

The asymmetry is deliberate: a fact is composed, a tie's reason is not. Where the
record holds no reason for a link, no step is proposed. A trail step invented by
a model is a writing assignment wearing a citation's clothes.

## 4. What "transcript" means here

A transcript is the harness's own append-only log of one session — every message
and tool call, written by the harness, not by MEMEX.

It is **the store**, in Bush's sense: kept whole, kept outside the Library,
pruned on a schedule. The Scribe reads it after the session ends. Nothing in it
is a record until it has passed a Button.

Two consequences worth stating:

- **The Library is not a summary of your transcripts.** Bulk-indexing the store
  into the Library is the design this project rejected; see the curation figures
  in `README.md`.
- **A spoken-text cap applies.** The Scribe truncates what it sends to the model.
  On a long session most of the transcript is never read, which is another
  reason capture cannot be the mechanism that keeps the record honest.

## 5. The automatic parts

### `memex daily`

The 24-hour pass, in the owner's design: *"Every 24h the system looks for the
whole memex and checks if any other change is made. If the agent founds
something that could be recorded on the trail, it put it on the queue. Then
whenever I come back, in any session, the agent shows me the button for the
trails first."*

It reads **the Library**, never a transcript, and **calls no model** — there is
no model call anywhere in `memex/trails.py`. So it costs nothing to run, and the
cadence is set by how fast the Library changes rather than by a token budget.

```
prune expired candidates
  → find links with one end already on a trail and the other not
  → quote the prose that holds the link  (drop it if there is none)
  → filter: headings, tables, lists, metadata lines, anything under 40 chars,
            anything containing an identifier
  → queue up to the room left under the global cap
```

It proposes and never writes.

### `memex doctor`

Five failing checks and a summary. Every one exists because the thing it looks
for actually went wrong.

| # | check | the failure it catches |
|---|---|---|
| 1 | links all resolve | a rename left dead links behind |
| 2 | every Book parses | frontmatter broken → invisible to everything |
| 3 | search index current | a Book written and never reindexed |
| 4 | Books hold fact only | an unagreed layer leaked into a Book |
| 5 | prompt offers only ops we accept | the prompt drifted from what the code handles |

Then, informationally: Books, shelves, vault count, trails, Books on no route,
ties no trail explains, candidates waiting, unanswered proposals.

**Known limit:** check 3 verifies *presence*, not *freshness*. A Book edited
without a reindex still reads green. Comparing the stored hash against a
recomputed one is the real check.

### The Scribe's five guards

Each run spawns a headless child session, which is a recursion risk: a child that
triggers the same hooks spawns another. During development an unguarded version
produced 2,260 headless sessions in a day.

1. **Geography** — the child runs from a directory outside `$HOME`, which the
   hook guard does not match, and its own transcript lands outside the pool the
   scanner searches.
2. **An environment marker** — set in the child, checked on entry.
3. **Self-blindness** — the Scribe skips transcripts containing its own marker.
4. **A budget** — at most 3 transcripts per run, nothing older than 3 days.
5. **A lock file** — one Scribe at a time, with a bounded wait.

Guard 1 is the one that broke silently once: widening the hook pattern from
`$HOME/memex*` to `$HOME/*` brought the child back inside the guard. Geography
is a strong guard only while the geography holds.

## 6. Bush, section by section

| § | what Bush says | what implements it |
|---|---|---|
| §2 | the record "must be continuously extended" | the transcript store, kept whole |
| §3-4 | the machine does the repetitive part; judgment stays human | the closed trigger list — scanning is mechanical, deciding is not |
| §5 | "we have to select from the record by indexing" | `memex recall`; an unfindable Book is a failure, not a filing success |
| §6 | be "profligate" about the store; ordinary indexing does not disappear | the store takes everything; `CLASSIFICATION.md` is the ordinary index under the trails |
| §7 | "the process of tying two items together is the important thing" | the Button, and `trails/` |
| §7.6 | a record earns its place by the question **not yet asked** | the second half of the criterion |
| §7.7 | trails transfer to a reader who was not there | every step names its reason |
| §8 | "trails can become shared knowledge artifacts" | sharing is a property of every trail, not a tier above them |

## 7. Durability — how a local-only Library survives

The Library has no remote, by design. That trades one risk for another: no code
host means no off-machine copy, and a disk is a single point of failure. The
answer is not a remote. It is an encrypted archive.

```
git, on the machine          →  history
nightly:  tar the workspace  →  gpg --encrypt --recipient <key>   (asymmetric)
                             →  upload to TWO independent S3-compatible stores
                             →  prune to a rolling window of snapshots
```

Four rules make it a backup rather than a gesture:

- **Encrypt before it leaves the machine**, never after. The provider must only
  ever hold ciphertext.
- **Encrypt to a public key, and keep the private key off the machine.** This is
  the rule worth changing an existing setup for: with a symmetric passphrase, a
  box that can write its backups can also read every one of them, so compromising
  the machine compromises its whole history. Asymmetric splits that — the machine
  can encrypt and cannot decrypt.
- **Two providers, independently credentialed.** One provider is an availability
  assumption, not a backup.
- **The restore runbook is stored *unencrypted* in both buckets, on purpose,**
  because it contains no secrets. A runbook you cannot read until after you have
  restored is not a runbook.

### The distinction the whole design rests on

**Encrypted-at-rest in a bucket is not the same as a public source remote.** The
first is a backup: the provider holds bytes it cannot read. The second is
publication. Confusing the two is exactly how a private Library ends up on a
code host "just for backup" — see `ACCESS_POLICY.md`.

### Verify it; do not believe it

An untested backup is a belief. Three checks, cheapest first:

1. **Count the objects** in each bucket and compare against the retention
   window. A leg that silently stopped uploading looks identical to one that
   never ran.
2. **Grep the upload log for warnings**, per leg. "No errors reported" is not
   the same as "errors were checked for".
3. **Restore into a scratch directory** and diff it against the live Library.
   This is the only check that proves anything; the first two only tell you
   where to look.

And one check specific to encrypting asymmetrically: **assert the archive was
encrypted to the key you meant**, by reading the packet header back before
upload. If the keyring changes underneath the job, `gpg` will cheerfully encrypt
to a different recipient and exit 0 — leaving a backup nobody holds the key for,
which looks exactly like a good one until the day it is needed.

Two failure modes worth naming because they are invisible until they matter: a
copy on the same disk is not a backup, and an access key that has never been
rotated is a standing credential with no expiry.

## 8. Where the code lives

| module | what it owns |
|---|---|
| `library.py` | reading Books off disk; the shelf↔type map; the controlled vocabulary |
| `edits.py` | applying ops to Books — **and refusing the ones that would damage one** |
| `candidates.py` | the queue outside the Library; the two kinds of Button |
| `criterion.py` | what earns a Button. One string, three readers |
| `recall.py` | chunking, embedding, scoring |
| `trails.py` | routes; the daily pass; quoting a reason rather than composing one |
| `scribe.py` | the headless reader and its five guards |
| `session.py` | what gets injected at session start |
| `pending.py` | what is waiting on the owner |
| `doctor.py` | the five checks |
| `page.py` | the Library rendered for a browser, loopback only |
| `__main__.py` | the CLI |

The asymmetry in `edits.py` is the design's spine: **the Scribe does not write
files.** It emits operations, and `edits.py` applies them. A model handed a whole
file will sometimes return it shorter than it found it, and a Book that silently
loses a paragraph is worse than a Book that never gained one. Here the only way
to remove text is to quote it exactly.
