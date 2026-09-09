# CLAUDE.md

Notes for an agent session opened in this folder. `AGENTS.md` is the contract;
this file is the harness-specific part.

@AGENTS.md

## Specifics

- **The files are the record.** Write Books by editing `brain/` directly. There
  is no database to write through and no sync to wait for. Anything that exists
  only in an index is not part of MEMEX.
- **Recall before you grep.** `memex recall "<question>"` searches every Book by
  meaning, with a keyword fallback. Prefer it over file greps for anything about
  people, projects, or the past. Ask in the words of the question, not in
  keywords.
- **Hooks.** `SessionStart` → `memex start`, which injects the standing rules,
  the owner's preferences and everything open — do not duplicate what it
  injects, use it. `SessionEnd` → `memex scribe --pending`. `Stop` →
  `memex pending --nudge`, which exits 2 and refuses to end a turn while
  anything is unagreed. See `hooks.example.json`.
- **Never invoke the Scribe by hand mid-session.** Each run spawns a headless
  child session. Five guards keep that bounded — geography, an environment
  marker, self-blindness, a budget, and a lock file — and there is no reason to
  lean on them.
- **The Scribe cannot write a Book.** That is a capability boundary in
  `memex/edits.py`, not an instruction it is trusted to follow. It queues; the
  Button writes.
