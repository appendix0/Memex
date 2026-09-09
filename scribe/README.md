# scribe/

The Scribe reads a session transcript and keeps the Library current: the facts
in the Books, and the trail as their appendix. It is ours — written for MEMEX,
not inherited from any engine.

- `PROMPT.md` — the prompt. Written deliberately; this is the product.
- `../memex/scribe.py` — the runner: reads a transcript, hands it plus the
  Library's Books and trails to the model, applies the returned operations,
  writes the receipt.
- `../memex/edits.py` — applies those operations. The Scribe never writes files
  itself, which is why it cannot damage a Book.

**Input:** `~/.claude/projects/<encoded-cwd>/<session>.jsonl` — Claude Code's
own session transcript. Only `[user]` and `[assistant]` spoken lines are read;
tool calls, results, meta and sidechain records are dropped before the model
sees anything.

**Output:** candidates queued in `state/candidates.jsonl` — **outside** the
Library — plus append-only `## Trail` and `## Timeline` entries, whole-file
writes only under `trails/`, and one receipt line per segment in
`state/scribe-receipts.jsonl`. It cannot write a fact or create a Book.

**Run:** `memex scribe --pending`, or `memex scribe <transcript.jsonl>`. Add
`--dry` to see the operations without applying them.

## What it costs, and when it costs nothing

One `SessionEnd` hook, one model call per session — and only if the session
could contain something. `worth_scribing()` decides that from the text alone,
free: under 800 characters of new conversation, or fewer than two user turns,
and no call is made at all. The receipt still records where it stopped reading,
so that stretch is never looked at twice.

`PreCompact` was removed 2026-09-07. Compaction does not truncate the
transcript file, so `SessionEnd` already sees the whole session; firing at each
compaction paid the ~4.4k-token floor again for content that was going to be
read anyway.

If a run loses the lock it waits up to `MEMEX_LOCK_WAIT` (420s), and if that
expires the transcript is queued in `state/scribe-queue.txt` for the next run
rather than dropped. The budget applies to the whole run, queue included.

The one rule, from `PROMPT.md`: nothing enters a Book except through the
Button. The Scribe queues; the owner's yes, in a live session, writes.

## Why the runner is defensive

Each `claude -p` call is itself a Claude Code session, so on 2026-09-06 it fired
this repo's SessionEnd hook and called the Scribe again — 2,260 headless
sessions in a day. Five independent guards now prevent that, documented at the
top of `../memex/scribe.py`. Do not remove one because the others look
sufficient.
