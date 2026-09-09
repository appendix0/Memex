"""What earns a Button — the one criterion, in one place, carried everywhere.

The owner, 2026-09-09: *"you writing it mid session is wholely honor system now. No
robust criterion, no prompt for this, just you recording anything that you
might think it is important ... My agreement on button is not enough when the
context I am dealing with become vast."*

He is right. His yes only ratifies a selection he cannot see the basis of, so
the selection needs a rule that is stated, closed, and cheap enough to apply
every time without ceremony.

WHY THIS IS NOT A BOOK. It was going to be `concepts/what-earns-a-button.md`.
The owner: *"make sure this not to be written as a book and just rot somewhere. This
is an important thing that the agent(you) should always carry."* A Book is read
when someone goes looking; this has to be in front of the agent before it needs
it. So it lives here, is injected by `memex start` into every session under
~, and is appended to the Scribe's prompt at runtime. One string, three
readers, no copies to drift.

Grounded in the essay, not in taste:
  the closed list      §3-4  judgment is the human's; the machine does the
                             repetitive part, which is scanning for the shapes
  "the future question" §7.6 the Turkish bow trail was made for "why was the
                             bow better?" and reused years later for "why do
                             societies resist better technology?" A record
                             earns its place by the question NOT YET ASKED.
  "a reader would look" §7.7 trails transfer; it must hold for someone who was
                             not in the room
  the exclusions       §2    be profligate about the STORE -- which is the
                             transcripts, kept whole -- not about the Library,
                             which is the abstract of the facts
"""
from __future__ import annotations

# The closed list. Nothing outside it may become a Button. Each is written to
# be recognised, not weighed: if you are arguing about whether one fired, it
# did not.
TRIGGERS: list[tuple[str, str]] = [
    ("T1", "the owner states a rule, preference, correction or decision"),
    ("T2", "a measurement — a number, count, rate or pass/fail from running something"),
    ("T3", "a cause established — \"X is broken BECAUSE Y\", with the evidence named"),
    ("T4", "an external source read that changed a decision"),
    ("T5", "a capability boundary moved — possible became impossible, or the reverse"),
    ("T6", "a recorded claim contradicted — a Book says X, we established not-X"),
]

# Where drift actually happens. Naming them is cheaper than re-deciding.
EXCLUDED = ("progress, plans, intentions, \"it works now\", restatements of a "
            "file, and anything git or `--help` answers in under a minute")

# If the criterion is right this is the rate. Zero in a session that established
# six things is a miss; a dozen is drift. A number makes it auditable instead of
# believed.
EXPECTED_PER_SESSION = (2, 5)


def render() -> str:
    """The block injected at session start and into the Scribe's prompt."""
    rows = "\n".join(f"   {code}  {what}" for code, what in TRIGGERS)
    lo, hi = EXPECTED_PER_SESSION
    return (
        "## What earns a Button\n"
        "Nothing enters a Book except through the Button — the owner shown one exact\n"
        "sentence and one exact Book, saying yes. What you may put in front of\n"
        "him is not a judgement call. Two steps:\n\n"
        "**1. Is it one of these six?** Nothing outside the list qualifies.\n"
        f"{rows}\n\n"
        "**2. Say both in one breath:** the future question it answers, and the\n"
        "thing a reader would go look at. Either missing → no Button.\n\n"
        f"Never: {EXCLUDED}. Git holds the what; a Book holds what git cannot.\n\n"
        "Press the moment it happens, not at the end. Carry the basis with it:\n"
        "`T# · <the referent> · answers \"<the future question>\"`\n"
        f"Roughly {lo}–{hi} a session. Zero when six things were established is a\n"
        "miss, and a dozen is drift — both are visible, which is the point."
    )
