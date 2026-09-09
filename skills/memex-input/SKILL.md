---
name: memex-input
version: 2.0.0
description: |
  Put knowledge into MEMEX — a fact on an existing Book, a new Book, or a
  correction that supersedes one. Always shows the owner the exact sentence and the
  exact destination through the Button, and writes only on yes. Use when the owner asks to
  record something, or when something durable was established mid-session.
triggers:
  - add this to memex
  - remember this
  - file this
  - write that down
  - make a book for this
  - save this paper
allowed-tools:
  - Bash
  - Read
  - AskUserQuestion
---

# Writing into MEMEX

A Book is a **base of fact**. Nothing enters one on an agent's word.

Three steps, no shortcuts:

**compose → the Button → write.**

---

## 0. Does it qualify at all?

**The gate is not yours to set.** `memex/criterion.py` holds it, and every
session already carries it — `memex start` injects it before the
conversation begins. Two steps, both cheap:

1. **One of the six triggers?** T1 the owner states a rule · T2 a measurement ·
   T3 a cause established · T4 a source that changed a decision · T5 a
   capability boundary moved · T6 a recorded claim contradicted. Nothing
   outside the list qualifies.
2. **Name the future question it answers, and the thing a reader would go
   look at.** Either missing → no Button.

Never: progress, plans, intentions, "it works now", restatements of a file,
or anything git answers in a minute.

The owner, 2026-09-09: *"My agreement on button is not enough when the context I am
dealing with become vast."* His yes ratifies the sentence; it cannot ratify a
selection he never saw. The list is what makes the selection checkable.

## 1. Compose

Turn what the owner said into **one standing statement** — independently true,
independently checkable, and still true next year.

> Not: *"the owner decided to keep the PDFs."*
> But: **"Papers are stored as the original beside a Book; a summary alone
> cannot be checked against the source."**

> Not: *"the link is stale"* — a lie the moment someone fixes it.
> But: **"the README's setup link pointed at `scripts/bootstrap/`, deleted in a1b2c3d;
> found 2026-09-07"**.

Two claims are two facts. `--replaces` matches text **exactly**, so a claim
buried inside a paragraph can never be corrected later without rewriting the
sentences around it.

Then pick the destination:

- `memex recall "<subject>"` first — the Book usually already exists.
- `brain/RESOLVER.md` routes the type; `brain/CLASSIFICATION.md` turns it into
  a shelf and the facets that go with it. **Read them, don't guess.**
- **The shelf is the `type:`.** There is no second question.
- **Always set `about:`** — the topic facet, from the controlled list in
  CLASSIFICATION.md. It is the tie that replaced the shelf; a Book without
  it is findable only by its own words.
- **Test 0**: anything about a person, identity, relationship, health, money
  or personal material is `visibility: vault`. `people/`, `type: person` and
  an `about:` naming a person are refused without it — don't make the code
  argue with you.
- Never any secret value. Record *where* to recover one, never the value.

---

## 2. The Button — AskUserQuestion, always

Bush §7: nothing ties itself; the researcher presses. **The Button** is that
press — the owner shown one exact thing and one exact destination, saying yes.
Definition: `brain/concepts/links-and-trails.md`.

**There are two Buttons, because there are two acts.** Bush names them
separately and MEMEX keeps them separate. The owner must be able to tell which one he
is being asked for *without reading the words*, so the shapes differ — not just
the labels.

| | **FACT** | **TIE** |
|---|---|---|
| what it does | writes a claim into a Book | joins a Book to a route, as a step |
| Bush | the record (§2) | the important act (§7) |
| what the owner judges | is this true, and does it belong here? | did this force that, and is *this* why? |
| header chip | `MEMEX` | `TRAIL` |
| the visible shape | a sentence, then a destination | an **arrow** between two things |
| where it lands | `brain/<shelf>/<book>.md` | `brain/trails/<route>.md`, never inside a Book |
| ordering | after the ties | **always asked first** |

### The FACT Button

```
header:   "MEMEX"                       (≤12 chars)
question: Should I write "<the exact sentence>" on <shelf/book>?

          T# · <referent> · answers "<the future question>"

options:  Yes             — write it exactly as shown
          Reword          — right idea, wrong wording; redraft and ask again
          Different Book  — right fact, wrong destination
          No              — don't record this
```

The owner sees the sentence **as it will appear** and the Book **it lands on**. He
cannot agree to a summary of a sentence he has not read.

Three shapes of fact, three questions:

| Shape | The question |
|---|---|
| Fact on an existing Book | `Should I write "<sentence>" on <shelf/book>?` |
| New Book | `Create <shelf/slug> — "<title>"<, vault> — opening with "<sentence>"?` |
| Correction | `On <shelf/book>, replace "<old>" with "<new>"?` |

### The TIE Button

```
header:   "TRAIL"                       (≤12 chars)
question: Tie  <shelf/book>  →  <trails/route>   as step N?

          because “<the reason, QUOTED from the record>”
          — quoted from <the Book holding the link>, <date>

options:  Yes               — add the step exactly as shown
          Different reason  — the tie holds, that is not why; say what is
          Different trail   — right tie, wrong route
          No                — these do not belong on one route
```

**The arrow is the signature.** A tie is one Book joining a route; the question
must *look* like that, because that is what Bush's press does — *"the process of
tying two items together is the important thing."*

**The reason is quoted, never composed.** `trails.py` refuses to invent one, and
so must the question: name the Book the sentence came from and its date, so the owner
is ratifying an existing sentence rather than being handed a writing task. If
the record holds no reason, there is no Button — the tie stays in the backlog.

**A tie is never asked about a link.** A link is made freely, with no ceremony
and no permission; there are 206 of them. Only the *step* — the ordered move
with a reason — goes through a Button.

**Rules for both Buttons:**

- **Ties first.** When both are waiting, ask every TIE before any FACT. Bush
  calls the tie the important act, and facts are the thing there is no shortage
  of. `memex open` and the Stop hook both order them this way already.
- One question per item. Up to 4 in one press **only when they came from the
  same moment** — never accumulate them across a session.
- The question carries the content. Option labels stay one line.
- **Carry the basis.** A FACT carries `T# · <referent> · answers "<question>"`;
  a TIE carries the quotation and where it came from. The owner is agreeing to a
  selection as much as to a sentence, and that is the part he could not
  otherwise check.
- Ask **when it comes up**, not at the end. The owner, 2026-09-08: *"this is like
  doing vacation homework at the last day of vacation."*
- Every option but **Yes** and **No** loops back to step 1 and asks again. They
  are not a no.
---

## 3. Write

One command per act, so neither can be performed while meaning the other.

```bash
# after a FACT Button
memex note <shelf/book> "<statement>" --agreed                 # fact
memex note <shelf/book> "<new>" --agreed --replaces "<old>"    # correction
memex new  <shelf/slug> --title "<T>" --text "<S>" \
           --type <type> --about <a,b> [--vault]               # new Book

# after a TIE Button
memex tie  <trails/route> <shelf/book> --why "<the QUOTED reason>"

# either, when it came off the queue
memex pending --accept <id>          # routes itself: a fact to its Book,
                                     # a step to its route
memex reindex                        # or it is unsearchable
```

`--agreed` is a claim that **the owner said yes in this session**. Never set it
because the fact looks right, because it is obviously true, or because he
would probably agree. If the Button was not pressed, the flag is a lie.

**The owner away** (background job, headless, no one to answer):

```bash
memex note <shelf/book> "<statement>"      # queues, outside the Library
```

It waits in `state/candidates.jsonl` and never touches a Book. The Stop hook
raises it every turn until it is asked.

---

## Then

A fact nobody can reach by a route is in the Library and on nobody's path.
So after a FACT lands, look at whether it made a tie worth pressing.

```bash
memex trail --through <shelf/book>     # which routes already cross it
memex trail --unexplained              # ties nobody has reasoned about yet
memex open                             # what is waiting — ties listed first
```

You do not have to hunt for these. `memex daily` walks the whole Library once a
day, finds ties whose reason is **already written down somewhere**, and queues
them as TIE Buttons. It calls no model and costs nothing. What it cannot find a
written reason for stays in the backlog — never turned into a writing task.

---

## A paper, article or essay

`sources/`, with `kind: paper`. Keep **the original, or an exact pointer to it** — a summary alone
cannot be checked against the source. Then the abstract of what it
establishes. The owner's comments and yours are kept separate and dated. A wrong
reading is answered by a later comment, never edited away.
