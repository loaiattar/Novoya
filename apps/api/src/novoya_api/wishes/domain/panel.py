from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

DEFAULT_SECTION = "preferences"


@dataclass(frozen=True, slots=True)
class Tag:
    id: str
    label: str
    preselected: bool = False


@dataclass(frozen=True, slots=True)
class PanelSection:
    id: str
    title: str
    multi: bool
    tags: tuple[Tag, ...]


@dataclass(frozen=True, slots=True)
class Panel:
    """The preference panel: sections of tags to pick, then budget, travellers and dates.

    The frontend renders it from to_dict() and never needs to know which sections exist."""

    sections: tuple[PanelSection, ...]
    ask_budget: bool = True
    ask_persons: bool = True
    ask_dates: bool = True

    @classmethod
    def from_tags(cls, tags: Iterable[str]) -> "Panel":
        """The fallback panel, built from the tags of the offers at the destination.

        Tags are "section:tag" ("style:beach"); a tag without a section goes to
        "preferences"."""
        grouped: dict[str, list[str]] = {}
        for raw in tags:
            split = _split_catalog_tag(raw)
            if split is None:
                continue
            section, tag = split
            if tag not in grouped.setdefault(section, []):
                grouped[section].append(tag)
        return cls(
            sections=tuple(
                PanelSection(
                    id=section,
                    title=_label(section),
                    multi=True,
                    tags=tuple(Tag(id=tag, label=_label(tag)) for tag in section_tags),
                )
                for section, section_tags in grouped.items()
                if section_tags
            )
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Panel":
        """The panel saved by to_dict(), so the answers are checked against what was shown."""
        return cls(
            sections=tuple(
                PanelSection(
                    id=section["id"],
                    title=section["title"],
                    multi=section["multi"],
                    tags=tuple(
                        Tag(id=tag["id"], label=tag["label"], preselected=tag["preselected"])
                        for tag in section["tags"]
                    ),
                )
                for section in data["sections"]
            ),
            ask_budget=data["ask_budget"],
            ask_persons=data["ask_persons"],
            ask_dates=data["ask_dates"],
        )

    def restricted_to(self, tags: Iterable[str]) -> "Panel":
        """Keep only tags that exist on the offers; drop empty sections.

        Catalog tags are "section:tag". The LLM JSON uses separate section and tag ids."""
        allowed = _catalog_keys(tags)
        kept: list[PanelSection] = []
        seen: set[str] = set()
        for section in self.sections:
            tags_kept: list[Tag] = []
            for tag in section.tags:
                key = f"{section.id.strip().lower()}:{tag.id.strip().lower()}"
                if key in allowed and key not in seen:
                    seen.add(key)
                    tags_kept.append(tag)
            if tags_kept:
                kept.append(
                    PanelSection(section.id, section.title, section.multi, tuple(tags_kept))
                )
        return Panel(tuple(kept), self.ask_budget, self.ask_persons, self.ask_dates)

    def section(self, section_id: str) -> PanelSection | None:
        return next((section for section in self.sections if section.id == section_id), None)

    def to_dict(self) -> dict[str, Any]:
        """The JSON shape of ARCHITECTURE.md section 3."""
        return {
            "sections": [
                {
                    "id": section.id,
                    "title": section.title,
                    "multi": section.multi,
                    "tags": [
                        {"id": tag.id, "label": tag.label, "preselected": tag.preselected}
                        for tag in section.tags
                    ],
                }
                for section in self.sections
            ],
            "ask_budget": self.ask_budget,
            "ask_persons": self.ask_persons,
            "ask_dates": self.ask_dates,
        }


def _split_catalog_tag(raw: str) -> tuple[str, str] | None:
    section, _, tag = raw.strip().lower().rpartition(":")
    section, tag = section.strip() or DEFAULT_SECTION, tag.strip()
    if not tag:
        return None
    return section, tag


def _catalog_keys(tags: Iterable[str]) -> set[str]:
    keys: set[str] = set()
    for raw in tags:
        if split := _split_catalog_tag(raw):
            keys.add(f"{split[0]}:{split[1]}")
    return keys


def _label(identifier: str) -> str:
    text = identifier.replace("_", " ").replace("-", " ")
    return text[:1].upper() + text[1:]
