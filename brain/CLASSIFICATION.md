---
title: "CLASSIFICATION — the shelf and the facets"
type: resolver
created: 2026-09-09
---

# CLASSIFICATION

**Read this with [[RESOLVER]] before creating or moving a Book.** RESOLVER
decides *whether* a Book exists and what it is called. This file decides *where
it sits* and *what it is tagged with*, and those are two different questions
that were one question until they were separated.

Bush §6: ordinary indexing does not disappear. *"He can add marginal notes and
comments… just as though he had the physical page before him."* The Memex keeps
normal lookup and puts association **on top of** it. This file is the normal
lookup. [[concepts/links-and-trails]] is the layer above.

---

## The two layers

Library science runs both, and they are not alternatives:

| Layer | Rule | Here |
|---|---|---|
| **Classification** | one Book → **one** place | the shelf |
| **Descriptors** | one Book → **many** terms | the facets in frontmatter |

A classification answers *where is it kept*. Descriptors answer *what is it
about*. Using one for both jobs is what produced, in the Library this system was
built for, 20 shelves for 58 Books — nine of them holding a single Book, and one
person filed on eight shelves at once.

## Why faceted, and not Dewey

An **enumerative** scheme (Dewey, Library of Congress) pre-lists every subject
and assigns each item one slot. It can represent only one aspect of a subject at
a time. It exists because a physical book occupies one physical shelf.

A **faceted** scheme (Ranganathan, *Colon Classification*, 1933) does not list
subjects at all. It lists **dimensions**, and a subject is assembled from them.

The Library has no physical shelf. The constraint that justified enumeration
does not apply, so the Library is faceted. The shelf survives only as *one*
facet, chosen as the primary one because a file must live at a path.

---

## Layer 1 — the shelf

> **The shelf is the Book's `type:`. Always. No judgment call.**

This is mechanical, and that is the point: a rule that needs taste produces a
different answer each time it is applied.

| Shelf | `type:` | Holds |
|---|---|---|
| `people/` | `person` | a human being |
| `projects/` | `project` | a workstream |
| `research/` | `research` | a campaign, its numbers and what they showed |
| `concepts/` | `concept` | a defined idea the rest of the Library leans on |
| `writing/` | `writing` | a manuscript, a site, anything drafted for readers |
| `infra/` | `infra` | a machine, service or runtime and how it behaves |
| `sources/` | `source` | something someone else wrote |
| `notes/` | `note` | standing guidance that is not any of the above |
| `trails/` | — | **routes, not Books.** The one exemption, below. |
| root | `resolver` | this file, [[RESOLVER]], [[schema]] |

`trails/` is exempt because a trail is not a Book: it is the ordered route
*between* Books, and it has no subject of its own to be classified by. See
[[concepts/links-and-trails]].

**If a Book's type changes, the Book moves.** That is not a special case; it is
the rule restating itself.

## Layer 2 — the facets

Everything the shelf used to encode now lives in frontmatter, where a Book can
carry more than one value and `memex recall` can read them.

```yaml
---
title: "Human-readable name"
type: project                 # = the shelf. Required.
created: 2026-09-09           # Required, a real date.
about: [greenhouse, memex]    # Topic. The tie that replaces the shelf.
status: active                # active | archived | inbox. Omit when active.
visibility: vault             # vault or absent. THE ONLY privacy mechanism.
kind: paper                   # sources/ only: paper | reference
domain: [I.2.7]               # ACM CCS 2012. sources/, research/, writing/.
---
```

### `about:` — the topic facet

A list of subject slugs. **This is what replaces the scattered shelves.** Six
Books about one person sat on six shelves; they now sit on one shelf and carry
`about: [owner]`, which is a single query instead of six directories.

Values are a controlled list, not free text. The terms below are the **example**
vocabulary shipped with this repo — replace them with your own subjects:

<!-- about-terms:begin -->
`owner` · `agent` · `memex` · `greenhouse` · `home-server`
<!-- about-terms:end -->

**Adding a term is an edit to this file, made before it is used.** An
uncontrolled vocabulary is not a vocabulary; it is a tag cloud, and it fails
silently by putting two spellings of one subject in two places.

That is enforced, not asked for: `memex/edits.py` reads the list **between the
markers above** and refuses a `new` Book carrying a term that is not in it. The
markers are why the prose around the list can change freely. If the block is
missing or empty the read raises rather than allowing everything through — a
vocabulary check that fails open is not a check.

### `status:` — the lifecycle facet

`active` (the default, and omitted) · `archived` · `inbox`.

This replaces the `archive/` and `inbox/` shelves:

- **`archived`** — dead or superseded. Set the facet, never delete the Book.
  Archived means *retired*, not *private*; a sensitive Book retires with its
  `visibility: vault` intact.
- **`inbox`** — an unsorted capture that matched no rule. **Temporary.** A Book
  sitting at `inbox` means this file needs to evolve; it is not a dumping ground.

### `visibility:` — the privacy facet

`vault`, or absent. **This is the only mechanism that decides privacy.**

An earlier design encoded privacy twice: once here, and once in the *names* of
eight shelves, with `memex/edits.py` holding a hardcoded shelf list to match.
The two could disagree, and the shelf half could be defeated by moving a file.
The shelf half is gone. The guard in `edits.py` now keys on `type: person` and
on `about:` naming a person, which travels with the Book.

Unchanged from RESOLVER Test 0 — **always vault, no judgment call:** any Book
about a human being, the owner included; identity; anything authored by or about
a third party; personal material — health, family, private reflection; and the
sensitive half of infra.

### `kind:` — sources only

`paper` (a published work, kept with its original) or `reference` (documentation,
a technique writeup, an API). The rules for what a paper's Book must hold are in
`sources/README.md`.

### `domain:` — the external vocabulary

**ACM Computing Classification System (2012)** terms, on `sources/`, `research/`
and `writing/` Books only. CCS is the de facto standard subject vocabulary for
computing, a four-level poly-hierarchy published as SKOS — comparable to MSC for
mathematics. It is here so that the Library's research half can be addressed in
the same terms as the literature it cites.

Optional everywhere, and deliberately so: on a Book about someone's daily
routine it would be noise. Omit it rather than invent one.

---

## Creating a Book

1. **[[RESOLVER]] Test 0 first** — visibility.
2. **`type:` decides the shelf.** Look it up in the table. Do not deliberate.
3. **`about:` from the controlled list.** If the term does not exist, add it to
   this file first.
4. `status:` only if not `active`. `kind:`/`domain:` where they apply.
5. One Book per subject; one shelf per Book; many facets per Book.

## Editing a Book

- **Changing facets is an ordinary edit.** They sit above the line, in the
  compiled-truth layer, and are rewritten as the truth changes.
- **Changing `type:` moves the file.** Move it, then rewrite every wiki-link
  that pointed at the old slug, then `memex reindex`, then `memex doctor` — the
  broken-link check is check 1, and it exists because a rename left dead links
  behind.
- **Never encode a facet in a directory name again.** That is the defect this
  file was written to end. A new shelf is a change to the table above, and the
  table is `type:`, which is a closed set in `memex/edits.py`. Adding a shelf
  therefore means adding a type, in code, on purpose.

## What this does not touch

Links, `## See Also`, `## Trail`, `## Timeline` and everything in `trails/` are
**unchanged**. Reclassification moves where a Book is stored; it does not touch
what it is tied to or why. Bush keeps LINK and TRAIL separate from INDEX, and so
does this.

## See Also

[[RESOLVER]] · [[schema]] · [[concepts/links-and-trails]] ·
[[sources/as-we-may-think]]
