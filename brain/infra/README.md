---
title: "infra/ — resolver"
type: resolver
created: 2026-09-09
---

# infra

**Goes here:** A machine, server, network, service or runtime, and how it
actually behaves — including the environment gotchas that bite you if you
forget them. `type: infra`.

**Does NOT go here:** The project that runs on it (`projects/`).

## The rule that makes this shelf worth having

Record the **trap**, not the tutorial. "The service needs an absolute PATH
because cron does not run a login shell" is worth a Book. "How to use cron" is
not; it is a manual page.

## Never write an identifier

Not in a `vault` Book either. **A `vault` label does not make a secret
admissible; secrets are not knowledge.** No keys, tokens, cloud resource ids, IP
addresses, passwords or fingerprints. They are recoverable from the systems that
own them.

Record *where* to recover one — "the deploy key lives in the password manager
under <entry name>" — never the value.

The sensitive half of this shelf carries `visibility: vault`.

## See Also

[[RESOLVER]] · `ACCESS_POLICY.md` (repo root — outside the Library, so not a wiki-link)
