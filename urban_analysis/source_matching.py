"""Compare objects from different sources, e.g. ALKIS and OSM (S12, E12, E19).

Two areas of the same category from different sources are *probably the
same* object when the centre of one lies inside the other and their areas
differ by at most 30 % – or by at most 50 % if each centre lies inside the
other (``mapping_rules.json`` → ``quellen_abgleich``).  OSM often cuts
buildings differently from ALKIS, so a fixed 20 % left half of all pairs
uncertain.  If a centre lies inside but the areas differ more, the group is
*uncertain* and only counts after the user confirmed it.

``match_sources`` marks the records (``HarmonizedRecord.source_match``) and
returns one readable group per match; ``priority_choices`` gives step 6 the
numbers per category and the suggested source; ``apply_source_priority``
keeps, per group, only the objects of the chosen source.  Objects without a
partner in another source always stay.  Pure Python, no extra packages.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from .contracts import ValidationIssue
from .data_pipeline import HarmonizedRecord, _count
from .geometry import BBox, Geometry, GeometryError, point_in_geometry, polygon_area, read_geometry, representative_point
from .mapping import RULES_FILE


GRID_CELL_M = 100.0


@dataclass(frozen=True)
class MatchSettings:
    max_area_deviation: float = 0.3
    # Higher limit when each centre lies inside the other area.
    max_area_deviation_mutual: float = 0.5
    # category -> suggested source kind (E19)
    suggested_priority: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SourceMatch:
    """One group of probably identical objects from different sources."""

    group_id: str
    category: str
    record_count: int
    source_kinds: Tuple[str, ...]
    certain: bool
    # largest area difference between two partners, 0.25 = 25 %
    area_deviation: float


@dataclass(frozen=True)
class PriorityChoice:
    """What step 6 shows per category (W12): counts and the suggested source."""

    category: str
    source_kinds: Tuple[str, ...]
    suggested_source: str
    group_count: int
    uncertain_count: int
    record_count: int


def load_settings(path: Optional[Path] = None) -> MatchSettings:
    """Threshold and suggested priority from ``mapping_rules.json``."""
    data = json.loads(Path(path or RULES_FILE).read_text(encoding="utf-8")).get("quellen_abgleich", {})
    deviation = float(data.get("max_flaechen_abweichung", MatchSettings.max_area_deviation))
    mutual = float(data.get("max_flaechen_abweichung_gegenseitig", MatchSettings.max_area_deviation_mutual))
    for name, value in (("max_flaechen_abweichung", deviation), ("max_flaechen_abweichung_gegenseitig", mutual)):
        if not 0 <= value < 1:
            raise ValueError(f"{name} muss zwischen 0 und 1 liegen")
    return MatchSettings(
        max_area_deviation=deviation,
        max_area_deviation_mutual=max(mutual, deviation),
        suggested_priority={
            str(category): str(kind)
            for category, kind in data.get("vorrang", {}).items()
            if not str(category).startswith("_")
        },
    )


@dataclass
class _Area:
    position: int
    kind: str
    category: str
    geometry: Geometry
    bbox: BBox
    centre: Tuple[float, float]
    area: float


def _areas(records: Sequence[HarmonizedRecord]) -> List[_Area]:
    areas = []
    for position, record in enumerate(records):
        category = record.attributes.get("category")
        if not record.source_kind or not category:
            continue
        try:
            geometry = read_geometry(record.geometry)
        except GeometryError:
            continue
        if geometry is None or not geometry.polygons:
            continue
        area = polygon_area(geometry)
        centre = representative_point(geometry)
        bbox = geometry.bbox()
        if area <= 0 or centre is None or bbox is None:
            continue
        areas.append(_Area(position, record.source_kind, str(category), geometry, bbox, centre, area))
    return areas


def _cells(bbox: BBox) -> Iterable[Tuple[int, int]]:
    for x in range(math.floor(bbox[0] / GRID_CELL_M), math.floor(bbox[2] / GRID_CELL_M) + 1):
        for y in range(math.floor(bbox[1] / GRID_CELL_M), math.floor(bbox[3] / GRID_CELL_M) + 1):
            yield x, y


def _centres_inside(first: _Area, second: _Area) -> int:
    """How many of the two centres lie inside the other area (0, 1 or 2)."""
    return int(point_in_geometry(first.centre, second.geometry)) + int(
        point_in_geometry(second.centre, first.geometry)
    )


def _deviation(first: _Area, second: _Area) -> float:
    return abs(first.area - second.area) / max(first.area, second.area)


def _pair_certain(deviation: float, mutual: bool, settings: MatchSettings) -> bool:
    limit = settings.max_area_deviation_mutual if mutual else settings.max_area_deviation
    return deviation <= limit


def _pairs(areas: Sequence[_Area]) -> List[Tuple[int, int, float, bool]]:
    """Index pairs (into ``areas``) from different sources whose centre lies in the other.

    The last value says whether each centre lies inside the other area."""
    grid: Dict[Tuple[str, Tuple[int, int]], List[int]] = {}
    for index, item in enumerate(areas):
        for cell in _cells(item.bbox):
            grid.setdefault((item.category, cell), []).append(index)
    pairs = []
    seen: Set[Tuple[int, int]] = set()
    for (_, _), members in grid.items():
        for offset, first_index in enumerate(members):
            first = areas[first_index]
            for second_index in members[offset + 1:]:
                second = areas[second_index]
                key = (min(first_index, second_index), max(first_index, second_index))
                if first.kind == second.kind or key in seen:
                    continue
                seen.add(key)
                inside = _centres_inside(first, second)
                if inside:
                    pairs.append((key[0], key[1], _deviation(first, second), inside == 2))
    return pairs


def _groups(count: int, pairs: Sequence[Tuple[int, int, float, bool]]) -> List[List[int]]:
    parent = list(range(count))

    def root(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    for first, second, *_ in pairs:
        parent[root(first)] = root(second)
    members: Dict[int, List[int]] = {}
    for first, second, *_ in pairs:
        for index in (first, second):
            group = members.setdefault(root(index), [])
            if index not in group:
                group.append(index)
    return sorted((sorted(group) for group in members.values()), key=lambda group: group[0])


def match_sources(
    records: Sequence[HarmonizedRecord], settings: Optional[MatchSettings] = None
) -> Tuple[List[HarmonizedRecord], List[SourceMatch], List[ValidationIssue]]:
    """Find probably identical areas from different sources (S12).

    Returns the records with ``source_match`` set (a new list, the input is
    not changed), one ``SourceMatch`` per group and one hint per category.
    Records without a partner keep ``source_match = None``.
    """
    settings = settings or load_settings()
    areas = _areas(records)
    pairs = _pairs(areas)
    worst: Dict[int, float] = {}
    doubtful: Set[int] = set()  # members of at least one uncertain pair
    for first, second, deviation, mutual in pairs:
        for index in (first, second):
            worst[index] = max(worst.get(index, 0.0), deviation)
            if not _pair_certain(deviation, mutual, settings):
                doubtful.add(index)

    marked = [replace(record, source_match=None) if record.source_match else record for record in records]
    matches: List[SourceMatch] = []
    numbers: Dict[str, int] = {}
    for group in _groups(len(areas), pairs):
        category = areas[group[0]].category
        numbers[category] = numbers.get(category, 0) + 1
        group_id = f"{category}:{numbers[category]}"
        deviation = max(worst[index] for index in group)
        for index in group:
            position = areas[index].position
            marked[position] = replace(marked[position], source_match=group_id)
        matches.append(
            SourceMatch(
                group_id=group_id,
                category=category,
                record_count=len(group),
                source_kinds=tuple(sorted({areas[index].kind for index in group})),
                certain=not any(index in doubtful for index in group),
                area_deviation=round(deviation, 3),
            )
        )
    return marked, matches, _issues(matches, settings)


def _issues(matches: Sequence[SourceMatch], settings: MatchSettings) -> List[ValidationIssue]:
    by_category: Dict[str, List[SourceMatch]] = {}
    for match in matches:
        by_category.setdefault(match.category, []).append(match)
    percent = round(settings.max_area_deviation * 100)
    mutual_percent = round(settings.max_area_deviation_mutual * 100)
    issues = []
    for category, group in by_category.items():
        kinds = " und ".join(sorted({kind for match in group for kind in match.source_kinds}))
        uncertain = sum(not match.certain for match in group)
        message = f"{category}: " + (
            f"1 Objekt ist wahrscheinlich in {kinds} doppelt vorhanden."
            if len(group) == 1
            else f"{_count(len(group))} Objekte sind wahrscheinlich in {kinds} doppelt vorhanden."
        )
        if uncertain:
            message += f" Bei {_count(uncertain)} davon ist das unsicher."
        issues.append(
            ValidationIssue(
                code="cross-source-duplicate",
                message=message,
                action="In Schritt 6 wählen, welche Quelle für diese Kategorie gilt."
                + (" Unsichere Fälle einzeln bestätigen." if uncertain else ""),
                details=(
                    "Zwei Objekte aus verschiedenen Quellen gelten als gleich, wenn der Mittelpunkt "
                    f"des einen im anderen liegt und ihre Flächen höchstens {percent} % voneinander "
                    f"abweichen – liegen beide Mittelpunkte im jeweils anderen, sind bis zu {mutual_percent} % "
                    "erlaubt. Weichen die Flächen stärker ab, ist der Fall unsicher. Objekte, die es nur "
                    "in einer Quelle gibt, bleiben immer erhalten."
                ),
                severity="warning" if uncertain else "info",
                # The choice is made in step 6, not by a tick in step 4.
                requires_confirmation=False,
                rule="Abgleich der Quellen",
            )
        )
    return issues


def priority_choices(
    matches: Sequence[SourceMatch], settings: Optional[MatchSettings] = None
) -> List[PriorityChoice]:
    """One entry per category with matches, for the choice in step 6 (W12, E19).

    Without a suggestion in the settings file, ALKIS is suggested if present.
    """
    settings = settings or load_settings()
    by_category: Dict[str, List[SourceMatch]] = {}
    for match in matches:
        by_category.setdefault(match.category, []).append(match)
    choices = []
    for category, group in by_category.items():
        kinds = tuple(sorted({kind for match in group for kind in match.source_kinds}))
        suggested = settings.suggested_priority.get(category, "")
        if suggested not in kinds:
            suggested = "ALKIS" if "ALKIS" in kinds else kinds[0]
        choices.append(
            PriorityChoice(
                category=category,
                source_kinds=kinds,
                suggested_source=suggested,
                group_count=len(group),
                uncertain_count=sum(not match.certain for match in group),
                record_count=sum(match.record_count for match in group),
            )
        )
    return choices


def apply_source_priority(
    records: Sequence[HarmonizedRecord],
    priority: Mapping[str, str],
    matches: Sequence[SourceMatch],
    confirmed_uncertain: Iterable[str] = (),
) -> List[HarmonizedRecord]:
    """Keep, per matched group, only the objects of the chosen source (S12).

    ``priority`` maps a category to the source kind the user confirmed, e.g.
    ``{"Gebäude": "ALKIS", "Grünflächen": "OSM"}``.  Groups of categories
    without a choice, uncertain groups not in ``confirmed_uncertain`` and
    objects without a partner stay unchanged.  The input is not modified.
    """
    confirmed = set(confirmed_uncertain)
    decided: Dict[str, str] = {}
    for match in matches:
        chosen = priority.get(match.category)
        if chosen and chosen in match.source_kinds and (match.certain or match.group_id in confirmed):
            decided[match.group_id] = chosen
    return [
        record for record in records
        if record.source_match not in decided or record.source_kind == decided[record.source_match]
    ]
