---
title: "RESOLVER — master decision tree"
type: resolver
created: 2026-09-09
---

# RESOLVER — the master decision tree

**Read this before creating any Book. Not optional.**

Two gates, in order. First **which visibility** (Test 0), then **which type**
(Test 1). One Book per subject, one home per Book.

## The words

| Term | Means |
|---|---|
| **MEMEX** | the whole system. Not a directory. |
| **the Library** | the markdown files under `brain/`. One collection, one index. |
| **a Book** | one markdown file. One project, one person, one idea. |
| **an Entity** | a Book that is a *someone* — a person, an org. Every Entity is a Book; most Books are not Entities. Test 0 sends every one of them to `vault`. |
| **a Shelf** | one directory of the Library — `projects/`, `people/`. |
| **a Program** | a Book shaped as a hub: a workstream running for months whose detail lives in other Books. |
| **vault** | a frontmatter label, `visibility: vault`. The agent reads it; nothing so marked leaves the machine. |
| **the Button** | the moment the owner is shown one exact sentence and one exact destination and says yes. Bush §7, the press that ties. **The only way anything enters a Book.** [[concepts/links-and-trails]]. |
| **a Trail** | the ordered, reasoned route between Books. `trails/`. **Open** = still being walked; **closed** = the Learned line says where it arrived. |
| **a Book's `## Trail`** | the appendix below the `---` in one Book: *why* it went this way, as against `## Timeline`, which is *what happened*. It is not a route — a route lives in `trails/`. The two share a word and nothing else. |
| **the Scribe** | `memex scribe`. Reads a finished session and records only what is checkable. `scribe/PROMPT.md`. |
| **the index** | `state/recall-index.json`, behind `memex recall`. A cache. Delete it and rebuild; it is never the record. |

Full definitions: [[concepts/memex-glossary]]. Link vs trail — the two that get
confused, and the file to read before writing either:
[[concepts/links-and-trails]].

Do not coin new terms for these. If a term is missing, add it there first.

---

## Test 0 — which visibility?

> **Would this harm someone, or profile the owner, if it left this machine?**
> Yes → `visibility: vault` in the Book's frontmatter. No → no label.

One Library, one index. The agent reads everything. The label is not a wall; it
is a mark that the **exits** enforce: nothing marked `vault` is pushed,
exported, served to another surface, or quoted to anyone but the owner. See
`ACCESS_POLICY.md`.

**Always `vault`, no judgment call:**

- Any Book about a **human being** — the owner included. `people/`, or `notes/`
  with `about:` naming them.
- **Identity** — the agent's persona file, the owner's profile, interview answers.
- **Standing guidance about a person** — how the owner wants to be worked with,
  what they are committed to, their routine. `notes/`, `about: [owner]`.
- **Relationships**, **email**, and anything else authored by or about a third
  party. They never agreed to leave the machine. This is a rule, not a risk
  calculation.
- **Personal** material — health, family, private reflection.
- **The sensitive half of infra.**

Privacy is a property of the **Book**, never of its path. An earlier design
encoded it in eight shelf names with a matching list of directories in
`memex/edits.py`; moving a file moved it out of the guard's reach.
`visibility: vault` is now the only thing that marks a Book sensitive, and the
code guard keys on `type: person` and on `about:` naming a person — both of
which travel with the Book. See [[CLASSIFICATION]].

**Never in any Book, labeled or not:** key fingerprints, cloud resource ids, IP
addresses, tokens, passwords. A `vault` label does not make a secret
admissible; secrets are not knowledge. They are recoverable from the systems
that own them. Record *where* to recover one, never the value.

---

## Test 1 — which type?

**The shelf is the `type:`.** Answer this once and the shelf is decided; there
is no second question. Full table and the facets that go with it:
[[CLASSIFICATION]].

1. Is it a **human being**? → `person` → `people/`, `visibility: vault`
2. Is it a **measured result, label set, calibration figure, or a claim that
   will appear in a report**? → `research` **(APPEND-ONLY — see below)**
3. Is it a **machine, server, network, or an environment gotcha** (a trap that
   bites you if you forget it)? → `infra`
4. Is it **being actively built** — has a repo, a spec, or a deadline? → `project`
5. Is it a **finished prose artifact** — an essay, a draft, a post? → `writing`
6. Is it a **mental model or framework you would teach someone**? → `concept`
7. Is it something **someone else wrote** — a paper, an API doc, a snapshot?
   → `source`, plus `kind: paper|reference`
8. Is it **standing guidance** that is none of the above — how to work, what to
   hold to? → `note`
9. Is it a **question pursued over time** — a route through other Books, with
   what was learned? → `trails/`. This is a trail, and it is not a Book.

Then set the facets: `about:` always, `status:` if not active, `visibility:`
per Test 0, `kind:`/`domain:` where they apply.

**There is no `inbox/`, `personal/` or `archive/` shelf.** They were lifecycle
and privacy wearing a directory's clothes:

- unsorted → `status: inbox`. Temporary, and a signal the rules need to change.
- dead or superseded → `status: archived`. Never delete; retag.
- private → `visibility: vault` on whatever shelf the subject belongs to.

## Disambiguation

- **projects/ vs research/** — the thing being built is a project; the number it
  produced is research. The sensor rig is `projects/`; "18 of 24 germinated" is
  `research/`.
- **projects/ vs infra/** — if it is the subject of the work, `projects/`. If it
  is the machine the work runs on, `infra/`.
- **concepts/ vs writing/** — a framework in your head is `concepts/`. A finished
  piece someone else reads is `writing/`.
- **`status: archived` vs `visibility: vault`** — archived means *retired*, vault
  means *sensitive*. Two facets, and a Book can carry both. Never say "archived"
  to mean "sensitive"; a shelf named `archive/` kept inviting that conflation,
  which is part of why it is gone.
- **A rule is never its own Book.** Rules about how to work attach to the Book
  they govern: project-scoped rules go in that project's `## Rules` block,
  global working preferences go on [[notes/owner-preferences]].

## The append-only rule for research/

Books in `research/` have NO compiled-truth layer that an agent may rewrite.
Timeline only. An agent may **flag** a contradiction between two results; only
the owner resolves one. An agent that reconciles two conflicting results has
destroyed evidence.

Every other shelf follows the standard two-layer Book: compiled truth above the
`---`, append-only appendix below.

## See Also

[[CLASSIFICATION]] · [[schema]] · [[concepts/links-and-trails]] ·
[[concepts/memex-glossary]] · [[sources/as-we-may-think]]
