# MEMORY.md

Hot state. Loaded into every session. **This is not the Library** — it holds
what is live right now, not what is durably known. Anything here that is still
true in a month belongs in a Book.

Keep it short. Everything in this file is paid for on every single session.

---

## Standing rules learned from corrections

One line, dated, imperative, with the bug it prevents:

> - 2026-01-15 — Compute the day of the week with `date`, never from memory.
>   (Bug: asserted Tuesday on a Wednesday; the whole schedule downstream was
>   wrong.)

*(Replace with your own.)*

## Active context

What is being worked on right now, and anything a new session would otherwise
have to be told again.

*(Empty.)*

## Open commitments

Things the agent said it would do and has not finished, and things others owe
the owner. **A promise not in this file will be forgotten, and being forgotten
is how an agent loses trust.**

*(Empty.)*
