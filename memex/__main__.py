"""memex — the CLI.

  memex start                     session-start context (hook)
  memex recall "<query>" [-n N]   search every Book
  memex reindex                   re-embed changed Books
  memex open                      proposals waiting on the owner
  memex note <shelf/book> "<s>" --agreed      record a fact (the owner said yes)
  memex new  <shelf/slug> --title T --text S  create a Book
  memex pending [--accept ID|--drop ID]       the queue waiting on the owner
  memex scribe <transcript.jsonl> [--dry]
  memex scribe --pending [--dry]  the newest few unscribed transcripts
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


_HOOK: dict | None = None


def _hook_json() -> dict:
    """The hook payload Claude Code writes to stdin, read at most once.

    stdin is a single-shot pipe -- a second reader gets nothing. `scribe`
    wants transcript_path and `pending --nudge` wants stop_hook_active, so it
    is read here and cached rather than by whoever asks first.
    """
    global _HOOK
    if _HOOK is not None:
        return _HOOK
    _HOOK = {}
    if sys.stdin is None or sys.stdin.isatty():
        return _HOOK
    try:
        raw = sys.stdin.read()
    except Exception:
        return _HOOK
    try:
        d = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError:
        return _HOOK
    if isinstance(d, dict):
        _HOOK = d
    return _HOOK


def _hook_payload() -> Path | None:
    """The transcript Claude Code names on stdin when it fires a hook.

    SessionEnd and PreCompact pass {"transcript_path": ...}. Taking it is
    strictly better than searching by directory prefix: it works for a session
    opened anywhere, and it can never pick up an unrelated project. Before
    this, a session started in ~ was given context by SessionStart and then
    never recorded, because ~/.claude/projects/-home-<user> does not begin with
    the repo's encoded path.
    """
    p = _hook_json().get("transcript_path")
    if not p:
        return None
    path = Path(p)
    return path if path.is_file() else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="memex", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("start")
    r = sub.add_parser("recall"); r.add_argument("query"); r.add_argument("-n", type=int, default=5)
    r.add_argument("--no-vault", action="store_true")
    r.add_argument("--agreed", action="store_true", help="only the curated layer")
    r.add_argument("--observed", action="store_true", help="only auto-captured")
    sub.add_parser("reindex")
    sub.add_parser("daily", help="the 24h pass over the Library — propose ties")
    ti = sub.add_parser("tie", help="add a step to a route — after the owner said yes")
    ti.add_argument("trail"); ti.add_argument("book")
    ti.add_argument("--why", required=True, help="the reason, QUOTED from the record")
    ti.add_argument("--date", default="")
    sub.add_parser("open")
    dr = sub.add_parser("doctor", help="check the whole structure")
    dr.add_argument("--brief", action="store_true")
    pd = sub.add_parser("pending", help="candidate facts waiting on the owner")
    pd.add_argument("--accept", metavar="ID"); pd.add_argument("--drop", metavar="ID")
    pd.add_argument("--nudge", action="store_true",
                    help="for the Stop hook: say something only if the owner owes an answer")
    tr = sub.add_parser("trail", help="walk a trail, or list them")
    tr.add_argument("slug", nargs="?")
    tr.add_argument("--through", metavar="BOOK",
                    help="which trails pass through this Book (Bush §7)")
    tr.add_argument("--orphans", action="store_true",
                    help="Books no trail reaches")
    tr.add_argument("--unexplained", action="store_true",
                    help="ties no trail has given a reason for — the backlog")
    tr.add_argument("--suggest", metavar="BOOK",
                    help="recover a candidate route from links and dates already in the Library")
    tr.add_argument("--depth", type=int, default=1)
    tr.add_argument("--sync", action="store_true",
                    help="rewrite each Book's ## Trail to the routes that cross it")
    n = sub.add_parser("note", help="record something into a Book, now")
    n.add_argument("book"); n.add_argument("text")
    n.add_argument("--agreed", action="store_true",
                   help="the owner assented. Only these may overwrite.")
    n.add_argument("--replaces", help="exact text to supersede (needs --agreed)")
    nw = sub.add_parser("new", help="create a Book — after the owner said yes")
    nw.add_argument("book", help="shelf/slug")
    nw.add_argument("--title", required=True)
    nw.add_argument("--text", required=True, help="the abstract of the facts")
    nw.add_argument("--type", default="",
                    help="omit to infer it from the shelf — they are the same fact")
    nw.add_argument("--about", default="",
                    help="comma-separated subject slugs (brain/CLASSIFICATION.md)")
    nw.add_argument("--vault", action="store_true", help="RESOLVER Test 0")

    s = sub.add_parser("scribe"); s.add_argument("transcript", nargs="?")
    s.add_argument("--pending", action="store_true"); s.add_argument("--dry", action="store_true")
    a = ap.parse_args(argv)

    if a.cmd == "start":
        from .session import render
        sys.stdout.write(render()); return 0

    if a.cmd == "recall":
        from .recall import search
        kinds = None
        if a.agreed:
            kinds = {"agreed"}
        elif a.observed:
            kinds = {"observed"}
        for h in search(a.query, a.n, include_vault=not a.no_vault, kinds=kinds):
            tag = " [vault]" if h.vault else ""
            print(f"[{h.score:.3f}] {h.slug}{tag} [{h.kind}] — {h.title}\n    {h.excerpt}")
        return 0

    if a.cmd == "reindex":
        from .recall import reindex
        c, u = reindex(verbose=True); print(f"indexed {c}, unchanged {u}"); return 0

    if a.cmd == "trail":
        from .library import BRAIN as BRAIN_
        from .trails import all_trails, orphans, render_suggestion, suggest, through, walk
        if a.sync:
            from .trails import sync_backrefs
            w, sk = sync_backrefs()
            print(f"back-references written into {len(w)} Books")
            for slug in sk:
                print(f"  SKIPPED {slug}: carries a ## Trail no route reaches. "
                      "Move that prose into a trail first; it is not deleted.")
            return 0
        if a.suggest:
            rows = suggest(a.suggest, depth=a.depth)
            if not rows:
                print(f"No Book {a.suggest!r}."); return 1
            print(render_suggestion(a.suggest, rows))
            print("Name the question and confirm the route, and this becomes an\n"
                  "Inquiry. Steps marked *** have no reason in the record; they\n"
                  "are dropped, not guessed.")
            return 0
        if a.unexplained:
            from .trails import unexplained
            u = unexplained()
            from collections import Counter
            c = Counter(a_ for a_, _ in u)
            print(f"{len(u)} ties no trail explains.\n\n"
                  "A link says these belong together. A trail says what that\n"
                  "forced. These are the ties nobody has reasoned about yet —\n"
                  "raw material, and the honest measure of what is left.\n")
            for slug, n in c.most_common(12):
                print(f"  {n:3d}  {slug}")
            return 0
        if a.orphans:
            o = orphans()
            print(f"{len(o)} Books no trail reaches:")
            for slug in o:
                print(f"  {slug}")
            print("\nBush §7: an item is reached by the paths through it. A Book on\n"
                  "no path is in the Library but not in anyone's route.")
            return 0
        if a.through:
            hits = through(a.through)
            if not hits:
                print(f"No trail passes through {a.through}."); return 0
            print(f"{len(hits)} trail(s) through {a.through}:")
            for t, st in hits:
                print(f"  {t.slug}  step {st.n}: {st.move}")
            return 0
        trails = all_trails()
        if a.slug:
            # A bare name resolves against the one shelf.
            for t in trails:
                if t.slug == a.slug or t.slug.split("/", 1)[1] == a.slug:
                    print(walk(t)); return 0
            print(f"No trail {a.slug!r}. Try `memex trail` to list them."); return 1
        if not trails:
            print("No trails yet."); return 0
        for t in trails:
            print(f"{t.slug:44s} {len(t.steps)} steps, {len(t.books)} Books"
                  f"   {t.title}")
        return 0

    if a.cmd == "doctor":
        from .doctor import report
        out, bad = report(brief=a.brief)
        print(out)
        return 1 if bad else 0

    if a.cmd == "pending":
        from .candidates import accept, pending, prune, render, take
        if a.nudge:
            # The Stop hook. Exit 2 does not print a reminder that can be
            # read past -- it REFUSES to end the turn and hands this back to
            # the agent on stderr. Measured 2026-09-08: Stop input carries
            # stop_hook_active, and Claude Code caps consecutive blocks at 8.
            if _hook_json().get("stop_hook_active"):
                return 0          # already sent back once; never loop
            prune()
            q = pending()
            if not q:
                return 0
            from .candidates import steps_first
            q = steps_first(q)
            n_step = sum(1 for c in q if c.kind == "step")
            head = (f"[memex] {len(q)} thing(s) noticed and NOT yet agreed. Do not "
                    f"end the turn. Press the Button on each — run the "
                    f"memex-input skill, one AskUserQuestion per item.")
            if n_step:
                # The owner, 2026-09-09: the trail Buttons come first. Bush §7 calls
                # the tie the important act; facts we have no shortage of.
                head += (f" {n_step} of them are TIES — ask those FIRST, and ask "
                         f"them as ties, not as sentences.")
            out = [head]
            for c in q[:4]:
                if c.kind == "step":
                    out.append(f'  TIE  Add {c.book} to {c.trail} as a step, '
                               f'because "{c.text[:90]}"?   id={c.id}')
                else:
                    out.append(f'  FACT Should I write "{c.text[:100]}" on '
                               f'{c.book}?   id={c.id}')
            if len(q) > 4:
                out.append(f"  …and {len(q) - 4} more — `memex pending`.")
            out.append("  yes -> `memex pending --accept <id>`   "
                       "no -> `memex pending --drop <id>`")
            print("\n".join(out), file=sys.stderr)
            return 2
        if a.accept:
            book = accept(a.accept)
            print(f"recorded into {book}" if book else "no such candidate")
            return 0 if book else 1
        if a.drop:
            c = take(a.drop)
            print(f"dropped {c.book}: {c.text[:70]}" if c else "no such candidate")
            return 0 if c else 1
        out = render(limit=99)
        print(out if out else "Nothing waiting. The Books hold only fact.")
        return 0

    if a.cmd == "new":
        # `new` has lived in edits.py all along, with every Test 0 and vault
        # guard on it, and nothing in the CLI could reach it -- only the
        # Scribe, which is now refused outright. So until this command the
        # skill had no way to make a Book at all.
        from .edits import Refused, apply_op
        # The shelf and the type are one fact (brain/CLASSIFICATION.md), so
        # either one determines the other and giving both is a chance to
        # disagree. Infer when it was not passed; apply_op refuses a mismatch.
        from .library import SHELF
        shelf = a.book.strip("/").split("/")[0]
        type_for_shelf = {v: k for k, v in SHELF.items() if v}
        op = {"op": "new", "book": a.book, "title": a.title, "text": a.text,
              "type": a.type or type_for_shelf.get(shelf, "note")}
        if a.about:
            op["about"] = [s.strip() for s in a.about.split(",") if s.strip()]
        if a.vault:
            op["visibility"] = "vault"
        try:
            rel = apply_op(op)
        except Refused as e:
            print(f"refused — {e}")
            return 1
        print(f"created {rel}.  next: memex reindex")
        return 0

    if a.cmd == "note":
        # The live path. Bush presses the button AT THE MOMENT (§2-3), not in a
        # sweep afterwards; the Scribe runs headless with nobody to ask, which
        # is the only reason a queue exists at all.
        from .edits import Refused, apply_op
        # `memex note <book> <text>` — I got this backwards myself and the error
        # that came back was "<the whole sentence> does not exist — use op
        # 'new'", which reads as a missing Book rather than swapped arguments.
        if " " in a.book or "/" not in a.book:
            print(f"refused — first argument is the Book, second is the text.\n"
                  f"  got book={a.book[:60]!r}\n"
                  f"  try: memex note <shelf/book> \"<statement>\" [--agreed]")
            return 1
        # --replaces without --agreed used to be silently DROPPED: the caller
        # asked to supersede something and got an append instead, with a success
        # message. Refuse loudly; a downgrade nobody is told about is the exact
        # failure this provenance split exists to prevent.
        if a.replaces and not a.agreed:
            print("refused — --replaces supersedes an existing fact, so it needs "
                  "--agreed (the owner's word). Drop --replaces to append an observation.")
            return 1
        if a.agreed:
            op = {"op": "fact", "book": a.book, "text": a.text,
                  "provenance": "agreed"}
            if a.replaces:
                op["replaces"] = a.replaces
        else:
            # Not fact yet. It waits for the owner, outside the Library.
            from .candidates import add
            c = add(a.book, a.text, source="note")
            if c is None:
                print("already queued — this restates a candidate already waiting")
                return 0
            print(f"queued `{c.id}` for {a.book}. `memex pending` to see it, "
                  f"`memex pending --accept {c.id}` once the owner says yes.")
            return 0
        try:
            apply_op(op)
        except Refused as e:
            print(f"refused — {e}"); return 1
        from .recall import reindex
        reindex()
        kind = "recorded as fact" if a.agreed else "queued as a candidate"
        print(f"{a.book}: {kind}")
        return 0

    if a.cmd == "tie":
        # The partner of `memex note`. Two acts, two commands, so that neither
        # can be performed by accident while meaning the other. A step lands in
        # trails/, never in a Book: a route that lives inside one Book cannot
        # pass through another, so it would not be a route.
        from .trails import append_step
        from .edits import Refused, apply_op
        from datetime import datetime
        from .library import TZ
        date = a.date or datetime.now(TZ).strftime("%Y-%m-%d")
        try:
            body = append_step(a.trail, a.book, a.why, a.why, date)
            apply_op({"op": "trail_file", "book": a.trail, "body": body})
        except (ValueError, Refused) as e:
            print(f"refused — {e}"); return 1
        from .recall import reindex
        reindex()
        print(f"{a.trail}: {a.book} tied as a step")
        return 0

    if a.cmd == "daily":
        # The owner, 2026-09-09: "Every 24h the system looks for the whole memex and
        # checks if any other change is made. If the agent founds something that
        # could be recorded on the trail, it put it on the queue."
        #
        # It reads the Library and calls no model, so it costs nothing. It
        # proposes; it never writes. What it cannot find a written reason for is
        # left in the backlog rather than turned into homework.
        from .trails import propose_steps, unexplained, orphans
        from .candidates import add_step, prune, room
        expired = prune()
        free = room()
        made = 0
        if free:
            for r in propose_steps(limit=free):
                if add_step(r["trail"], r["book"], r["via"], r["date"], r["why"]):
                    made += 1
        print(f"queued {made} tie(s) for the Button"
              + (f"; expired {expired}" if expired else "")
              + (" — queue full" if not free else ""))
        print(f"backlog: {len(unexplained())} ties no trail explains, "
              f"{len(orphans())} Books on no route")
        return 0

    if a.cmd == "open":
        # Two different things wait on the owner and both must show here. Measured
        # 2026-09-09: three candidates sat in the queue while this command
        # said "Nothing waiting on you", because it only ever read the open
        # questions inside Books. Session start advertises `memex open` as
        # "what is waiting on your word", so a queue it cannot see is a queue
        # that rots -- the exact failure the Button exists to prevent.
        from .pending import render, waiting
        from .candidates import render as queued_render
        items = waiting()
        queued = queued_render(limit=99)
        if not items and not queued:
            print("Nothing waiting on you."); return 0
        if queued:
            print(queued)
            print("\nyes -> `memex pending --accept <id>`   "
                  "no -> `memex pending --drop <id>`")
        if items:
            if queued:
                print()
            print(render(full=True))
            print(f"\nEach sits in the Book named above. Answer one and it stops "
                  f"being a question; say so and I will record it as agreed.")
        return 0

    if a.cmd == "scribe":
        from .scribe import (Busy, GUARD_ENV, drain_queue, enqueue, nested,
                             pending, run, single_run)
        # A Scribe child fires this repo's hooks too. It leaves without a word.
        if nested():
            print(f"{GUARD_ENV} set — nested Scribe, nothing done")
            return 0
        targets: list[Path] = []
        if a.pending:
            from .scribe import needs_scribe
            hooked = _hook_payload()
            if hooked is not None:
                # The session that just ended. Scribe it only if it has content
                # no run has read -- PreCompact and SessionEnd both fire on the
                # same file, and the second must add the tail, not repeat it.
                targets = [hooked] if needs_scribe(hooked) else []
                if not targets:
                    print(f"nothing new in {hooked.name}")
            else:
                targets = pending()
            # Anything an earlier run queued after losing the lock race.
            for q in drain_queue():
                if q not in targets and needs_scribe(q):
                    targets.append(q)
            # The budget applies to the whole run, queue included -- otherwise a
            # backlog of queued sessions becomes one unbounded invocation, which
            # is the shape of the thing the budget exists to prevent. Whatever
            # does not fit goes back on the queue for the next run.
            from .scribe import MAX_PER_RUN
            if len(targets) > MAX_PER_RUN:
                for t in targets[MAX_PER_RUN:]:
                    enqueue(t)
                print(f"budget: {len(targets)} due, taking {MAX_PER_RUN}, "
                      f"{len(targets) - MAX_PER_RUN} re-queued")
                targets = targets[:MAX_PER_RUN]
        elif a.transcript:
            targets = [Path(a.transcript)]
        else:
            ap.error("give a transcript path or --pending")
        try:
            # A hook has a 600s budget. Waiting for the lock is far better than
            # dropping the session, which is what failing fast used to do.
            from .scribe import LOCK_WAIT
            with single_run(wait_seconds=LOCK_WAIT if a.pending else 0):
                for t in targets:
                    try:
                        rec = run(t, dry=a.dry)
                    except RuntimeError as e:
                        print(json.dumps({"segment": t.name, "skipped": str(e)}))
                        continue
                    print(json.dumps(rec, ensure_ascii=False))
        except Busy as e:
            for t in targets:
                enqueue(t)
            print(f"busy — {e}; queued {len(targets)} for the next run")
            return 0
        if not targets:
            print("nothing pending")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
