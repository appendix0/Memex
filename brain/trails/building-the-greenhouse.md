---
title: "Why the greenhouse controller is shaped the way it is"
type: note
created: 2026-09-09
about: [greenhouse]
---

# Why the greenhouse controller is shaped the way it is

**This is an example trail.** The reasoning behind the controller's shape, in
the order each decision forced the next.

Note what a trail is: an **ordered route over links that already exist**, with a
reason at each turn. Every reason below is quoted from a dated entry already
written in one of these Books. Where the record held no reason, no step was
written — a step is dropped rather than guessed.

Note also that the order is **logical, not chronological**. The dates ride
along; they do not decide the sequence.

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
   reading, and water use did not rise with it. Those two together answer the
   objection that the controller is only a timer: a timer that watered more
   would raise both numbers.
   → [[writing/benchmark-report]]

4. **The trap that survives the project belongs to the machine.** — 2026-09-09
   The cron PATH and the stale-binary traps are properties of the host, and the
   next project to run there will hit them identically. Filing them with the
   first project that tripped over them is how the second one trips again.
   → [[infra/home-server]]
