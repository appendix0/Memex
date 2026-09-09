"""The Scribe: runs scribe/PROMPT.md against a finished transcript.

It reads a session after the fact and emits operations. It **cannot** create a
Book or write a fact -- that is refused in `edits.py`, not merely discouraged
here. What it can do is queue candidates and append below the line.

The model is reached through the `claude` CLI in headless mode, using the
same login the session uses. No API key is stored or read by this code.

WARNING. Every `claude -p` call below is itself a session in this repo, so it
fires this repo's SessionEnd hook, which calls the Scribe again. On 2026-09-06
that ran away: 2,260 headless sessions and 382 MB of transcripts in one day,
every one of them the Scribe reading the Scribe. FIVE independent guards now
stop it, and each must hold on its own:

  1. GEOGRAPHY      -- the child runs from SCRIBE_CWD, outside $HOME, which the
                       hook guard does not match; its own transcript is filed
                       outside the pool find_transcripts() searches.
  2. RECURSION      -- MEMEX_SCRIBE=1 is set on the child, and any process that
                       sees it refuses to scribe at all.
  3. SELF-BLINDNESS -- a transcript carrying our own prompt marker is never a
                       target, so even an unguarded child cannot feed on us.
  4. BUDGET         -- one invocation scribes at most MAX_PER_RUN transcripts,
                       none older than MAX_AGE_DAYS. A runaway stays bounded.
  5. LOCK           -- one Scribe at a time, with a bounded wait.

Do not remove one because the other four look sufficient. Guard 1 has already
failed silently once: widening the hook pattern from $HOME/memex* to $HOME/*
brought the child back inside the guard.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

from .edits import apply_all, parse_ops
from .trails import all_trails
from .library import ROOT, STATE, TZ, books, shelves

PROMPT = ROOT / "scribe" / "PROMPT.md"
RECEIPTS = STATE / "scribe-receipts.jsonl"
TRANSCRIPTS = Path.home() / ".claude" / "projects"

_SPOKEN_MAX = 60_000   # chars of conversation we hand the model per run

GUARD_ENV = "MEMEX_SCRIBE"   # set on the child; its presence forbids scribing
LOCK_WAIT = float(os.environ.get("MEMEX_LOCK_WAIT", "420"))  # hook budget is 600s
MAX_PER_RUN = 3              # transcripts one invocation may scribe
MAX_AGE_DAYS = 3             # older transcripts are history, not pending work

# The child `claude -p` runs HERE. Two consequences, both load-bearing: the
# hooks are guarded by `case "$PWD" in "$HOME"|"$HOME"/*)`, which this
# path does NOT match, so they exit at once; and the child's transcript is filed
# outside the pool find_transcripts() searches. The loop is broken by geography
# before any other guard is consulted.
#
# It must stay OUTSIDE $HOME. It lived under ~/.local/share until
# 2026-09-07, when the hook pattern was widened from $HOME/memex* to
# $HOME/* -- which silently brought the child back inside the guard and
# cost this guard entirely. Only the env guard was left holding it.
SCRIBE_CWD = Path("/var/tmp/memex-scribe-runs")


def _encoded(path: Path) -> str:
    """How Claude Code names a project directory: both "/" and "." become "-".

    Getting this wrong is not loud. A prune aimed at a directory that does not
    exist reports success and sweeps nothing, which is how the first version of
    this leaked one transcript per run while its own test printed 0.
    """
    return str(path).replace("/", "-").replace(".", "-")


SCRIBE_TRANSCRIPTS = TRANSCRIPTS / _encoded(SCRIBE_CWD)

# Appears verbatim in the prompt we send, therefore in every transcript the
# Scribe's own `claude -p` run leaves behind. This is how we recognise ourselves.
SELF_MARKER = b"# Open Inquiries (full text)"


class Busy(RuntimeError):
    """Another Scribe holds the lock. This one does nothing."""


QUEUE = STATE / "scribe-queue.txt"


def enqueue(path: Path) -> None:
    """Remember a transcript we could not scribe now, so a later run takes it.

    Losing the lock race must never lose the session. A transcript named only
    by a hook's stdin payload -- any session outside ~/memex -- has nothing
    else that would ever find it again.
    """
    STATE.mkdir(exist_ok=True)
    with QUEUE.open("a") as f:
        f.write(f"{path}\n")


def drain_queue() -> list[Path]:
    """Take everything queued by an earlier run that lost the race."""
    if not QUEUE.exists():
        return []
    out, seen = [], set()
    for line in QUEUE.read_text().splitlines():
        line = line.strip()
        if not line or line in seen:
            continue
        seen.add(line)
        p = Path(line)
        if p.is_file():
            out.append(p)
    QUEUE.unlink(missing_ok=True)
    return out


@contextlib.contextmanager
def single_run(wait_seconds: float = 0.0):
    """Guard 5: at most one Scribe on this machine, ever, at any instant.

    The env guard depends on inheritance and the marker on file content. This
    depends on neither. If a cascade ever starts by some route not foreseen
    here, every process after the first dies on this lock.

    `wait_seconds` because failing fast here silently DROPPED sessions: the
    hook log for 2026-09-07 shows four "busy" lines, each one a session that
    was never recorded by anything. A hook has a 600s budget; use some of it.
    """
    STATE.mkdir(exist_ok=True)
    lock = STATE / "scribe.lock"
    fh = lock.open("w")
    try:
        deadline = time.monotonic() + max(0.0, wait_seconds)
        while True:
            try:
                fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise Busy(f"another Scribe holds {lock}")
                time.sleep(3)
        fh.write(f"{os.getpid()} {datetime.now(TZ).isoformat(timespec='seconds')}\n")
        fh.flush()
        yield
    finally:
        fh.close()


def nested() -> bool:
    """True when this process was spawned by the Scribe. It must never scribe."""
    return bool(os.environ.get(GUARD_ENV))


def is_self_transcript(path: Path, probe: int = 200_000,
                       on_error: bool = True) -> bool:
    """True if this transcript is one of the Scribe's own headless runs.

    `on_error` is what an unreadable file counts as, and the two callers need
    opposite answers. Selecting work: True, so we skip it rather than spend a
    call. Deleting: False, because "I could not read it" must never authorise
    an unlink. (codex review, 2026-09-07)
    """
    try:
        with path.open("rb") as f:
            return SELF_MARKER in f.read(probe)
    except OSError:
        return on_error


# Harness wrappers to drop. Matching a bare "<" also threw away any real line
# that merely began with one -- a quoted tag, an XML snippet, "<- like this".
_WRAPPER = re.compile(r"\s*<(system-reminder|command-name|command-message|"
                      r"local-command|user-prompt-submit-hook|budget:)", re.I)


def line_count(jsonl: Path) -> int:
    try:
        with jsonl.open("rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def spoken_lines(jsonl: Path, start: int = 0) -> str:
    """Claude Code session transcript -> '[user]/[assistant]' spoken turns only.

    `start` skips records already scribed. PreCompact fires mid-session, so a
    long session is scribed once at compaction and again at SessionEnd; without
    this the second pass either re-reads everything or, once deduped, drops the
    entire back half of the conversation on the floor.
    """
    out = []
    for line in jsonl.read_text(encoding="utf-8", errors="replace").splitlines()[start:]:
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        role = rec.get("type")
        if rec.get("isMeta") or rec.get("isSidechain"):
            continue
        msg = rec.get("message") or {}
        content = msg.get("content")
        if role not in ("user", "assistant") or content is None:
            continue
        texts = []
        if isinstance(content, str):
            texts.append(content)
        else:
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    texts.append(part["text"])
        text = "\n".join(t for t in texts if t and not _WRAPPER.match(t)).strip()
        if text:
            out.append(f"[{role}]\n{text}\n")
    return "\n".join(out)


def _first_para(text: str, limit: int = 200) -> str:
    for block in text.split("\n\n"):
        b = " ".join(block.split())
        if b and not b.startswith(("#", "---", "**Status:")):
            return b[:limit]
    return ""


# The gate exists to skip sessions that cannot contain anything, not to ration
# what is recorded. It was built when every record needed BOTH parties, so it
# demanded two user turns -- but an observation needs none: the agent can notice
# that a link is dead while working alone, and that is worth keeping. Bush §6
# is "profligate"; the only thing this should stop is paying for an empty room.
MIN_CHARS = 300      # below this there is no conversation to read


def worth_scribing(conversation: str) -> tuple[bool, str]:
    """Is this worth a model call? A cheap gate in front of an expensive one.

    Every session end used to spend ~5k tokens of floor -- prompt plus Library
    context -- before a single word of the conversation was considered, and
    most sessions have nothing to record. This decides from the text alone, at
    no cost, and can only ever SKIP: it never records anything, so a false skip
    loses a record but a lax gate costs only tokens. Kept deliberately dumb for
    that reason -- volume and turn-taking, never meaning.
    """
    text = conversation.strip()
    if len(text) < MIN_CHARS:
        return False, f"only {len(text)} chars of new conversation"
    if "[assistant]" not in conversation and "[user]" not in conversation:
        return False, "no spoken turns at all"
    return True, ""


def _context() -> str:
    trails = all_trails()
    parts = ["# Open Inquiries (full text)\n"]   # SELF_MARKER: do not reword
    parts.append("\nThe routes through the Library. A trail records the association\n"
                 "and the logical relationship between Books -- each step names what\n"
                 "the one before it forced, and which Books it ties.\n")
    if not trails:
        parts.append("(none yet)\n")
    for t in trails:
        parts.append(f"\n- {t.slug} — {t.title} ({len(t.steps)} steps): "
                     + " → ".join(t.books) + "\n")

    # The Books themselves. Without these the Scribe cannot name where a fact
    # belongs, and every agreement it finds has nowhere to land.
    parts.append("\n# The Library — every Book\n\n")
    for b in books():
        tag = " [vault]" if b.vault else ""
        parts.append(f"- `{b.slug}`{tag} — {_first_para(b.above_the_line, 90)}\n")
    parts.append("\n# Shelves\n" + ", ".join(shelves()) + "\n")
    return "".join(parts)


def _prune_own_transcripts() -> int:
    """Delete the transcripts our own `claude -p` calls leave behind.

    MEMEX does not stack up piles. Everything in SCRIBE_TRANSCRIPTS was written
    by us, holds nothing but a prompt we can rebuild, and is deleted as soon as
    the answer is in hand.
    """
    if not SCRIBE_TRANSCRIPTS.is_dir():
        return 0
    n = 0
    for f in list(SCRIBE_TRANSCRIPTS.glob("*.jsonl")) + list(SCRIBE_TRANSCRIPTS.glob("*.jsonl.tmp")):
        # Only our own runs. Deleting everything in the directory would take a
        # human's transcript with it if anyone ever opened a session there.
        if not is_self_transcript(f, on_error=False):
            continue
        try:
            f.unlink(); n += 1
        except OSError:
            pass
    return n


def _ask(prompt: str, timeout: int = 600) -> str:
    # The child is a full Claude Code session. Left alone it would fire this
    # repo's SessionEnd hook and call the Scribe again -- that is what burned
    # 2026-09-06. Three things stop it here, before the guards in run():
    #   cwd=SCRIBE_CWD          the repo's hooks are $PWD-guarded, so they exit
    #   GUARD_ENV in the env    inherited by any hook that does run
    #   --setting-sources       user settings, where the hooks live, not loaded
    env = dict(os.environ, **{GUARD_ENV: "1"})
    SCRIBE_CWD.mkdir(parents=True, exist_ok=True)
    _prune_own_transcripts()          # anything a previous run raced past
    try:
        r = subprocess.run(
            ["claude", "-p", "--output-format", "text", "--model", "sonnet",
             "--setting-sources", "project"],
            input=prompt, capture_output=True, text=True, timeout=timeout,
            env=env, cwd=SCRIBE_CWD,
        )
    finally:
        time.sleep(1)                 # the child finalises its transcript on exit
        _prune_own_transcripts()
    if r.returncode != 0:
        raise RuntimeError(f"claude -p failed: {r.stderr[-800:]}")
    return r.stdout


def run(transcript: Path, dry: bool = False, start: int | None = None) -> dict:
    if nested():
        raise RuntimeError(f"{GUARD_ENV} is set: this process is a Scribe child "
                           "and must not scribe.")
    if is_self_transcript(transcript):
        raise RuntimeError(f"{transcript.name} is one of the Scribe's own runs.")
    total = line_count(transcript)
    if start is None:
        had = consumed().get(transcript.name)
        start = had if (had is not None and had > 0) else 0
    conversation = spoken_lines(transcript, start)
    ok, why = worth_scribing(conversation)
    if not ok:
        # No model call. The receipt still advances `lines`, so this stretch of
        # the transcript is never examined again.
        receipt = {"segment": transcript.name, "steps": 0, "opened": 0, "closed": 0,
                   "proposals_pending": 0, "rejections": 0, "inquiries_touched": [],
                   "skipped": why}
    else:
        conversation = conversation[-_SPOKEN_MAX:]
        from .criterion import render as _criterion
        prompt = (
            PROMPT.read_text()
            + "\n\n---\n\n" + _criterion()
            + "\n\nYou cannot press the Button -- nobody is here to answer it.\n"
              "Apply the six triggers anyway: what passes them is what you\n"
              "queue, and nothing else is worth queueing.\n"
            + "\n\n---\n\n# HOW TO ANSWER\n\n"
            "Output one JSON object per line — the operations, then the receipt\n"
            "last. Nothing else: no prose, no code fences, no explanation.\n"
            "Most of what you find is `observe`. Reach for it first, and never\n"
            "leave a question for the owner that a checkable statement would settle.\n"
            "If the session established nothing, output only the receipt.\n\n"
            "---\n\n" + _context()
            + "\n\n---\n\n# THE TRANSCRIPT\n\n" + conversation
        )
        answer = _ask(prompt)
        ops = parse_ops(answer)
        # The receipt is the last JSON line that is not an operation.
        receipt = {}
        for line in reversed(answer.strip().splitlines()):
            line = line.strip()
            if line.startswith("{") and line.endswith("}"):
                try:
                    cand = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(cand, dict) and "op" not in cand:
                    receipt = cand
                    break
        # `observe` does not touch a Book. It queues, and waits for the owner.
        notices = [o for o in ops if o.get("op") == "observe"]
        ops = [o for o in ops if o.get("op") != "observe"]
        # A cap, not a filter: the model ranks by putting the most important
        # first, and everything past MAX_PER_SESSION is dropped. An uncapped
        # queue is the backlog the owner never read.
        from .candidates import MAX_PER_SESSION, prune, room
        dropped = max(0, len(notices) - MAX_PER_SESSION)
        notices = notices[:MAX_PER_SESSION]
        queued = 0
        if not dry:
            from .candidates import add
            prune()                       # expire first, then measure the room
            free = room()
            over_full = max(0, len(notices) - free)
            for o in notices[:free]:
                if o.get("book") and o.get("text") and add(o["book"], o["text"]):
                    queued += 1
        else:
            over_full = 0
            queued = len(notices)
        if dropped:
            receipt["dropped_over_cap"] = dropped
        if over_full:
            # Not the same failure as the per-run cap, and it must not read as
            # one: this says the owner has stopped draining, not that the run was
            # noisy. On a schedule this is the number that matters.
            receipt["dropped_queue_full"] = over_full
        written, refused = apply_all(ops, dry=dry, actor="scribe")
        receipt["queued"] = queued
        receipt["segment"] = transcript.name   # never the model's label; this is the join key
        receipt["files_written"] = written
        if refused:
            receipt["refused"] = refused
    receipt["scribed_at"] = datetime.now(TZ).isoformat(timespec="seconds")
    receipt["from_line"] = start
    # A run that wrote nothing and refused everything has not consumed this
    # stretch of the transcript -- advancing `lines` here discarded the work
    # silently. Retry it, but bounded: a deterministic refusal would otherwise
    # loop forever. (codex review, 2026-09-07)
    stuck = receipt.get("refused") and not receipt.get("files_written")
    if stuck and _attempts(transcript.name) < 2:
        receipt["lines"] = start
        receipt["retry"] = True
    else:
        receipt["lines"] = total
        if stuck:
            receipt["abandoned"] = True
    receipt["dry"] = dry
    if not dry:
        STATE.mkdir(exist_ok=True)
        with RECEIPTS.open("a") as f:
            f.write(json.dumps(receipt, ensure_ascii=False) + "\n")
        if receipt.get("files_written"):
            # A record nobody can find is not a record. Search reads a cached
            # index and only rebuilds it when empty, so without this a Book the
            # Scribe just wrote stayed invisible to `memex recall` until someone
            # reindexed by hand. Embeddings are local and incremental, so this
            # costs a second and no money. (codex review, 2026-09-07)
            try:
                from .recall import reindex
                reindex()
            except Exception as e:            # never fail a write over search
                receipt["reindex_error"] = str(e)[:200]
    return receipt


def consumed() -> dict[str, int]:
    """segment -> how many transcript lines a previous run already read.

    A receipt written before 2026-09-07 carries no line count. We cannot know
    what it read, so it is recorded as -1 and treated as fully consumed: the
    conservative choice, since the alternative re-scribes the whole backlog.
    """
    if not RECEIPTS.exists():
        return {}
    counted: dict[str, int] = {}   # receipts that recorded where they stopped
    legacy: set[str] = set()       # receipts that did not
    for line in RECEIPTS.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        seg = r.get("segment")
        if not seg:
            continue
        name = Path(seg).name
        n = r.get("lines")
        if isinstance(n, int) and n >= 0:
            counted[name] = max(counted.get(name, 0), n)
        else:
            legacy.add(name)
    out = dict(counted)
    for name in legacy:
        out.setdefault(name, -1)   # only legacy receipts: treat as fully read
    return out


def _attempts(segment: str) -> int:
    """How many previous runs refused everything on this segment."""
    if not RECEIPTS.exists():
        return 0
    n = 0
    for line in RECEIPTS.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if Path(r.get("segment", "")).name == segment and r.get("retry"):
            n += 1
    return n


def needs_scribe(path: Path, seen: dict[str, int] | None = None) -> bool:
    """True if this transcript has content no run has read yet."""
    seen = consumed() if seen is None else seen
    had = seen.get(path.name)
    if had is None:
        return True          # never scribed
    if had < 0:
        return False         # legacy receipt, no line count: treat as done
    return line_count(path) > had


# Where the WORK happens, which is not where the Library lives. Every session
# on this machine runs from ~ or somewhere under it -- the always-on tmux session
# runs from ~ itself -- so transcripts are filed under `-home-<user>`, and
# `-home-<user>` does not start with `-home-<user>-memex`. Defaulting the scan
# to the repo made `pending()` return [] for every session that has ever run
# here; measured 2026-09-09, `-home-<user>-memex/` is empty and always has
# been. Nothing noticed because the hook passes the transcript in directly and
# never consults this. A scheduled run has no hook payload and consults nothing
# else, so it would have scribed nothing, silently, forever.
#
# This is the same boundary the hooks use: `case "$PWD" in "$HOME"|"$HOME"/*)`.
WORK = Path.home()


def find_transcripts(project_dir: Path = WORK) -> list[Path]:
    """Claude Code files transcripts under ~/.claude/projects/<encoded cwd>/.

    A session opened in a subdirectory or a worktree is filed under that path,
    so match the directory itself and every directory below it -- but on a
    segment boundary, so `-home-<user>` never swallows `-home-<user>XYZ`.
    """
    enc = _encoded(project_dir)   # one encoding, not two (codex review)
    if not TRANSCRIPTS.exists():
        return []
    cutoff = time.time() - MAX_AGE_DAYS * 86400
    out: list[Path] = []
    for d in TRANSCRIPTS.iterdir():
        if not (d.is_dir() and (d.name == enc or d.name.startswith(enc + "-"))):
            continue
        for f in d.glob("*.jsonl"):
            try:
                if f.stat().st_mtime < cutoff:
                    continue
            except OSError:
                continue
            if is_self_transcript(f):    # guard 2: never read our own runs
                continue
            out.append(f)
    return sorted(out, key=lambda p: p.stat().st_mtime)


def pending(project_dir: Path = WORK) -> list[Path]:
    """The transcripts a single invocation is allowed to scribe. Never unbounded."""
    if nested():
        return []
    seen = consumed()
    fresh = [p for p in find_transcripts(project_dir) if needs_scribe(p, seen)]
    return fresh[-MAX_PER_RUN:]          # guard 3: newest few, and no more
