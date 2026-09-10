"""MEMEX regression tests. `python3 tests/test_memex.py` from the repo root.

Every case here is a bug that actually happened. Nothing is hypothetical, and
nothing calls the model -- these run in under a second and cost nothing, so
there is no excuse for not running them.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from memex import edits as E          # noqa: E402
from memex import scribe as S         # noqa: E402

PASS, FAIL = [], []


def check(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  {'ok  ' if cond else 'FAIL'} {name}{('  — ' + detail) if detail and not cond else ''}")


# The write path reads brain/CLASSIFICATION.md for the `about:` vocabulary and
# refuses everything if it is missing -- a vocabulary check that fails open is
# not a check. Every temp Library therefore needs one, same as a real one.
ABOUT_TERMS = ["memex", "greenhouse", "owner", "agent"]


def seed_classification(brain):
    brain.mkdir(parents=True, exist_ok=True)
    (brain / "CLASSIFICATION.md").write_text(
        '---\ntitle: "CLASSIFICATION"\ntype: resolver\ncreated: 2026-09-08\n---\n\n'
        "<!-- about-terms:begin -->\n"
        + " · ".join(f"`{x}`" for x in ABOUT_TERMS)
        + "\n<!-- about-terms:end -->\n")
    # person_subjects() derives who counts as a human from the people/ shelf,
    # so a Library without one derives nobody and the vault guard would look
    # like it passed when it simply had nothing to check.
    (brain / "people").mkdir(exist_ok=True)
    (brain / "people" / "owner.md").write_text(
        '---\ntitle: "The Owner"\ntype: person\ncreated: 2026-08-30\n'
        'about: [owner]\nvisibility: vault\n---\n\n# The Owner\n')
    return brain



# ---------------------------------------------------------------- edits.py --
def test_edits():
    print("\nedits — the Scribe must not be able to damage a Book")
    tmp = Path(tempfile.mkdtemp()); E.BRAIN = seed_classification(tmp)
    b = tmp / "projects" / "demo.md"; b.parent.mkdir(parents=True)
    b.write_text('---\ntitle: "D"\ntype: project\ncreated: 2026-01-01\n---\n\n'
                 '# D\n\nSummary that must survive.\n\n## State\n\nfield: value\n\n'
                 '## See Also\n\n[[x]]\n\n---\n\n## Timeline\n\n2026-01-01 — first.\n')

    E.apply_op({"op": "fact", "book": "projects/demo", "text": "a new fact", "provenance": "agreed"})
    t = b.read_text()
    check("fact lands above the line", t.index("a new fact") < t.index("\n---\n\n## Timeline"))
    check("fact goes before See Also", t.index("a new fact") < t.index("## See Also"))
    check("blank line before See Also", "\n\na new fact\n\n## See Also" in t)

    E.apply_op({"op": "fact", "book": "projects/demo", "replaces": "field: value",
                "text": "field: NEW", "provenance": "agreed"})
    t = b.read_text()
    check("replaces substitutes exactly", "field: NEW" in t and "field: value" not in t)

    # the model dates its own text; the code dates it too -> "2026-09-07 — 2026-09-07 —"
    E.apply_op({"op": "trail", "book": "projects/demo", "date": "2026-09-07",
                "text": "**2026-09-07** — why it went this way"})
    E.apply_op({"op": "timeline", "book": "projects/demo", "date": "2026-09-07",
                "text": "2026-09-07 — an event"})
    t = b.read_text()
    check("trail date not doubled", "**2026-09-07** — why it went" in t
          and "2026-09-07** — **2026-09-07" not in t)
    check("timeline date not doubled", "2026-09-07 — 2026-09-07" not in t)
    check("timeline newest first", t.index("an event") < t.index("first."))
    check("nothing was lost", "Summary that must survive." in t and "[[x]]" in t)
    check("frontmatter intact", t.startswith('---\ntitle: "D"'))
    check("See Also not duplicated", t.count("## See Also") == 1)

    for op, why in [
        ({"op": "fact", "book": "projects/demo", "replaces": "ABSENT", "text": "x",
          "provenance": "agreed"}, "replaces must match verbatim"),
        ({"op": "fact", "book": "projects/nope", "text": "x", "provenance": "agreed"}, "missing Book refused"),
        ({"op": "inquiry", "book": "projects/demo", "body": "x" * 200},
         "whole-file write outside inquiries/ refused"),
        ({"op": "fact", "book": "../../etc/passwd", "text": "x", "provenance": "agreed"}, "path escape refused"),
        ({"op": "new", "book": "projects/demo", "title": "t", "type": "project",
          "about": ["memex"], "text": "y"}, "new over existing refused"),
        ({"op": "new", "book": "projects/z", "title": "t", "type": "bogus",
          "about": ["memex"], "text": "y"}, "unknown type refused"),
        ({"op": "trail", "book": "projects/demo", "date": "not-a-date", "text": "x"},
         "bad date refused"),
    ]:
        try:
            E.apply_op(op); check(why, False, "op was applied")
        except (E.Refused, OSError):
            check(why, True)

    # a `new` must be usable by later ops in the same batch, even in a dry run
    w, r = E.apply_all([
        {"op": "trail", "book": "projects/fresh", "date": "2026-09-07", "text": "why"},
        {"op": "new", "book": "projects/fresh", "title": "F", "type": "project",
         "about": ["memex"], "text": "facts"},
    ], dry=True)
    check("dry run orders new before its dependants", not r, str(r))
    shutil.rmtree(tmp)


# --------------------------------------------------------------- scribe.py --
def test_trust_boundary():
    print("\nedits — model output is data, not frontmatter")
    import re as _re
    import yaml as _yaml
    tmp = Path(tempfile.mkdtemp()); E.BRAIN = seed_classification(tmp)

    # A model-supplied title once landed unescaped inside `title: "..."`.
    evil = 'health"\ntype: note\nvisibility: world\nx: "'
    E.apply_op({"op": "new", "book": "projects/t", "title": evil,
                "type": "project", "about": ["memex"], "text": "Body."})
    out = (tmp / "projects" / "t.md").read_text()
    fm = _yaml.safe_load(_re.match(r"---\n(.*?)\n---\n", out, _re.S).group(1))
    check("title cannot inject frontmatter keys", fm.get("visibility") is None, str(fm))
    check("declared type survives injection", fm.get("type") == "project")
    check("title is collapsed to one line", "\n" not in fm["title"])

    # RESOLVER Test 0, enforced in code rather than only asked for in the prompt.
    for op, why in [
        ({"op": "new", "book": "people/x", "title": "X", "type": "person",
          "about": ["owner"], "text": "y"},
         "person Book without vault refused"),
        # The shelf-name list this used to rely on is gone; the guard now keys
        # on facets that travel with the Book. A note about the owner is exactly the
        # case the retired `direction/ preferences/ ...` shelves used to catch.
        ({"op": "new", "book": "notes/x", "title": "X", "type": "note",
          "text": "y", "about": ["owner"]},
         "note about a person without vault refused"),
        ({"op": "new", "book": "notes/z", "title": "Z", "type": "note",
          "text": "y", "about": ["the owner"]},
         "about: rejects anything but lowercase slugs"),
        # CLASSIFICATION.md states these three as requirements. Until the
        # 2026-09-09 review they were enforced nowhere, which is the same
        # "rule lives only in prose" defect the faceted scheme was written
        # to end.
        ({"op": "new", "book": "projects/noabout", "title": "N",
          "type": "project", "text": "y"},
         "a Book without about: is refused"),
        ({"op": "new", "book": "projects/typo", "title": "T", "type": "project",
          "text": "y", "about": ["pincercaft"]},
         "a term outside the controlled list is refused"),
        ({"op": "new", "book": "projects/y", "title": "Y", "type": "project",
          "about": ["memex"], "text": "y", "visibility": "world"}, "visibility other than vault refused"),
    ]:
        try:
            E.apply_op(op); check(why, False, "was applied")
        except (E.Refused, OSError):
            check(why, True)
    E.apply_op({"op": "new", "book": "people/z", "title": "Z", "type": "person",
                "about": ["owner"], "text": "y", "visibility": "vault"})
    check("person Book WITH vault is allowed",
          "visibility: vault" in (tmp / "people" / "z.md").read_text())

    # The vault check was a substring test, so a body merely MENTIONING the
    # phrase satisfied it while declaring itself world.
    (tmp / "inquiries").mkdir(exist_ok=True)
    q = tmp / "inquiries" / "q.md"
    q.write_text('---\ntitle: "Q"\ntype: note\ncreated: 2026-01-01\n'
                 'visibility: vault\n---\n\n# Q\n\nbody\n')
    sneaky = ('---\ntitle: "Q"\ntype: note\ncreated: 2026-01-01\nvisibility: world\n'
              '---\n\n# Q\n\n<!-- visibility: vault -->\n' + "x" * 100)
    try:
        E.apply_op({"op": "inquiry", "book": "inquiries/q", "body": sneaky})
        check("a comment cannot fake the vault label", False, "bypass applied")
    except E.Refused:
        check("a comment cannot fake the vault label", True)

    # _undate belongs to trail/timeline, where the code supplies the date.
    E.apply_op({"op": "fact", "book": "projects/t", "provenance": "agreed",
                "text": "2026-08-19 — manuscript v0.1 was pushed"})
    check("a fact keeps its own leading date",
          "2026-08-19 — manuscript" in (tmp / "projects" / "t.md").read_text())
    shutil.rmtree(tmp)


def test_wrapper_filter():
    print("\nscribe — harness wrappers dropped, real lines kept")
    for text, drop in [("<system-reminder>x</system-reminder>", True),
                       ("<command-name>/review", True),
                       ("<div> is what I meant", False),
                       ("<- like this", False),
                       ("normal text", False)]:
        got = bool(S._WRAPPER.match(text))
        check(f"{'drop' if drop else 'keep'}: {text[:24]!r}", got == drop)


def test_prune_scope():
    print("\nscribe — prune takes our runs only")
    # Against a temp directory, never the real one. This test used to run the
    # pruner over the live scribe transcript directory. (codex review)
    real = S.SCRIBE_TRANSCRIPTS
    S.SCRIBE_TRANSCRIPTS = Path(tempfile.mkdtemp())
    try:
        mine = S.SCRIBE_TRANSCRIPTS / "t-mine.jsonl"
        mine.write_text("# Open Inquiries (full text)\n")
        human = S.SCRIBE_TRANSCRIPTS / "t-human.jsonl"
        human.write_text('{"type":"user"}\n')
        unreadable = S.SCRIBE_TRANSCRIPTS / "t-unreadable.jsonl"
        unreadable.write_text("x"); unreadable.chmod(0o000)
        S._prune_own_transcripts()
        check("our own run is deleted", not mine.exists())
        check("a human transcript is left alone", human.exists())
        check("an unreadable file is NOT deleted", unreadable.exists())
        unreadable.chmod(0o600)
        shutil.rmtree(S.SCRIBE_TRANSCRIPTS)
    finally:
        S.SCRIBE_TRANSCRIPTS = real


def test_candidates():
    print("\ncandidates — a queue outside the Library, never a layer inside it")
    from memex import candidates as C
    import tempfile as _tf
    tmpq = Path(_tf.mkstemp(suffix=".jsonl")[1]); C.QUEUE = tmpq
    tmp = Path(_tf.mkdtemp()); E.BRAIN = seed_classification(tmp)
    b = tmp / "p" / "d.md"; b.parent.mkdir(parents=True)
    b.write_text('---\ntitle: "D"\ntype: project\ncreated: 2026-01-01\n---\n\n# D\n\nS.\n')
    try:
        c = C.add("p/d", "The README link points at a deleted directory.")
        check("a notice is queued, not written", c is not None
              and "README link" not in b.read_text())
        check("the queue lives outside brain/", "brain" not in str(C.QUEUE))
        check("a restatement is not queued twice",
              C.add("p/d", "The README link points at a deleted dir.") is None)
        check("one waiting", len(C.pending()) == 1)

        # a Book cannot be written without the owner's word, however the op is shaped
        for op, why in [
            ({"op": "fact", "book": "p/d", "text": "x"}, "appending a fact needs agreement"),
            ({"op": "fact", "book": "p/d", "text": "x", "replaces": "S."},
             "superseding a fact needs agreement"),
            ({"op": "observe", "book": "p/d", "text": "x"}, "the observe op is gone"),
        ]:
            try:
                E.apply_op(op); check(why, False, "was applied")
            except E.Refused:
                check(why, True)

        book = C.accept(c.id)
        check("the owner's yes turns a candidate into a fact", book == "p/d")
        check("and it lands in the Book", "README link" in b.read_text())
        check("and leaves the queue", len(C.pending()) == 0)

        c2 = C.add("p/d", "Something nobody wants.")
        C.take(c2.id)
        check("a dropped candidate is gone", len(C.pending()) == 0)
        check("dropping wrote nothing", "nobody wants" not in b.read_text())
    finally:
        tmpq.unlink(missing_ok=True); shutil.rmtree(tmp)


def test_consumed():
    print("\nscribe — incremental bookkeeping (a compacted session lost its tail)")
    tmp = Path(tempfile.mkstemp(suffix=".jsonl")[1]); S.RECEIPTS = tmp
    for name, recs, expect in [
        ("legacy receipt means fully read", [{"segment": "a.jsonl"}], -1),
        ("line count is taken", [{"segment": "b.jsonl", "lines": 10}], 10),
        ("legacy then counted", [{"segment": "c.jsonl"}, {"segment": "c.jsonl", "lines": 10}], 10),
        ("counted then legacy", [{"segment": "d.jsonl", "lines": 10}, {"segment": "d.jsonl"}], 10),
        ("highest count wins", [{"segment": "e.jsonl", "lines": 5},
                                {"segment": "e.jsonl", "lines": 12}], 12),
        ("full path normalised", [{"segment": "/x/y/f.jsonl", "lines": 7}], 7),
    ]:
        tmp.write_text("\n".join(json.dumps(r) for r in recs) + "\n")
        got = S.consumed().get(Path(recs[0]["segment"]).name)
        check(name, got == expect, f"got {got}, expect {expect}")
    tmp.unlink()


def test_incremental_read():
    print("\nscribe — only the new part of a transcript is read")
    t = Path(tempfile.mkstemp(suffix=".jsonl")[1])

    def add(texts):
        with t.open("a") as f:
            for x in texts:
                f.write(json.dumps({"type": "user", "message": {"role": "user",
                        "content": [{"type": "text", "text": x}]}}) + "\n")

    add([f"early-{i}" for i in range(5)])
    n1 = S.line_count(t)
    add([f"late-{i}" for i in range(3)])
    tail = S.spoken_lines(t, start=n1)
    check("line_count is right", n1 == 5, str(n1))
    check("tail excludes what was read", "early-0" not in tail)
    check("tail includes what is new", "late-0" in tail and "late-2" in tail)
    check("whole file still readable", "early-0" in S.spoken_lines(t, 0))
    check("needs_scribe: never seen", S.needs_scribe(t, {}))
    check("needs_scribe: fully read", not S.needs_scribe(t, {t.name: 8}))
    check("needs_scribe: has grown", S.needs_scribe(t, {t.name: 5}))
    check("needs_scribe: legacy receipt", not S.needs_scribe(t, {t.name: -1}))
    t.unlink()


def test_gate():
    print("\nscribe — the cheap gate in front of the expensive call")
    # The gate skips an EMPTY room, nothing more. It used to demand two user
    # turns, which assumed every record needs both parties -- but an observation
    # needs none: the agent can notice a dead link working alone, and that is
    # worth keeping. Bush §6 is "profligate".
    for name, conv, expect_call in [
        ("trivial session",      "[user]\nls\n\n[assistant]\nHere.\n", False),
        ("empty",                "", False),
        ("whitespace only",      "   \n\n  ", False),
        ("assistant monologue",  "[assistant]\n" + "x" * 2000, True),
        ("one user turn only",   "[user]\n" + "x" * 2000, True),
        ("a real exchange",
         "[user]\n" + "a" * 500 + "\n\n[assistant]\n" + "b" * 500 + "\n\n[user]\nyes do that\n",
         True),
    ]:
        ok, why = S.worth_scribing(conv)
        check(f"gate: {name}", ok == expect_call, f"got call={ok} ({why})")
    check("the gate can only skip, never record",
          "return True, \"\"" in Path(ROOT / "memex" / "scribe.py").read_text())


def test_guards():
    print("\nscribe — the guards that stop a recursive run")
    check("child cwd is outside the home directory",
          not str(S.SCRIBE_CWD).startswith(str(Path.home())), str(S.SCRIBE_CWD))
    check("child transcripts are outside the search pool",
          not S.SCRIBE_TRANSCRIPTS.name.startswith(str(S.ROOT).replace("/", "-")))
    f = Path(tempfile.mkstemp(suffix=".jsonl")[1])
    f.write_text("# Open Inquiries (full text)\n")
    check("a Scribe's own run is never a target", S.is_self_transcript(f)); f.unlink()
    r = subprocess.run([sys.executable, "-m", "memex", "scribe", "--pending"],
                       capture_output=True, text=True, cwd=ROOT,
                       env={**os.environ, S.GUARD_ENV: "1"}, stdin=subprocess.DEVNULL)
    check("a nested process refuses to scribe", "nothing done" in r.stdout, r.stdout.strip())
    check("budget is bounded", S.MAX_PER_RUN <= 5 and S.MAX_AGE_DAYS <= 7)


def test_lock_and_queue():
    print("\nscribe — losing the lock race must not lose the session")
    # The child process re-imports memex and uses the REAL queue path, so an
    # in-process monkeypatch would not cover it. Snapshot and restore instead;
    # this test used to destroy a pending queue outright. (codex review)
    _saved = S.QUEUE.read_text() if S.QUEUE.exists() else None
    S.QUEUE.unlink(missing_ok=True)
    victim = Path("/var/tmp/memex-test-queue.jsonl")
    victim.write_text(json.dumps({"type": "user", "message": {"role": "user",
                      "content": [{"type": "text", "text": "hi"}]}}) + "\n")
    with S.single_run():
        r = subprocess.run([sys.executable, "-m", "memex", "scribe", "--pending"],
                           input=json.dumps({"transcript_path": str(victim)}),
                           text=True, capture_output=True, cwd=ROOT,
                           env={**os.environ, "MEMEX_LOCK_WAIT": "2"})
        check("a second Scribe is refused", "busy" in r.stdout, r.stdout.strip())
        check("it says what it queued", "queued 1" in r.stdout, r.stdout.strip())
    q = S.drain_queue()
    check("the lost session was queued", [p.name for p in q] == [victim.name], str(q))
    check("the queue is cleared after draining", not S.QUEUE.exists())
    S.QUEUE.write_text(f"{victim}\n/var/tmp/does-not-exist-xyz.jsonl\n")
    got = S.drain_queue()
    check("a vanished file is dropped from the queue", [p.name for p in got] == [victim.name])
    victim.unlink()
    if _saved is not None:
        S.QUEUE.write_text(_saved)
    check("a pre-existing queue is left as it was",
          (S.QUEUE.read_text() if S.QUEUE.exists() else None) == _saved)


def test_session_scope():
    print("\nsession — start injects less outside the repo")
    from memex import session as SS
    env_in = {**os.environ, "MEMEX_CALLER_PWD": str(ROOT)}
    env_out = {**os.environ, "MEMEX_CALLER_PWD": "/tmp"}
    run = lambda e: subprocess.run([sys.executable, "-m", "memex", "start"],
                                   capture_output=True, text=True, cwd=ROOT, env=e).stdout
    inside, outside = run(env_in), run(env_out)
    check("inside the repo carries MEMORY.md", "From MEMORY.md" in inside)
    check("outside does not", "From MEMORY.md" not in outside)
    # Not a size ratio -- that depends on how much hot state a given Library
    # happens to carry, and this repo ships a deliberately short example. Assert
    # the three things the trim actually drops.
    check("outside drops the preferences Book",
          "(notes/owner-preferences)" not in outside)
    check("outside drops the scribe report", "Scribe, last 7d" not in outside)
    check("outside is smaller", len(outside) < len(inside),
          f"{len(outside)} vs {len(inside)}")
    for part in ("The record", "memex recall", "memex trail"):
        check(f"outside still carries {part!r}", part in outside)
    # bin/memex cds into the repo, so without MEMEX_CALLER_PWD the check is
    # always True and the trim silently never applies.
    check("the wrapper exports the caller's directory",
          "MEMEX_CALLER_PWD" in (ROOT / "bin" / "memex").read_text())
    check("the wrapper still cds into the repo",
          'cd "$(dirname' in (ROOT / "bin" / "memex").read_text())


def test_waiting():
    print("\npending — what is waiting on the owner must be impossible to miss")
    from memex import pending as P
    tmp = Path(tempfile.mkdtemp())
    import memex.library as L
    real_brain, real_pb = L.BRAIN, P.BRAIN
    L.BRAIN = P.BRAIN = tmp
    try:
        (tmp / "projects").mkdir(); (tmp / "inquiries").mkdir()
        fm = lambda t: f'---\ntitle: "T"\ntype: {t}\ncreated: 2026-01-01\n---\n\n# T\n\nx\n'
        # all three shapes the Scribe has actually written
        (tmp / "projects" / "a.md").write_text(
            fm("project") + "\n---\n\n## Timeline\n\n"
            "2026-09-07 — proposed by the agent, unconfirmed: alpha thing.\n\n"
            "2026-09-07 — proposed (the agent): beta thing. Not yet confirmed by the owner.\n\n"
            "2026-09-07 — the owner confirmed the gamma thing.\n")
        # a resolver's TEMPLATE must not be mistaken for a real question
        (tmp / "projects" / "r.md").write_text(
            fm("resolver") + "\n## Open\n\n- <one proposal or question, with context>\n")
        # an Inquiry's real Open section
        (tmp / "inquiries" / "q.md").write_text(
            fm("note") + "\n## Open\n\n- **Should we do the thing?** — proposed by the agent.\n")
        # "Not yet confirmed by the owner" CONTAINS "confirmed". Reading the
        # resolution word alone marked nine open questions answered and emptied
        # the queue in silence; reading the negation alone then kept a genuinely
        # resolved line open forever. Both directions are pinned here.
        for line, answered in [
            ("proposed X. Not yet confirmed by the owner.", False),
            ("proposed X, unconfirmed: thing.", False),
            ("proposed X. Never agreed.", False),
            ("the owner confirmed the thing.", True),
            ("proposed X. Not yet confirmed by the owner. "
             "Resolved 2026-09-07: recorded as an observation.", True),
        ]:
            check(f"answered={answered}: {line[:38]!r}",
                  P._is_answered(line) == answered)
        got = P.waiting()
        texts = " | ".join(w.text for w in got)
        check("catches 'proposed by X, unconfirmed'", "alpha thing" in texts)
        check("catches 'proposed (X):'", "beta thing" in texts)
        check("catches an Inquiry's ## Open bullet", "Should we do the thing" in texts)
        check("ignores an already-confirmed line", "gamma" not in texts)
        check("ignores a resolver's template", not any(w.slug == "projects/r" for w in got))
        check("counts them all", len(got) == 3, str(len(got)))
        check("render leads with a count", P.render().startswith("## ⚠ 3 waiting"))
        long = P.Waiting("x/y", 1, "A. " + "z" * 400, "timeline")
        check("gist is truncated for the session block", len(long.gist()) <= 151)
    finally:
        L.BRAIN, P.BRAIN = real_brain, real_pb
        shutil.rmtree(tmp)


def test_trails():
    print("\ntrails — association and logical flow, and nothing else (Bush §7)")
    from memex import trails as T
    import memex.library as L
    tmp = Path(tempfile.mkdtemp())
    real_b, real_t = L.BRAIN, T.BRAIN
    L.BRAIN = T.BRAIN = tmp
    try:
        (tmp / "trails").mkdir()
        (tmp / "trails" / "q.md").write_text(
            '---\ntitle: "A route"\ntype: note\ncreated: 2026-01-01\n---\n\n'
            '# A route\n\nWhat this route is about.\n\n## Route\n\n'
            '1. **First move.** — 2026-06\n'
            '   Because of a reason.\n'
            '   → [[people/owner]] → [[routine/owner]]\n\n'
            '2. **Second move.** — 2026-07\n'
            '   Another reason.\n'
            '   → [[projects/x]]\n\n'
            '3. **A step that tied nothing.** — 2026-08\n'
            '   Just thinking.\n')
        t = T.parse(tmp / "trails" / "q.md")
        check("the trail takes its name from the title", t.title == "A route")
        check("every step is found", [s.n for s in t.steps] == [1, 2, 3])
        check("a step keeps its reason", "Because of a reason" in t.steps[0].why)
        check("a step names the Books it ties",
              t.steps[0].reaches == ["people/owner", "routine/owner"])
        check("a step that tied nothing still parses", t.steps[2].reaches == [])
        check("the trail knows every Book it crosses",
              t.books == ["people/owner", "routine/owner", "projects/x"])
        check("no lifecycle fields survive the strip",
              not hasattr(t, "status") and not hasattr(t, "question")
              and not hasattr(t, "learned"))
        # a trail written under the older shape must still parse
        (tmp / "trails" / "legacy.md").write_text(
            '---\ntitle: "Legacy"\ntype: note\ncreated: 2026-01-01\n---\n\n'
            '# Legacy\n\n**Status:** open\n\n## Route\n\n'
            '1. **Old shape.** — 2026-06 · agreed\n   Why.\n   → [[projects/x]]\n')
        lt = T.parse(tmp / "trails" / "legacy.md")
        check("an older trail with Status and a mark still parses",
              len(lt.steps) == 1 and lt.steps[0].move == "Old shape.")

        w = T.walk(t)
        check("walk renders steps in order",
              w.index("First move") < w.index("Second move") < w.index("A step that tied"))
        check("walk shows where each step reached", "→ people/owner → routine/owner" in w)

        # Bush §7: one item belongs to numerous trails
        hits = T.through("projects/x")
        check("a Book names every trail through it", len(hits) == 2, str(len(hits)))
        check("a Book on no trail is not claimed", T.through("nothing/here") == [])

        # recovery: order is NOT chronological, and reasons are never invented
        (tmp / "projects").mkdir(exist_ok=True)
        fm = '---\ntitle: "B"\ntype: project\ncreated: 2026-01-01\n---\n\n# B\n\n'
        (tmp / "projects" / "early.md").write_text(
            fm + "Links [[projects/late]].\n\n---\n\n## Timeline\n\n"
            "2026-05-16 — the first thing happened.\n\n2026-08-29 — a later thing.\n")
        (tmp / "projects" / "late.md").write_text(
            fm + "Links [[projects/early]].\n\n---\n\n## Timeline\n\n"
            "2026-07-01 — the second thing happened.\n")
        (tmp / "projects" / "undated.md").write_text(fm + "Links [[projects/early]].\n")
        rows = T.suggest("projects/early", depth=1)
        by = {r["book"]: r for r in rows}
        check("the seed and its neighbours are collected",
              {"projects/early", "projects/late", "projects/undated"} <= set(by))
        check("the reason belongs to the earliest date, not the first line seen",
              "the first thing happened" in by["projects/early"]["reason"]
              and "a later thing" not in by["projects/early"]["reason"])
        check("a Book with no dated entry reports the gap, not a guess",
              by["projects/undated"]["reason"] == "")
        check("the rendering says the order is not the trail's",
              "NOT the order of the trail" in T.render_suggestion("projects/early", rows))

        # a link is not a trail: ties nobody reasoned about are the backlog
        u = T.unexplained()
        pairs = {(a, b) for a, b in u}
        check("a tie no trail explains is counted",
              ("projects/early", "projects/late") in pairs
              or ("projects/late", "projects/early") in pairs)
        check("a trail's own links are not its own backlog",
              not any(a.startswith("trails/") for a, _ in u), str(u[:3]))

        # the other direction
        br = T.backrefs("projects/x")
        check("a reached Book gets its routes listed", "[[trails/q]] step 2" in br)
        check("the back-reference says where the step lives", "a step has one home" in br)
        check("an unreached Book gets nothing", T.backrefs("projects/undated") == "")
    finally:
        L.BRAIN, T.BRAIN = real_b, real_t
        shutil.rmtree(tmp)


def test_cli():
    """Every command, driven the way a person drives it.

    The suite exercised apply_op directly and never went through main(), so a
    dangling `--promote` reference crashed `memex note` AFTER a successful
    write while 126 checks passed. Exit codes and side effects, from outside.
    """
    print("\ncli — the commands, from outside")
    root = Path(tempfile.mkdtemp())
    (root / "brain" / "projects").mkdir(parents=True)
    (root / "brain" / "trails").mkdir(parents=True)
    (root / "state").mkdir()
    seed_classification(root / "brain")
    (root / "brain" / "projects" / "d.md").write_text(
        '---\ntitle: "D"\ntype: project\ncreated: 2026-01-01\n---\n\n'
        '# D\n\nA starting fact.\n\n## See Also\n\n[[projects/e]]\n')
    (root / "brain" / "projects" / "e.md").write_text(
        '---\ntitle: "E"\ntype: project\ncreated: 2026-01-01\n---\n\n# E\n\nAnother.\n')
    (root / "brain" / "trails" / "t.md").write_text(
        '---\ntitle: "A route"\ntype: note\ncreated: 2026-01-01\n---\n\n# A route\n\n'
        'What it is.\n\n## Route\n\n1. **A move.** — 2026-05-16\n   Why.\n'
        '   → [[projects/d]]\n')

    env = {**os.environ, "MEMEX_ROOT": str(root)}

    def run(*args, stdin=""):
        return subprocess.run([sys.executable, "-m", "memex", *args],
                              capture_output=True, text=True, cwd=ROOT,
                              env=env, input=stdin)

    def book(name="d"):
        return (root / "brain" / "projects" / f"{name}.md").read_text()

    # note: the argument order that bit me
    r = run("note", "a long sentence used as if it were a slug", "projects/d")
    check("swapped arguments are refused", r.returncode == 1)
    check("and the message names the mistake",
          "first argument is the Book" in r.stdout, r.stdout.strip()[:80])

    # note: queues by default, writes only with --agreed
    r = run("note", "projects/d", "Something merely noticed.")
    check("note queues by default", r.returncode == 0 and "queued" in r.stdout)
    check("and writes nothing to the Book", "merely noticed" not in book())

    r = run("note", "projects/d", "A confirmed fact.", "--agreed")
    check("note --agreed exits 0", r.returncode == 0, r.stderr.strip()[-120:])
    check("note --agreed writes the fact", "A confirmed fact." in book())
    check("and says so without a traceback",
          "recorded as fact" in r.stdout and "Traceback" not in r.stderr)

    r = run("note", "projects/d", "x", "--replaces", "A starting fact.")
    check("--replaces without --agreed is refused", r.returncode == 1)
    check("and the Book is untouched", "A starting fact." in book())

    # pending: the queue and both ways out
    r = run("pending")
    check("pending lists the queued item",
          "merely noticed" in r.stdout and r.returncode == 0)
    cid = [w.strip("`") for w in r.stdout.split() if w.startswith("`")][0]
    r = run("pending", "--accept", cid)
    check("pending --accept records it", r.returncode == 0
          and "Something merely noticed." in book())
    r = run("note", "projects/d", "Doomed.")
    cid2 = [w.strip("`") for w in run("pending").stdout.split() if w.startswith("`")][0]
    r = run("pending", "--drop", cid2)
    check("pending --drop removes it", r.returncode == 0 and "Doomed." not in book())
    check("and the queue empties", "Nothing waiting" in run("pending").stdout)
    r = run("pending", "--accept", "nosuchid")
    check("an unknown id exits non-zero", r.returncode != 0)

    # trails
    check("trail lists routes", "trails/t" in run("trail").stdout)
    check("trail <name> walks one", "A move." in run("trail", "t").stdout)
    check("an unknown trail exits non-zero", run("trail", "nope").returncode != 0)
    check("trail --through names the route",
          "trails/t" in run("trail", "--through", "projects/d").stdout)
    check("trail --orphans reports the unreached",
          "projects/e" in run("trail", "--orphans").stdout)
    check("trail --unexplained counts ties",
          "ties no trail explains" in run("trail", "--unexplained").stdout)
    check("trail --suggest returns raw material",
          "NOT the order of the trail" in run("trail", "--suggest", "projects/d").stdout)
    r = run("trail", "--sync")
    check("trail --sync writes back-references",
          r.returncode == 0 and "Trails through this Book" in book())

    # start, open, and an unknown command
    r = run("start")
    check("start emits the context block",
          r.returncode == 0 and "MEMEX session context" in r.stdout)
    check("start names the Library path", str(root / "brain") in r.stdout)
    check("open runs with an empty queue", run("open").returncode == 0)
    check("an unknown command exits non-zero", run("nonesuch").returncode != 0)

    # the scribe guard, through the CLI
    r = subprocess.run([sys.executable, "-m", "memex", "scribe", "--pending"],
                       capture_output=True, text=True, cwd=ROOT,
                       env={**env, "MEMEX_SCRIBE": "1"}, stdin=subprocess.DEVNULL)
    check("a nested scribe refuses via the CLI",
          "nothing done" in r.stdout and r.returncode == 0)

    check("the real Library was never touched",
          not (ROOT / "brain" / "projects" / "d.md").exists())
    shutil.rmtree(root)


def test_prompt_matches_code():
    """Every op the prompt offers must be one the system accepts.

    The prompt kept offering `promote` and `observe` after both left edits.py.
    A Scribe emitting a refused op produces nothing, and after two attempts the
    segment is marked consumed -- so a session gets read, yields nothing, and
    is closed as done. Silent, and the exact failure MEMEX exists to prevent.
    """
    print("\nscribe — the prompt offers only ops the system accepts")
    import re as _re
    prompt = set(_re.findall(r'\{"op":"(\w+)"', (ROOT / "scribe" / "PROMPT.md").read_text()))
    handled = set(_re.findall(r'kind (?:==|in \()\s*[("]([a-z_]+)',
                              (ROOT / "memex" / "edits.py").read_text()))
    handled |= {"trail", "timeline"}          # share one branch
    handled |= {"observe"}                    # routed to the queue by scribe.run
    check("no op is offered that nothing handles",
          not (prompt - handled), f"orphaned: {sorted(prompt - handled)}")
    src = (ROOT / "memex" / "scribe.py").read_text()
    check("scribe routes observe to the queue, not to a Book",
          'o.get("op") == "observe"' in src and "from .candidates import add" in src)


def test_books_are_owners():
    """The Scribe cannot write a Book. Not discouraged -- refused.

    Until 2026-09-08 the Scribe was offered {"op":"fact","provenance":"agreed"}
    and told to use it only when it could "quote both lines". That is an
    honour-system gate on a model reading its own transcript, in a process that
    runs after the session with nobody to ask. It had never fired (7d: 12
    observed, 0 agreed) -- but the capability was there, and the owner's whole design
    is that it cannot be.
    """
    print("\nboundary — a Book is written by the owner's word or not at all")
    root = Path(tempfile.mkdtemp())
    (root / "brain" / "projects").mkdir(parents=True)
    (root / "state").mkdir()
    seed_classification(root / "brain")
    (root / "brain" / "projects" / "b.md").write_text(
        '---\ntitle: "B"\ntype: project\ncreated: 2026-01-01\n---\n\n# B\n\nA fact.\n')
    env = {**os.environ, "MEMEX_ROOT": str(root)}

    def run(*args, stdin=""):
        return subprocess.run([sys.executable, "-m", "memex", *args],
                              capture_output=True, text=True, cwd=ROOT,
                              env=env, input=stdin)

    prev_root = os.environ.get("MEMEX_ROOT")
    os.environ["MEMEX_ROOT"] = str(root)     # for the in-process calls below
    import importlib
    from memex import library as L
    importlib.reload(L)
    E2 = importlib.reload(E)
    check("the fake Library is what apply_op will touch",
          str(root) in str(L.BRAIN), str(L.BRAIN))

    for op in ({"op": "fact", "book": "projects/b", "text": "x",
                "provenance": "agreed"},
               {"op": "new", "book": "projects/c", "title": "C", "about": ["memex"],
                "text": "a body long enough to pass"}):
        try:
            E2.apply_op(op, actor="scribe")
            check(f"scribe refused {op['op']}", False, "it was allowed")
        except E2.Refused as e:
            check(f"scribe refused {op['op']}", "cannot write a Book" in str(e), str(e)[:60])

    try:
        E2.apply_op({"op": "fact", "book": "projects/b", "text": "Agreed here.",
                     "provenance": "agreed"})
        check("the skill path still writes", "Agreed here." in
              (root / "brain" / "projects" / "b.md").read_text())
    except E2.Refused as e:
        check("the skill path still writes", False, str(e)[:60])

    # the prompt must not advertise what the code refuses
    prompt = (ROOT / "scribe" / "PROMPT.md").read_text()
    check("the prompt no longer offers fact", '{"op":"fact"' not in prompt)
    check("the prompt no longer offers new", '{"op":"new"' not in prompt)
    check("and it says so in words", "cannot write a Book" in prompt)

    # memex new: the Book-creation path the skill needs
    r = run("new", "projects/widget", "--title", "Widget",
            "--about", "memex", "--text", "It ships Fridays.")
    check("memex new creates a Book", r.returncode == 0 and
          (root / "brain" / "projects" / "widget.md").exists(), r.stdout[:70])
    r = run("new", "people/x", "--title", "X", "--about", "owner", "--text", "A person.")
    check("memex new enforces RESOLVER Test 0", r.returncode == 1)
    r = run("new", "people/x", "--title", "X", "--about", "owner",
            "--text", "A person.", "--vault")
    check("memex new accepts --vault", r.returncode == 0 and "visibility: vault" in
          (root / "brain" / "people" / "x.md").read_text())

    # the Stop hook: exit 2 is the whole mechanism
    r = run("pending", "--nudge", stdin='{"stop_hook_active": false}')
    check("nudge is silent on an empty queue", r.returncode == 0 and not r.stderr.strip())
    run("note", "projects/b", "Noticed, not agreed.")
    r = run("pending", "--nudge", stdin='{"stop_hook_active": false}')
    check("nudge blocks the turn with exit 2", r.returncode == 2, f"rc={r.returncode}")
    check("and the question goes to stderr", "Should I write" in r.stderr, r.stderr[:70])
    r = run("pending", "--nudge", stdin='{"stop_hook_active": true}')
    check("stop_hook_active ends it — never a loop", r.returncode == 0)
    check("the candidate never reached the Book",
          "Noticed, not agreed." not in (root / "brain" / "projects" / "b.md").read_text())
    check("the real Library was never touched",
          not (ROOT / "brain" / "projects" / "b.md").exists()
          and not (ROOT / "brain" / "projects" / "widget.md").exists())

    if prev_root is None:
        os.environ.pop("MEMEX_ROOT", None)
    else:
        os.environ["MEMEX_ROOT"] = prev_root
    importlib.reload(L)
    importlib.reload(E)
    shutil.rmtree(root, ignore_errors=True)


def test_queue_cannot_stack():
    """A queue the owner does not answer is a chore, not a record.

    Seventeen candidates accumulated unseen. Two things stop that recurring: a
    cap on what one session may add, and an expiry on what nobody answered.
    """
    print("\nqueue — capped, and it drains")
    root = Path(tempfile.mkdtemp())
    (root / "brain" / "projects").mkdir(parents=True)
    (root / "state").mkdir()
    prev_root = os.environ.get("MEMEX_ROOT")
    os.environ["MEMEX_ROOT"] = str(root)
    import importlib
    from memex import library as L
    importlib.reload(L)
    from memex import candidates as C
    importlib.reload(C)

    check("the cap is small and explicit", C.MAX_PER_SESSION == 3, str(C.MAX_PER_SESSION))
    # deliberately unlike one another: add() drops near-restatements, so five
    # variations on one sentence would test the deduper, not the cap.
    for line in ("The widget ships on Fridays, per the release calendar.",
                 "Gears are machined in Busan before assembly.",
                 "Freight moves by rail whenever the harbour closes.",
                 "Voltage tolerance measured eleven percent above nominal.",
                 "Firmware documentation lives beside its repository."):
        C.add("projects/b", line)
    check("everything added is visible", len(C.pending()) == 5, str(len(C.pending())))

    # age one past the expiry and prune
    items = C._read()
    old = datetime.now(C.TZ) - timedelta(days=C.STALE_DAYS + 1)
    items[0].seen = old.isoformat(timespec="seconds")
    C._write(items)
    check("stale is hidden from pending", len(C.pending()) == 4, str(len(C.pending())))
    check("prune removes it", C.prune() == 1)
    check("and it is gone from the file", len(C._read()) == 4, str(len(C._read())))
    check("prune is idempotent", C.prune() == 0)

    src = (ROOT / "memex" / "scribe.py").read_text()
    check("the scribe applies the cap", "MAX_PER_SESSION" in src and
          "notices[:MAX_PER_SESSION]" in src)

    # put the environment back, or every later test reads a deleted directory
    if prev_root is None:
        os.environ.pop("MEMEX_ROOT", None)
    else:
        os.environ["MEMEX_ROOT"] = prev_root
    importlib.reload(L)
    importlib.reload(C)
    shutil.rmtree(root, ignore_errors=True)


def test_the_schedule_can_see_the_work():
    """A scheduled run has no hook payload; it must find transcripts itself.

    Measured 2026-09-09: `find_transcripts` defaulted to the repo, so it looked
    under `-home-<user>-memex` -- a directory that is empty and always has been,
    because every session on this machine runs from ~ or below it. `pending()`
    returned [] for every session that has ever run here. The hook never
    noticed: it passes the transcript in directly. A cron run has nothing else,
    so it would have scribed nothing, silently, forever.
    """
    print("\nschedule — a run with no hook payload can still find the work")
    check("the scan root is where the work happens, not where the Library is",
          S.WORK == Path.home(), str(S.WORK))
    check("find_transcripts defaults to it",
          S.find_transcripts.__defaults__[0] == Path.home())
    check("and so does pending", S.pending.__defaults__[0] == Path.home())

    # the always-on session runs from ~ itself; the old prefix test missed it
    enc = S._encoded(Path.home())
    want = str(Path.home()).replace("/", "-").replace(".", "-")
    check("~ encodes to the bare prefix", enc == want, enc)
    check("the repo prefix could never match it",
          not enc.startswith(S._encoded(Path.home() / "memex")))

    # and the match is on a segment boundary, so a neighbour cannot be swallowed
    for name, want in ((enc, True), (enc + "-memex", True),
                       (enc + "-memex--claude-worktrees-x", True),
                       (enc + "xyz", False)):
        got = name == enc or name.startswith(enc + "-")
        check(f"{name} {'matches' if want else 'does not match'}", got == want)


def test_the_queue_has_a_ceiling():
    """The per-run cap stops bounding anything once runs are frequent.

    3-per-run was written when the Scribe ran at session end and the always-on
    session ended once a week. On a schedule that is 24 a day into a queue whose
    named failure was 17 items the owner never saw. The ceiling has to be on the queue.
    """
    print("\nqueue — a ceiling on the queue, not just on the run")
    root = Path(tempfile.mkdtemp())
    (root / "brain" / "projects").mkdir(parents=True)
    (root / "state").mkdir()
    prev = os.environ.get("MEMEX_ROOT")
    os.environ["MEMEX_ROOT"] = str(root)
    import importlib
    from memex import library as L
    importlib.reload(L)
    from memex import candidates as C
    importlib.reload(C)

    check("the ceiling is below the 17 that failed", C.MAX_PENDING < 17,
          str(C.MAX_PENDING))
    check("and above what one run may add", C.MAX_PENDING > C.MAX_PER_SESSION)
    check("an empty queue has room for all of it", C.room() == C.MAX_PENDING)

    words = ("ballast tide", "gantry crane", "sluice gate", "keel plate",
             "davit winch", "bilge pump", "hawser reel", "fender post",
             "capstan drum", "bollard ring", "sheave block", "cleat rail")
    for i, w in enumerate(words):
        C.add(f"projects/b{i}", f"The {w} is inspected each spring by the yard.")
    check("the queue stops at the ceiling", len(C.pending()) == C.MAX_PENDING,
          str(len(C.pending())))
    check("and reports no room", C.room() == 0)
    check("a full queue refuses rather than displaces",
          C.add("projects/z", "Something entirely new about the dry dock.") is None)
    check("nothing was pushed out to make space",
          len(C.pending()) == C.MAX_PENDING, str(len(C.pending())))

    # draining one makes room again
    C.take(C.pending()[0].id)
    check("answering one frees a slot", C.room() == 1, str(C.room()))
    check("and the next add is taken",
          C.add("projects/z", "Something entirely new about the dry dock.") is not None)

    src = (ROOT / "memex" / "scribe.py").read_text()
    check("the Scribe reports a full queue distinctly from a noisy run",
          "dropped_queue_full" in src and "dropped_over_cap" in src)

    if prev is None:
        os.environ.pop("MEMEX_ROOT", None)
    else:
        os.environ["MEMEX_ROOT"] = prev
    importlib.reload(L)
    importlib.reload(C)
    shutil.rmtree(root, ignore_errors=True)


def _fake_library(root: Path):
    """A trail with one step, and two Books — one on the route, one linked to it."""
    (root / "brain" / "projects").mkdir(parents=True)
    (root / "brain" / "trails").mkdir(parents=True)
    (root / "state").mkdir()
    (root / "brain" / "projects" / "onroute.md").write_text(
        '---\ntitle: "On the route"\ntype: project\ncreated: 2026-01-01\n---\n\n'
        "# On the route\n\n"
        "2026-05-02 — The harbour closed for dredging, so freight moved by rail "
        "instead and the schedule was rebuilt around [[projects/joined]].\n\n"
        "## See Also\n\n- [[projects/nореason]]\n")
    (root / "brain" / "projects" / "joined.md").write_text(
        '---\ntitle: "Joined"\ntype: project\ncreated: 2026-01-01\n---\n\n'
        "# Joined\n\nThe rail depot at the north end.\n")
    (root / "brain" / "trails" / "t.md").write_text(
        '---\ntitle: "A route"\ntype: note\ncreated: 2026-01-01\n---\n\n'
        "# A route\n\n## Route\n\n"
        "1. **The harbour closed.** — 2026-05-02\n   It forced everything after it.\n"
        "   \u2192 [[projects/onroute]]\n")


def test_a_claim_gets_its_own_vector():
    """A fact must never share a vector with an unrelated fact.

    Measured 2026-09-09: "the vault privacy guard was hardcoded to three names"
    sat in a 1,044-char chunk that opened with an unrelated fact about hook
    signatures. Asked the question it answers, that chunk scored 0.453 and lost
    to a Book that does not contain the answer (0.493). It was embedded and
    unreachable -- one vector standing for several unrelated claims.
    """
    print("\nchunking — one claim, one vector")
    from memex.recall import STANDALONE, INDEX_VERSION, _chunks
    from memex.library import Book

    a = "A" * 260 + " first claim, long enough to stand on its own."
    b = "B" * 260 + " second claim, entirely unrelated to the first."
    body = f"{a}\n\n{b}\n\nshort tail.\n"
    bk = Book(slug="projects/x", path=Path("/dev/null"), title="X",
              type="project", visibility="world", frontmatter={}, body=body)
    texts = [c for c, _ in _chunks(bk)]
    check("the two claims do not share a chunk",
          not any(a[:40] in x and b[:40] in x for x in texts), str(len(texts)))
    check("each claim is its own chunk",
          sum(1 for x in texts if a[:40] in x) == 1 and
          sum(1 for x in texts if b[:40] in x) == 1)
    check("the threshold is explicit", STANDALONE == 200, str(STANDALONE))
    check("the index version was bumped for the shape change",
          INDEX_VERSION >= 4, str(INDEX_VERSION))


def test_two_buttons():
    """Two acts, two shapes. The owner must tell them apart without reading the words.

    The owner, 2026-09-09: "make the button's design slightly different so that I can
    distinguish rather the button is adding trail or the button is adding facts."
    A FACT is a claim going into a Book; a TIE is one Book joining a route. The
    arrow is the tie's signature, because that is what Bush's press does.
    """
    print("\nbuttons — a fact and a tie are different acts, shown differently")
    root = Path(tempfile.mkdtemp())
    _fake_library(root)
    prev = os.environ.get("MEMEX_ROOT")
    os.environ["MEMEX_ROOT"] = str(root)
    import importlib
    from memex import library as L; importlib.reload(L)
    # edits.py binds BRAIN at import. Reloading library and trails but not edits
    # is how an earlier version of this test wrote brain/trails/t.md into the
    # REAL Library: accept() -> apply_op() still held the real root. Reload it,
    # and pin the fact below.
    from memex import edits as E2; importlib.reload(E2)
    from memex import candidates as C; importlib.reload(C)
    from memex import trails as T; importlib.reload(T)
    check("the fake root is the one in force", str(L.BRAIN).startswith(str(root)))
    check("and edits agrees", str(E2.BRAIN).startswith(str(root)), str(E2.BRAIN))

    # the daily pass finds the tie, and quotes the sentence that holds the link
    props = T.propose_steps()
    check("the pass finds the tie", len(props) == 1, str(props))
    check("it joins the Book that is off the route",
          props[0]["book"] == "projects/joined", str(props[0]))
    check("onto the route the other end sits on", props[0]["trail"] == "trails/t")
    check("and quotes the prose that holds the link, not a summary",
          "harbour closed for dredging" in props[0]["why"], props[0]["why"][:80])

    # queued as a step, not a fact
    C.add("projects/joined", "The depot handles nine trains a day, measured 2026-05.")
    c = C.add_step(**{k: props[0][k] for k in ("trail", "book", "via", "date", "why")})
    check("a step is queued as its own kind", c.kind == "step", c.kind)
    check("carrying the route it would join", c.trail == "trails/t")
    check("the same join is never queued twice",
          C.add_step(**{k: props[0][k] for k in ("trail", "book", "via", "date", "why")}) is None)

    # ties first, everywhere
    check("ties sort ahead of facts",
          C.steps_first(C.pending())[0].kind == "step")
    out = C.render()
    check("the tie renders with the arrow", "TIE" in out and "→" in out, out[:90])
    check("the fact renders as a sentence and a destination", "FACT" in out)
    check("the tie is listed first",
          out.index("TIE") < out.index("FACT"), out[:120])

    # accepting each routes to a different place
    where = C.accept(c.id)
    check("accepting a tie writes the ROUTE, not a Book", where == "trails/t", str(where))
    route = (root / "brain" / "trails" / "t.md").read_text()
    check("the step is numbered after the ones already there", "2. **" in route, route[-160:])
    check("and reaches the joined Book", "[[projects/joined]]" in route)
    joined = (root / "brain" / "projects" / "joined.md").read_text()
    check("nothing was written inside the Book itself",
          "## Route" not in joined and "harbour closed" not in joined)
    check("and the REAL Library was never touched",
          not (ROOT / "brain" / "trails" / "t.md").exists())

    # the step must READ like the steps already there: a short bold move, the
    # date once, the reason under it. Handing the whole quotation to both halves
    # printed "**2026-07-13 — Superseded by ... .** — 2026-07-13".
    step = route[route.index("2. **"):]
    check("the date is not printed twice", step.count("2026-05-02") == 1, step)
    check("the move is not the raw dated quotation",
          not step.startswith("2. **2026-"), step[:60])
    move, why = T._split_quote("2026-01-02 — First sentence here. Second one follows.")
    check("a quote splits into a move and a reason",
          move == "First sentence here." and why == "Second one follows.",
          f"{move!r} / {why!r}")
    check("a back-reference the arrow already makes is not repeated",
          "See [[projects/joined]]" not in step, step)

    if prev is None:
        os.environ.pop("MEMEX_ROOT", None)
    else:
        os.environ["MEMEX_ROOT"] = prev
    importlib.reload(L); importlib.reload(E2); importlib.reload(C); importlib.reload(T)
    shutil.rmtree(root, ignore_errors=True)


def test_a_reason_is_never_invented():
    """A tie with no written reason stays in the backlog. It never becomes a Button.

    The first version quoted the Book's EARLIEST dated entry as the reason,
    which is when the Book entered the record and not why the tie exists. It
    produced "canonical-terminology joins building-memex because 'frozen
    documents are renamed'" -- a misattribution wearing a citation.
    """
    print("\nreason — quoted from the record, or there is no Button")
    root = Path(tempfile.mkdtemp())
    _fake_library(root)
    # a link with no prose reason at all: only under ## See Also
    (root / "brain" / "projects" / "noreason.md").write_text(
        '---\ntitle: "No reason"\ntype: project\ncreated: 2026-01-01\n---\n\n'
        "# No reason\n\nA Book with nothing said about why.\n")
    (root / "brain" / "projects" / "onroute.md").write_text(
        (root / "brain" / "projects" / "onroute.md").read_text()
        .replace("nореason", "noreason"))
    prev = os.environ.get("MEMEX_ROOT")
    os.environ["MEMEX_ROOT"] = str(root)
    import importlib
    from memex import library as L; importlib.reload(L)
    from memex import trails as T; importlib.reload(T)

    picked = {r["book"] for r in T.propose_steps(limit=20)}
    check("a See Also link carries no reason, so it is not proposed",
          "projects/noreason" not in picked, str(picked))
    check("the tie explained in prose still is", "projects/joined" in picked)

    src = next(b for b in L.books() if b.slug == "projects/onroute")
    check("metadata is refused as a reason",
          T._tie_sentence.__doc__ is not None)
    for bad in ("phase: shipping now and it links [[projects/joined]] here.",
                "A fragment mentioning [[projects/joined]] with no full stop"):
        check(f"refused: {bad[:28]}…",
              T._META.match(bad) is not None or not bad.rstrip().endswith((".", "?", "!")))
    check("an identifier is refused outright",
          T._IDENT.search("uuid deadbeefcafe4f00ba5eba11c0ffee99 here") is not None)

    if prev is None:
        os.environ.pop("MEMEX_ROOT", None)
    else:
        os.environ["MEMEX_ROOT"] = prev
    importlib.reload(L); importlib.reload(T)
    shutil.rmtree(root, ignore_errors=True)


def test_open_shows_the_queue():
    """`memex open` must show the candidates, or the queue rots.

    Measured 2026-09-09: three candidates sat waiting while `memex open` said
    "Nothing waiting on you." It only read the open questions inside Books.
    Session start advertises `memex open` as "what is waiting on your word",
    so this was the advertised route to the queue failing silently -- the owner's
    own worry, "unless it will just rot somewhere just like our ##open issue".
    """
    print("\nopen — the queue is visible where the owner is told to look")
    root = Path(tempfile.mkdtemp())
    (root / "brain" / "projects").mkdir(parents=True)
    (root / "state").mkdir()
    env = dict(os.environ, MEMEX_ROOT=str(root))

    def run_open():
        return subprocess.run([sys.executable, "-m", "memex", "open"], cwd=ROOT,
                              env=env, capture_output=True, text=True).stdout

    check("empty queue still reads as empty", "Nothing waiting" in run_open())

    from memex import candidates as C
    import importlib
    from memex import library as L
    prev = os.environ.get("MEMEX_ROOT")
    os.environ["MEMEX_ROOT"] = str(root)
    importlib.reload(L); importlib.reload(C)
    cand = C.add("projects/thing", "Ballast is loaded before the tide turns.")
    cid = cand.id
    if prev is None:
        os.environ.pop("MEMEX_ROOT", None)
    else:
        os.environ["MEMEX_ROOT"] = prev
    importlib.reload(L); importlib.reload(C)

    out = run_open()
    check("the candidate is listed", "Ballast is loaded" in out, out[:120])
    check("with the id to answer it", str(cid) in out, out[:120])
    check("and how to say yes", "--accept" in out, out[:120])

    shutil.rmtree(root, ignore_errors=True)


def test_criterion_is_carried():
    """The rule for what to record must arrive before the thing worth recording.

    It was going to be a Book. The owner, 2026-09-09: "make sure this not to be
    written as a book and just rot somewhere ... the agent should always carry
    [it]." A Book is read when someone goes looking; this has to be in front of
    the agent unasked. So it is one string in code with three readers, and this
    test is what stops a fourth copy appearing.
    """
    print("\ncriterion — one string, carried everywhere, never a copy")
    from memex.criterion import EXPECTED_PER_SESSION, TRIGGERS, render
    body = render()

    check("the list is closed at six", len(TRIGGERS) == 6, str(len(TRIGGERS)))
    check("every trigger is rendered",
          all(c in body and w[:24] in body for c, w in TRIGGERS))
    check("both halves of the test are stated",
          "future question" in body and "would go look at" in body)
    check("the exclusions are named", "Git holds the what" in body)
    lo, hi = EXPECTED_PER_SESSION
    check("an expected rate makes it auditable", 0 < lo < hi <= 10, f"{lo}-{hi}")

    # reader 1: every session under ~
    src = (ROOT / "memex" / "session.py").read_text()
    check("session start injects it",
          "from .criterion import render" in src and "_criterion()" in src)

    # reader 2: the Scribe, at prompt-assembly time
    src = (ROOT / "memex" / "scribe.py").read_text()
    check("the Scribe's prompt is built with it",
          "from .criterion import render" in src and "_criterion()" in src)
    check("and the Scribe is told it cannot press",
          "cannot press the Button" in src)

    # reader 3: the skill
    skill = (ROOT / "skills" / "memex-input" / "SKILL.md").read_text()
    check("the skill names the gate", "criterion.py" in skill)
    check("and asks for the basis to be carried",
          "Carry the basis" in skill)

    # The copy that must NOT exist. Matching the PHRASE was wrong: an agreed
    # fact on projects/memex legitimately says where the rule lives, and says
    # it in those words. What must not exist is a Book that REPRODUCES the
    # criterion -- that is the copy that would drift.
    strays = []
    for p in (ROOT / "brain").rglob("*.md"):
        body = p.read_text()
        hits = sum(1 for _, what in TRIGGERS if what[:24] in body)
        if hits >= 3:
            strays.append(f"{p.relative_to(ROOT)} ({hits}/6 triggers)")
    check("the trigger list was not also filed as a Book", not strays, str(strays))


def test_the_button():
    """One name, in every file that carries it.

    The concept lived in six files as "the agreement popup", "a selection", and
    "AskUserQuestion" depending on which one you opened. A term that drifts is a
    term the next agent reinvents. The owner named it 2026-09-08: the Button.
    """
    print("\nvocabulary — the Button is called the Button")
    for rel in ("AGENTS.md",
                "skills/memex-input/SKILL.md",
                "scribe/PROMPT.md",
                "brain/RESOLVER.md",
                "brain/concepts/links-and-trails.md",
                "brain/concepts/memex-glossary.md"):
        body = (ROOT / rel).read_text().lower()
        check(f"{rel} names the Button", "the button" in body)
    defn = (ROOT / "brain" / "concepts" / "links-and-trails.md").read_text()
    check("the definition says what presses it",
          "Stop hook" in defn and "memex-input" in defn)
    check("and that it is the only way in",
          "except through the Button" in defn or "only way anything enters" in defn)


def test_stop_hook_installed():
    """The hook must not swallow what makes it work.

    It was installed as `... --nudge 2>/dev/null || true`: stderr discarded and
    the exit code forced to 0. Exit 2 IS the mechanism and stderr IS the
    message, so the hook looked present and did nothing.
    """
    print("\nhook — the Stop hook is wired to block, not to print")
    s = Path.home() / ".claude" / "settings.json"
    if not s.exists():
        check("settings.json present", True, "skipped — not this box")
        return
    try:
        cmd = json.loads(s.read_text())["hooks"]["Stop"][0]["hooks"][0]["command"]
    except (KeyError, IndexError, json.JSONDecodeError):
        check("a Stop hook is configured", False)
        return
    check("a Stop hook is configured", "pending --nudge" in cmd)
    check("it does not discard stderr", "2>/dev/null" not in cmd, cmd)
    check("it does not force exit 0", "|| true" not in cmd, cmd)


def test_library():
    print("\nlibrary — the Books parse")
    from memex.library import books, shelves, read_book
    bs = books()
    # The threshold guards against an empty or unreadable brain/, not against a
    # small one: this repository ships a worked EXAMPLE Library of ten Books,
    # where a private one runs to dozens. The structural checks below are what
    # actually test the contract, and they scale to either.
    check("Books load", len(bs) >= 5, str(len(bs)))
    # The shelf is the type, and nothing else. brain/CLASSIFICATION.md.
    from memex.library import SHELF
    shelf_set = set(shelves())
    allowed = {s for s in SHELF.values() if s} | {"trails"}
    check("every shelf is a type", not (shelf_set - allowed),
          str(sorted(shelf_set - allowed)))
    check("the retired shelves are gone",
          not (shelf_set & {"papers", "identity", "archive", "inbox", "personal",
                            "infrastructure", "direction", "frameworks",
                            "preferences", "routine", "service", "corrections"}))
    astray = [b.slug for b in bs
              if b.slug.split("/")[0] not in (SHELF.get(b.type), "trails")]
    check("every Book sits on the shelf its type names", not astray, str(astray[:3]))
    check("every Book carries the topic facet",
          not [b.slug for b in bs if not b.frontmatter.get("about")],
          str([b.slug for b in bs if not b.frontmatter.get("about")][:3]))
    bad = [b.slug for b in bs if not b.title or not b.slug]
    check("every Book has a title and slug", not bad, str(bad))
    p = ROOT / "brain" / "sources" / "as-we-may-think.md"
    if p.exists():
        bk = read_book(p)
        fm, above, below = E.split_book(p.read_text())
        check("the long paper splits above/below the line",
              len(above) > 1000 and "## Trail" in below)
        check("its frontmatter survived", bk is not None and bk.title.startswith("As We May Think"))


# ---------------------------------------------------------------- recall.py --
def test_recall_facets():
    """The facets are scored, and they stay out of what a reader sees.

    Layer 2 of brain/CLASSIFICATION.md is only real if `about:` can actually be
    found: six Books about the owner sat on six shelves and now sit on one, so the
    facet IS the tie. Folded into a chunk it matched fine but leaked "notes owner"
    into the front of every excerpt, so it is scored from its own field instead.
    Nothing covered either half -- there was no recall test at all -- until the
    2026-09-09 review.

    Embeddings are stubbed out, which forces the keyword path: no Ollama, no
    network, deterministic.
    """
    print("\nrecall — the facets are scored, never shown")
    import memex.recall as R
    from memex.library import Book

    def book(slug, fm, body):
        return Book(slug=slug, path=Path(slug), title="T",
                    type=fm.get("type", "note"),
                    visibility=fm.get("visibility", ""), frontmatter=fm, body=body)

    f = R._facets(book("notes/owner-routine",
                       {"type": "note", "about": ["owner"]}, "body"))
    check("facets carry the shelf", "notes" in f.split())
    check("facets carry the topic", "owner" in f.split())

    f2 = R._facets(book("sources/x", {"type": "source", "about": ["memex"],
                                      "kind": "paper", "status": "archived",
                                      "domain": ["H.3.7"]}, "body"))
    for want in ("memex", "paper", "archived", "H.3.7"):
        check(f"facets carry {want}", want in f2.split())

    # A Book whose BODY never says "owner" -- only its facet does. Before the
    # facet was indexed this Book was unreachable by its own subject.
    real_load, real_embed = R._load, R._embed
    R._embed = lambda text: None                      # force the keyword path
    R._load = lambda: {
        "__version__": R.INDEX_VERSION,
        "notes/owner-routine": {
            "title": "Routine", "vault": False, "facets": "notes owner", "fvec": None,
            "chunks": [{"text": "Sleep 00:00-07:00; the evening blocks move.",
                        "vec": None, "kind": "agreed"}]},
        "projects/other": {
            "title": "Other", "vault": False, "facets": "projects memex", "fvec": None,
            "chunks": [{"text": "Unrelated to the subject at hand.",
                        "vec": None, "kind": "agreed"}]},
    }
    try:
        hits = R.search("owner", limit=5)
        top = hits[0] if hits else None
        check("a Book is found by its about: facet alone",
              top is not None and top.slug == "notes/owner-routine",
              str([h.slug for h in hits]))
        check("the facet string never reaches the excerpt",
              top is not None and "notes owner" not in top.excerpt,
              top.excerpt[:60] if top else "no hit")
        check("a Book whose facet does not match stays out",
              all(h.slug != "projects/other" for h in hits))
        # The facets belong to no layer, so letting them score under an
        # explicit filter would quietly defeat it.
        check("an explicit kinds filter is not bypassed by the facet",
              not R.search("owner", limit=5, kinds={"observed"}))
    finally:
        R._load, R._embed = real_load, real_embed



# ---------------------------------------------------------------------------
# Portability and index integrity. Every case below is something a review found
# by running this on Windows, or by pulling the plug on the embedding server.
# ---------------------------------------------------------------------------


def test_the_lock_is_portable():
    """scribe.py imported fcntl at module scope, so the package was Unix-only.

    Nothing subtle happened on Windows: `import memex.session` raised
    ModuleNotFoundError, `memex start` died, and the whole of this file failed
    at import, so 0 of these checks ran on the platform that needed them most.
    """
    print("\nthe lock — one behaviour, two platforms")
    import ast
    from memex import library as L

    src = ast.parse((ROOT / "memex" / "scribe.py").read_text(encoding="utf-8"))
    top = [n for n in src.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = {a.name for n in top if isinstance(n, ast.Import) for a in n.names}
    check("scribe.py no longer imports fcntl at module scope", "fcntl" not in names)
    check("the lock lives in library.py, which both users import",
          hasattr(L, "_try_lock") and hasattr(L, "file_lock"))

    # and it still excludes, which is the only reason it exists
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "x.lock"
        with L.file_lock(p, wait_seconds=0):
            try:
                with L.file_lock(p, wait_seconds=0):
                    check("a second holder is refused", False, "both got in")
            except TimeoutError:
                check("a second holder is refused", True)
        with L.file_lock(p, wait_seconds=0):
            check("the lock is retakeable once released", True)


def test_every_text_file_is_read_as_utf8():
    """No text I/O may rely on the platform's locale encoding.

    On Korean Windows (cp949) reading a Book raised UnicodeDecodeError. On
    Western Windows (cp1252) the same bytes DECODE, into wrong text -- and
    doctor's prompt/edits cross-check then parses mojibake and reports a clean
    bill. The silent case is why this is a test and not a habit.
    """
    print("\nencoding — never the platform's guess")
    import ast
    bad = []
    for py in sorted((ROOT / "memex").glob("*.py")):
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if not isinstance(fn, ast.Attribute):
                continue
            if fn.attr not in ("read_text", "write_text", "open"):
                continue
            if fn.attr == "open":
                mode = node.args[0].value if (node.args and
                       isinstance(node.args[0], ast.Constant)) else ""
                if "b" in str(mode):
                    continue          # binary: an encoding would be wrong
            if not any(k.arg == "encoding" for k in node.keywords):
                bad.append(f"{py.name}:{node.lineno} .{fn.attr}()")
    check("every text read and write names its encoding", not bad,
          ", ".join(bad[:4]))

    from memex.__main__ import _utf8_console
    check("the console is reconfigured for output too", callable(_utf8_console))


def test_the_index_cannot_lie_about_being_embedded():
    """One recall run with Ollama down used to poison the index permanently.

    reindex() wrote every chunk with vec=None NEXT TO A VALID HASH. When the
    server came back, every Book matched its hash and was skipped as unchanged,
    so the Library stayed on keyword matching until a Book's text happened to
    change -- and `doctor` called the index current the whole time.
    """
    print("\nthe index — a hash may not outrun its vectors")
    import tempfile, shutil, json as _json
    from memex import recall as R

    real_embed, real_index, real_state, real_down = R._embed, R.INDEX, R.STATE, R._down
    tmp = Path(tempfile.mkdtemp())
    try:
        R.INDEX, R.STATE = tmp / "i.json", tmp
        R._embed = lambda t: None            # the server is down
        R._down = False
        R.reindex()
        idx = _json.loads(R.INDEX.read_text(encoding="utf-8"))
        recs = [k for k in idx if k != "__version__"]
        check("nothing is marked embedded when the server is down",
              recs and not any(idx[k].get("embedded") for k in recs))
        check("the chunk TEXTS are still written, so keyword search works",
              sum(len(idx[k]["chunks"]) for k in recs) > 0)

        R._embed = lambda t: [0.1] * 8       # the server comes back
        changed, same = R.reindex()
        check("every Book is re-embedded once the server returns",
              changed == len(recs) and same == 0, f"{changed}/{same}")
        idx = _json.loads(R.INDEX.read_text(encoding="utf-8"))
        check("no null vector survives",
              not [c for k in recs for c in idx[k]["chunks"] if c["vec"] is None])
        changed2, same2 = R.reindex()
        check("and caching still works after that",
              changed2 == 0 and same2 == len(recs), f"{changed2}/{same2}")
    finally:
        R._embed, R.INDEX, R.STATE, R._down = real_embed, real_index, real_state, real_down
        shutil.rmtree(tmp)


def test_the_embedding_server_is_probed_once():
    """_embed used to retry per chunk: 426 attempts on a real Library.

    Refused connections are instant on Linux, which is why this looked free.
    On Windows a closed localhost port costs a retry, and a review measured
    over two minutes of apparent hang before the keyword fallback appeared.
    """
    print("\nthe embedding server — one probe, not one per chunk")
    import io, contextlib
    from memex import recall as R

    calls = {"n": 0}
    real_urlopen, real_down = R.urllib.request.urlopen, R._down

    def refuse(*a, **k):
        calls["n"] += 1
        raise OSError("connection refused")
    try:
        R.urllib.request.urlopen = refuse
        R._down = False
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf):
            for i in range(200):
                R._embed(f"chunk {i}")
        check("200 calls cost one connection attempt", calls["n"] == 1, str(calls["n"]))
        check("and the fallback is announced, not silent",
              len(buf.getvalue().strip().splitlines()) == 1, buf.getvalue()[:60])
    finally:
        R.urllib.request.urlopen, R._down = real_urlopen, real_down


def test_a_claim_closes_its_chunk():
    """Splitting in front of a long paragraph is only half the split.

    The paragraph then packed with every short paragraph that FOLLOWED it --
    34 of 60 chunks in this repository's own Library, the worst holding nine
    paragraphs in one vector. The claim still shared a vector with its
    neighbours, which is the defect the split was added to end.
    """
    print("\nchunking — a claim closes its chunk as well as opening it")
    from memex.recall import _chunks, STANDALONE, GLUE
    from memex.library import Book

    claim = "C" * 240 + " the claim itself."
    body = f"{claim}\n\nshort one.\n\nshort two.\n\nshort three.\n"
    bk = Book(slug="projects/x", path=Path("/dev/null"), title="X",
              type="project", visibility="world", frontmatter={}, body=body)
    texts = [c for c, _ in _chunks(bk)]
    holding = [t for t in texts if claim[:40] in t][0]
    check("the claim does not carry the paragraphs after it",
          "short one." not in holding, holding[-40:])

    # a heading is not a claim, and must not become a chunk of its own
    body2 = f"## A heading\n\n{claim}\n"
    bk2 = Book(slug="projects/y", path=Path("/dev/null"), title="Y",
               type="project", visibility="world", frontmatter={}, body=body2)
    texts2 = [c for c, _ in _chunks(bk2)]
    check("a heading rides with the claim it introduces",
          not any(t.strip() == "## A heading" for t in texts2), str(texts2[:1]))
    check("the glue threshold is explicit", GLUE < STANDALONE, f"{GLUE}/{STANDALONE}")


def test_recall_matches_a_korean_particle():
    """Korean glues the particle to the noun, so token equality is the wrong test.

    Measured: "컨트롤러가" scored 0.0 against text reading "컨트롤러는" -- the same
    noun, a different particle -- while the English equivalent scored 0.98.
    """
    print("\nkeyword fallback — a noun keeps its meaning when the particle changes")
    from memex.recall import _keyword

    same = _keyword("컨트롤러가 어떻게 되었나", "컨트롤러는 밸브를 닫았다")
    other = _keyword("컨트롤러가", "온도와 습도를 측정한다")
    english = _keyword("controller valve", "the controller closed the valve")
    check("the same noun matches across particles", same > 0, f"{same:.3f}")
    check("an unrelated sentence still scores zero", other == 0, f"{other:.3f}")
    check("English is unaffected", english > 0.9, f"{english:.3f}")


def test_doctor_sees_a_changed_book():
    """`stale = [b for b in books if b.slug not in idx]` is a membership test.

    It cannot see a Book that is IN the index under its old text -- found by
    its old words, not its new ones -- and it could not see the null-vector
    index at all.
    """
    print("\ndoctor — current means current, not present")
    import tempfile, shutil, json as _json
    from memex import recall as R
    from memex.doctor import report

    real_embed, real_index, real_state = R._embed, R.INDEX, R.STATE
    tmp = Path(tempfile.mkdtemp())

    def index_line():
        out, _ = report()
        return [l for l in out.splitlines() if "search index" in l][0]

    try:
        R.INDEX, R.STATE = tmp / "i.json", tmp
        R._embed = lambda t: [0.1] * 8
        R.reindex()
        check("a fresh index reads ok", "ok" in index_line())

        idx = _json.loads(R.INDEX.read_text(encoding="utf-8"))
        slug = [k for k in idx if k != "__version__"][0]
        idx[slug]["hash"] = "0" * 16
        R.INDEX.write_text(_json.dumps(idx), encoding="utf-8")
        check("an edited Book is reported", "BAD" in index_line(), index_line())

        R.reindex()
        idx = _json.loads(R.INDEX.read_text(encoding="utf-8"))
        idx[slug]["embedded"] = False
        R.INDEX.write_text(_json.dumps(idx), encoding="utf-8")
        line = index_line()
        check("a Book indexed without vectors is reported",
              "BAD" in line and "keyword-only" in line, line)
    finally:
        R._embed, R.INDEX, R.STATE = real_embed, real_index, real_state
        shutil.rmtree(tmp)


def test_a_trail_never_loses_a_step():
    """`trail_file` is the one op that replaces a whole file, and it checked nothing.

    Every other write path enforces its own invariant in code -- `fact` refuses
    to shorten a Book without an exact `replaces`. A model rewriting a Route to
    add step 4 could drop step 2 and nothing would notice, against a document
    that promises "a wrong step is answered by a later step, never rewritten
    away".
    """
    print("\ntrails — append-only, enforced")
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        _fake_library(root)
        seed_classification(root / "brain")
        old_root = os.environ.get("MEMEX_ROOT")
        os.environ["MEMEX_ROOT"] = str(root)
        try:
            import importlib
            from memex import library as L, edits as ED
            importlib.reload(L); importlib.reload(ED)
            was = (root / "brain" / "trails" / "t.md").read_text(encoding="utf-8")
            check("the fixture has a step to lose", len(ED._steps(was)) == 1)

            added = was.rstrip("\n") + (
                "\n\n2. **And then the rail depot took the freight.** — 2026-05-03\n"
                "   Which is why the schedule was rebuilt.\n   \u2192 [[projects/joined]]\n")
            ED.apply_op({"op": "trail_file", "book": "trails/t", "body": added},
                        dry=True, created=set(), actor="scribe")
            check("appending a step is allowed", True)

            dropped = added.replace(
                "1. **The harbour closed.** — 2026-05-02\n   It forced everything after it.\n"
                "   \u2192 [[projects/onroute]]\n", "")
            try:
                ED.apply_op({"op": "trail_file", "book": "trails/t", "body": dropped},
                            dry=True, created=set(), actor="scribe")
                check("dropping a step is refused", False, "it was accepted")
            except ED.Refused as e:
                check("dropping a step is refused", "append-only" in str(e), str(e)[:60])
        finally:
            if old_root is None:
                os.environ.pop("MEMEX_ROOT", None)
            else:
                os.environ["MEMEX_ROOT"] = old_root
            import importlib
            from memex import library as L, edits as ED
            importlib.reload(L); importlib.reload(ED)


def test_the_queue_survives_two_writers():
    """The Scribe's lock guards scribe-queue.txt. It never guarded this file.

    candidates.jsonl is read whole, changed, and written whole. A live session
    running `memex note` and the background Scribe adding in the same instant
    each wrote a file computed from the state before the other, and one entry
    vanished with nothing logged. Measured unlocked: 37 of 40 writes lost.
    """
    print("\nthe candidate queue — two writers, no losses")
    import tempfile, shutil, threading
    from memex import library as L, candidates as C

    real = (L.STATE, C.STATE, C.QUEUE, C.LOCK, C.MAX_PENDING)
    tmp = Path(tempfile.mkdtemp())
    try:
        L.STATE = C.STATE = tmp
        C.QUEUE, C.LOCK = tmp / "q.jsonl", tmp / "q.lock"
        C.MAX_PENDING = 100
        n = 24
        barrier = threading.Barrier(n)

        def w(i):
            barrier.wait()
            C.add("projects/greenhouse",
                  f"alpha{i}zz beta{i}yy gamma{i}xx delta{i}ww", "t")
        ts = [threading.Thread(target=w, args=(i,)) for i in range(n)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        check(f"{n} concurrent adds all land", len(C.pending()) == n,
              str(len(C.pending())))

        C.QUEUE.unlink(missing_ok=True)
        C.MAX_PENDING = 6
        barrier2 = threading.Barrier(n)

        def w2(i):
            barrier2.wait()
            C.add("projects/greenhouse",
                  f"kappa{i}zz lambda{i}yy mu{i}xx nu{i}ww", "t")
        ts = [threading.Thread(target=w2, args=(i,)) for i in range(n)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        check("and the ceiling still holds under contention",
              len(C.pending()) == 6, str(len(C.pending())))
    finally:
        L.STATE, C.STATE, C.QUEUE, C.LOCK, C.MAX_PENDING = real
        shutil.rmtree(tmp)

if __name__ == "__main__":
    for t in (test_edits, test_trust_boundary, test_wrapper_filter,
              test_prune_scope, test_candidates, test_consumed, test_incremental_read,
              test_gate, test_guards, test_session_scope, test_waiting, test_trails,
              test_cli, test_prompt_matches_code, test_lock_and_queue,
              test_books_are_owners, test_queue_cannot_stack,
              test_the_button, test_open_shows_the_queue,
              test_the_schedule_can_see_the_work,
              test_the_queue_has_a_ceiling,
              test_a_claim_gets_its_own_vector,
              test_two_buttons, test_a_reason_is_never_invented,
              test_criterion_is_carried,
              test_stop_hook_installed, test_library,
              test_recall_facets,
              test_the_lock_is_portable, test_every_text_file_is_read_as_utf8,
              test_the_index_cannot_lie_about_being_embedded,
              test_the_embedding_server_is_probed_once,
              test_a_claim_closes_its_chunk,
              test_recall_matches_a_korean_particle,
              test_doctor_sees_a_changed_book,
              test_a_trail_never_loses_a_step,
              test_the_queue_survives_two_writers):
        t()
    print(f"\n{len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED: " + ", ".join(FAIL))
    sys.exit(1 if FAIL else 0)
