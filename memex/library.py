"""The Library: every Book under brain/, read straight from disk."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

# MEMEX_ROOT exists so the CLI can be pointed at a throwaway Library. Without
# it every command-line path was untestable: the tests drove apply_op directly
# and never went through main(), which is how a dangling reference crashed
# `memex note` AFTER a successful write while 126 checks passed.
# The OWNER's timezone, not the machine's. A date written into a Book is the
# date of the owner's day; a server in another zone would file an evening's
# work under tomorrow and the Timeline would read wrong forever after. One
# definition, imported everywhere, so the two can never drift apart.
TZ = ZoneInfo(os.environ.get("MEMEX_TZ") or "UTC")

ROOT = Path(os.environ.get("MEMEX_ROOT") or Path(__file__).resolve().parent.parent)
BRAIN = ROOT / "brain"
STATE = ROOT / "state"

_FM = re.compile(r"\A---\n(.*?)\n---\n", re.S)

# brain/CLASSIFICATION.md: the shelf IS the Book's type. One map, in one place,
# so the rule is a fact in code rather than a convention in prose -- the old
# arrangement was prose only, and it drifted into 20 shelves for 58 Books.
# `resolver` maps to the root, and trails/ holds routes rather than Books.
SHELF = {"person": "people", "project": "projects", "research": "research",
         "concept": "concepts", "writing": "writing", "infra": "infra",
         "source": "sources", "note": "notes", "resolver": ""}


@dataclass
class Book:
    slug: str                 # "people/owner"
    path: Path
    title: str
    type: str
    visibility: str           # "" or "vault"
    frontmatter: dict
    body: str                 # everything after the frontmatter

    @property
    def vault(self) -> bool:
        return self.visibility == "vault"

    @property
    def above_the_line(self) -> str:
        """Compiled truth: the body up to the first horizontal rule."""
        parts = re.split(r"\n---\n", self.body, maxsplit=1)
        return parts[0]

    def section(self, heading: str) -> str:
        """Text under a '## heading' up to the next '## ' or end."""
        m = re.search(rf"^## {re.escape(heading)}\s*\n(.*?)(?=^## |\Z)", self.body, re.S | re.M)
        return m.group(1).strip() if m else ""

    def links(self) -> list[str]:
        return sorted(set(re.findall(r"\[\[([^\]|#]+)", self.body)))


def read_book(path: Path) -> Book | None:
    text = path.read_text(encoding="utf-8")
    m = _FM.match(text)
    if not m:
        return None
    try:
        fm = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError:
        return None
    if not isinstance(fm, dict):
        return None
    slug = path.relative_to(BRAIN).with_suffix("").as_posix()
    return Book(
        slug=slug,
        path=path,
        title=str(fm.get("title", slug)),
        type=str(fm.get("type", "")),
        visibility=str(fm.get("visibility", "") or ""),
        frontmatter=fm,
        body=text[m.end():],
    )


def books(include_resolvers: bool = False) -> list[Book]:
    out = []
    for p in sorted(BRAIN.rglob("*.md")):
        b = read_book(p)
        if b is None:
            continue
        if not include_resolvers and b.type == "resolver":
            continue
        out.append(b)
    return out


def get(slug: str) -> Book | None:
    p = BRAIN / f"{slug}.md"
    return read_book(p) if p.exists() else None


def shelves() -> list[str]:
    return sorted(p.name for p in BRAIN.iterdir() if p.is_dir())


_ABOUT_BLOCK = re.compile(r"<!-- about-terms:begin -->(.*?)<!-- about-terms:end -->", re.S)


def about_terms(brain: Path | None = None) -> set[str]:
    """The controlled vocabulary for `about:`, read from CLASSIFICATION.md.

    The doc is the record: it says adding a term is an edit to that file made
    BEFORE the term is used, so the file is where the list has to live. Parsed
    between explicit markers so the prose around it stays free to change.

    Raises rather than returning empty. A vocabulary check that fails open is
    not a check -- it silently readmits the tag cloud the list exists to stop.

    `brain` is explicit so a caller that has swapped its own BRAIN (the tests
    do) reads ITS Library, not the real one sitting on disk beside it.
    """
    root = brain or BRAIN
    try:
        text = (root / "CLASSIFICATION.md").read_text(encoding="utf-8")
    except FileNotFoundError:
        raise RuntimeError(f"{root}/CLASSIFICATION.md is missing -- it carries "
                           "the `about:` vocabulary and nothing can be filed "
                           "without it") from None
    m = _ABOUT_BLOCK.search(text)
    terms = set(re.findall(r"`([a-z0-9-]+)`", m.group(1))) if m else set()
    if not terms:
        raise RuntimeError(
            "no `about:` vocabulary between the about-terms markers in "
            f"{root}/CLASSIFICATION.md -- refusing to accept any term")
    return terms


def person_subjects(brain: Path | None = None) -> set[str]:
    """Subject slugs that name a human, derived from the people/ shelf.

    Was a hardcoded {owner, agent} in edits.py, which meant the vault
    guard silently stopped covering anyone who was not one of those three --
    the same "privacy is a property of a name we wrote down once" defect the
    shelf list had. A person Book declares its own subject slug in `about:`,
    so filing one extends the guard with no code change.

    `agent` is seeded: the identity Book is on notes/, not people/, because
    the agent is not a human -- but SOUL.md is vault and must stay that way.
    """
    out = {"agent"}
    d = (brain or BRAIN) / "people"
    if d.is_dir():
        for p in sorted(d.glob("*.md")):
            if p.stem == "README":
                continue
            out.add(p.stem)
            # Frontmatter parsed directly, not via read_book(): that derives a
            # slug relative to the module-level BRAIN and raises on a Library
            # passed in as `brain`, which is exactly the case here.
            m = _FM.match(p.read_text(encoding="utf-8"))
            if not m:
                continue
            try:
                fm = yaml.safe_load(m.group(1)) or {}
            except yaml.YAMLError:
                continue
            a = fm.get("about") or [] if isinstance(fm, dict) else []
            out.update(a if isinstance(a, list) else [str(a)])
    return out
