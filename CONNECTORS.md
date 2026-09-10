# Connectors — design, not yet built

**Status: design only. No connector exists in this repository.** This file is
here so the constraints are settled before any code reaches a mailbox, and so
that anyone who builds one does not have to re-derive them.

The motivating case is email, but the shape generalises to any external source
a person already owns: mail, documents, issue trackers, chat.

---

## Why it belongs

The Library is currently fed by exactly one source: the conversation. That is a
real ceiling. The most consequential things a person knows often arrive
somewhere else — a decision settled in a thread, a constraint stated by someone
else, a date that moved. An agent that can only remember what was said *to it*
is missing most of the record.

## The rule that decides the whole design

> **An email is not a fact.**

The temptation is to sync a mailbox into the Library. That is the add-everything
regime, and it is the one the measurements rank last: adding everything scores
worse than a frozen hand-picked shelf, and both lose badly to strict curation.
Volume is the failure mode, not the goal.

What may enter is a **claim derived from** a message, held to exactly the same
bar as a claim derived from a conversation: one of the six triggers in
`memex/criterion.py`, plus the two-part test — name the future question it
answers, and the thing a reader would go look at.

A connector is therefore **not** an importer. It is another *noticer*, feeding
the same queue, gated by the same Button.

```
mailbox  →  fetch (bounded)  →  criterion  →  candidate queue  →  the Button  →  a Book
                                    │
                                    └─ fails the six triggers → dropped, never stored
```

## Five constraints, all non-negotiable

**1. Inbound only.** `ACCESS_POLICY.md` already settles this: a vault Book is
*"never written back to a third-party service — inbound only."* A connector
reads. It never writes a Book, a summary, or a reply back to the source. The
credential it holds should be read-scoped, and if the provider offers no
read-only scope, that is a reason not to build it.

**2. Third-party material is `vault` by default, not by judgement.** Almost
everything in a mailbox is written by, or about, people who never agreed to be
in anyone's Library. RESOLVER Test 0 already sends that to `visibility: vault`,
and the code guard on `type: person` and on `about:` naming a person already
enforces it. A connector must set the label at ingest and never leave it to be
decided later.

**3. Never store the source.** The Book records what was established and where
to look it up — a message id, a thread reference. It does not paste the message
body, the address book, or the attachment. The source system already holds the
source; duplicating it into a Library that is backed up elsewhere multiplies the
exposure for no retrieval benefit.

**4. The queue ceiling is the design constraint, not the API.** The whole queue
holds ten, and it **refuses** rather than displacing when full — a queue that
silently drops the oldest item is a queue that loses things. One mailbox sync
would exhaust that instantly. So the connector's job is not fetching; it is
**selection**, and it must be tuned to produce roughly the same 2–5 candidates
per run that a session does. A connector that regularly fills the queue is
miscalibrated and should be treated as broken.

**5. No credential in a Book, ever.** Not in a `vault` Book either. A `vault`
label does not make a secret admissible; secrets are not knowledge. Record where
a token is recoverable, never its value.

## What a candidate from a connector looks like

Identical to any other candidate, plus its origin — so that a fact's provenance
survives, and so a misbehaving connector can be identified and its output
reviewed as a group:

```json
{"id": "…", "book": "projects/x", "text": "<the standing statement>",
 "kind": "fact", "source": "connector:mail", "ref": "<message id>",
 "seen": "<timestamp>"}
```

`source` is already a field on the candidate record; nothing new is needed to
carry it.

## Open questions, honestly open

- **What triggers a fetch?** The daily pass is the natural host — it already
  runs unattended, reads only what it is pointed at, and proposes without
  writing. But the daily pass deliberately **calls no model**, which is why it
  costs nothing to run; extracting a claim from prose does not. Either the
  connector gets its own schedule, or the daily pass stops being free. That
  trade has not been made.
- **How is "already seen" tracked** without storing message contents? A
  high-water mark per source is the obvious answer and it is wrong on its own:
  mail is not append-only, and a thread that grows re-presents old ground.
- **Who decides the destination Book?** The existing write path resolves a
  destination by searching the Library first. That works when the agent has
  conversational context. A connector has only the message.

## What would make this a mistake

If the first version fetches broadly and lets the Button sort it out. That
inverts the design: the criterion exists so that a human is never handed a pile
to triage. **A connector that raises the queue's average depth is a regression,
however much it ingests.**

The measure of success is not messages processed. It is whether the Library
answers a question next year that it could not answer today.
