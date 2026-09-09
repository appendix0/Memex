---
title: "Greenhouse controller"
type: project
created: 2026-09-09
about: [greenhouse]
---

# Greenhouse controller

**This is an example Book.** A small irrigation and climate controller for a
backyard greenhouse: soil-moisture sensors on a microcontroller, a pump relay,
and a scheduler that decides when to water. It exists here to show the shape of
a `project` Book — what is being built, what state it is in, and what is still
open.

## State

- Four capacitive soil-moisture sensors, polled every 15 minutes.
- The scheduler waters when the trailing-hour median falls below a threshold,
  not on a fixed clock.
- Runs as a service on [[infra/home-server]].

## Open Threads

- Sensor 3 reads 4% lower than the others in the same pot. Not yet established
  whether that is calibration or the sensor.
- No alerting when the pump relay fails closed.

## Rules

- **A watering decision is logged with the reading that caused it.** A schedule
  that cannot say why it fired cannot be debugged after the fact.

## See Also

[[infra/home-server]] · [[research/germination-trial]] ·
[[writing/benchmark-report]]

---

## Trail

2026-09-09 — The scheduler waters on a **median of the trailing hour** rather
than on the latest reading, because a single sensor briefly touching dry air
during a top-up fired the pump twice in four minutes. The median makes a
one-sample excursion unable to move the decision. See
[[research/germination-trial]].

## Timeline

2026-09-09 — Book created as the worked example for the `projects/` shelf.
