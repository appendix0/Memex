---
title: "Home server"
type: infra
created: 2026-09-09
about: [home-server]
---

# Home server

**This is an example Book.** The always-on machine the greenhouse controller and
MEMEX both run on. An `infra` Book records how a machine *actually behaves* —
above all the traps that bite you if you forget them.

## State

- Runs the controller as a systemd unit and MEMEX's daily pass from cron.
- Backups are encrypted before they leave the machine, to two providers.

## Gotchas

- **Cron does not run a login shell.** A job that works interactively can pick a
  different, older interpreter under cron's minimal PATH and run that way for
  months without any error. Set `PATH` absolutely at the top of every cron
  script.
- **`--version` reads the binary on disk, not the one a running process
  started from.** A long-lived process keeps its original inode after an
  upgrade. To check what a process is *actually* running, read
  `/proc/<pid>/exe`; a `(deleted)` suffix means it is on a stale build.
- **Judge memory by measured free, not by summed RSS.** RSS double-counts pages
  shared between processes; a 1.9 GB RSS tally freed roughly 560 MB in reality.

## Rules

- **Never write an identifier into a Book** — no keys, tokens, cloud resource
  ids, IP addresses or passwords, and a `vault` label does not change that.
  Record *where* to recover one; never the value.
- **Every change to the machine's shape gets a receipt** — what changed, why,
  and how to roll it back. Move things aside rather than deleting them. An
  undocumented change to a long-lived box is indistinguishable from rot the next
  time someone looks.

## See Also

[[projects/greenhouse]]

---

## Trail

2026-09-09 — The gotchas above are on `infra/` rather than in the controller's
own Book because they are properties of the **machine**, and the next project to
run here will hit them identically. Filing them with the first project that
tripped over them is how the second project trips over them again.

## Timeline

2026-09-09 — Book created as the worked example for the `infra/` shelf.
