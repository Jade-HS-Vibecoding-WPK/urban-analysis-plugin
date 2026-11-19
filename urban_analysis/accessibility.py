"""Accessibility, stage 1: distance as the crow flies (M20, E26, E34).

QGIS-free like ``data_pipeline.py``.  For every object of the origin
categories (buildings by default) the distance from its centre to the
nearest chosen target (e.g. "Nahversorgung" or only "Supermarkt") is
measured in the project CRS, and whether it lies within each radius
(300 m / 500 m by default, ``mapping_rules.json`` → ``erreichbarkeit``).

The results become extra columns of the origin objects
(``HarmonizedRecord.extra_attributes``), e.g. "Abstand Supermarkt (m)" and
"Supermarkt bis 300 m" = "ja"/"nein", so they appear in the attribute table
and can colour the buildings.  Circles around the targets are drawn in QGIS
(W16) from ``target_records``.
"""

from __future__ import annotations

import bisect
import json
import math
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .contracts import ValidationIssue
from .data_pipeline import HarmonizedRecord, _count
from .geometry import GeometryError, Point, read_geometry, representative_point
from .mapping import RULES_FILE


@dataclass(frozen=True)
class AccessibilitySettings:
    radii_m: Tuple[int, ...] = (300, 500)
    origin_categories: Tuple[str, ...] = ("Gebäude",)
    target_categories: Tuple[str, ...] = ()
    # object type of an area -> (target category, subtype), e.g. hospital grounds
    area_targets: Mapping[str, Tuple[str, str]] = field(default_factory=dict)


@dataclass(frozen=True)
class TargetChoice:
    """What the user chose in W16: a category and optionally some subtypes.

    ``subtypes`` are object types such as "Supermarkt"; empty means all
    targets of the category.
    """

    category: str
    subtypes: Tuple[str, ...] = ()

    @property
    def label(self) -> str:
        return ", ".join(self.subtypes) if self.subtypes else self.category


def load_settings(path: Optional[Path] = None) -> AccessibilitySettings:
    """Radii and categories from ``mapping_rules.json`` → ``erreichbarkeit``."""
    data = json.loads(Path(path or RULES_FILE).read_text(encoding="utf-8")).get("erreichbarkeit", {})
    return AccessibilitySettings(
        radii_m=tuple(int(value) for value in data.get("radien_m", (300, 500))),
        origin_categories=tuple(data.get("ausgang_kategorien", ("Gebäude",))),
        target_categories=tuple(data.get("ziel_kategorien", ())),
        area_targets={
            str(object_type): (str(target[0]), str(target[1]))
            for object_type, target in data.get("flaechen_als_ziele", {}).items()
            if not str(object_type).startswith("_")
        },
    )


def _target_kind(record: HarmonizedRecord, settings: AccessibilitySettings) -> Optional[Tuple[str, str]]:
    """(category, subtype) if ``record`` can be a target, else ``None``."""
    category = record.attributes.get("category")
    object_type = record.attributes.get("object_type")
    if category in settings.target_categories:
        return str(category), str(object_type or category)
    return settings.area_targets.get(str(object_type)) if object_type else None


def _point(record: HarmonizedRecord) -> Optional[Point]:
    try:
        geometry = read_geometry(record.geometry)
    except GeometryError:
        return None
    return representative_point(geometry) if geometry is not None else None


def target_choices(
    records: Sequence[HarmonizedRecord], settings: Optional[AccessibilitySettings] = None
) -> Dict[str, List[Tuple[str, int]]]:
    """Targets present in the data, for the selection in W16.

    ``{"Nahversorgung": [("Bäckerei", 3), ("Supermarkt", 5)], …}`` – only
    categories from the settings that occur, subtypes sorted by name.
    """
    settings = settings or load_settings()
    counts: Dict[str, Dict[str, int]] = {}
    for record in records:
        kind = _target_kind(record, settings)
        if kind is not None:
            category, subtype = kind
            by_type = counts.setdefault(category, {})
            by_type[subtype] = by_type.get(subtype, 0) + 1
    return {
        category: sorted(counts[category].items())
        for category in settings.target_categories
        if category in counts
    }


def target_records(
    records: Sequence[HarmonizedRecord],
    choice: TargetChoice,
    settings: Optional[AccessibilitySettings] = None,
) -> List[HarmonizedRecord]:
    """The records that count as targets for ``choice`` (e.g. for circles in QGIS).

    Points of the target categories and areas listed in ``flaechen_als_ziele``
    (e.g. hospital grounds count as "Gesundheit" / "Krankenhaus").
    """
    settings = settings or load_settings()
    found = []
    for record in records:
        kind = _target_kind(record, settings)
        if kind and kind[0] == choice.category and (not choice.subtypes or kind[1] in choice.subtypes):
            found.append(record)
    return found


class _Nearest:
    """Nearest-point search: targets sorted by x, scanned outwards."""

    def __init__(self, points: Sequence[Point]):
        self.points = sorted(points)
        self.xs = [x for x, _ in self.points]

    def distance(self, point: Point) -> float:
        x, y = point
        best = math.inf
        right = bisect.bisect_left(self.xs, x)
        left = right - 1
        while left >= 0 or right < len(self.points):
            if right < len(self.points):
                dx = self.xs[right] - x
                if dx > best:
                    right = len(self.points)
                else:
                    best = min(best, math.hypot(dx, self.points[right][1] - y))
                    right += 1
            if left >= 0:
                dx = x - self.xs[left]
                if dx > best:
                    left = -1
                else:
                    best = min(best, math.hypot(dx, self.points[left][1] - y))
                    left -= 1
        return best


def _looks_geographic(points: Sequence[Point]) -> bool:
    """Degrees instead of metres: all coordinates within ±180/±90."""
    return bool(points) and all(abs(x) <= 180 and abs(y) <= 90 for x, y in points)


def add_air_distance(
    records: Sequence[HarmonizedRecord],
    choice: TargetChoice,
    settings: Optional[AccessibilitySettings] = None,
) -> Tuple[List[HarmonizedRecord], List[ValidationIssue]]:
    """Distance to the nearest target for every origin object (stage 1).

    Adds to ``extra_attributes`` of each origin object
    "Abstand <label> (m)" (whole metres) and one "<label> bis <r> m"
    ("ja"/"nein") per radius.  Returns the records and visible hints:
    a summary, or a warning if there are no targets or the coordinates are
    not in metres (then nothing is added).  Can be called once per choice;
    the column names keep the choices apart.
    """
    settings = settings or load_settings()
    targets = [point for point in map(_point, target_records(records, choice, settings)) if point is not None]
    label = choice.label
    if not targets:
        return list(records), [
            ValidationIssue(
                code="no-accessibility-targets",
                message=f"Im Gebiet gibt es keine Ziele „{label}“. Die Abstände wurden nicht berechnet.",
                severity="warning",
                rule="Erreichbarkeit (Luftlinie)",
                action="Andere Ziele wählen oder das Gebiet vergrößern.",
            )
        ]
    if _looks_geographic(targets):
        return list(records), [
            ValidationIssue(
                code="accessibility-needs-metres",
                message=(
                    "Die Abstände können nicht in Metern berechnet werden, weil das Projekt-KBS "
                    "in Grad rechnet."
                ),
                severity="error",
                rule="Erreichbarkeit (Luftlinie)",
                action="In Schritt 1 ein Projekt-KBS in Metern wählen, z. B. EPSG:25832.",
            )
        ]

    nearest = _Nearest(targets)
    distance_column = f"Abstand {label} (m)"
    radius_columns = [(radius, f"{label} bis {radius} m") for radius in settings.radii_m]
    within = {radius: 0 for radius in settings.radii_m}
    origins = 0
    updated: List[HarmonizedRecord] = []
    for record in records:
        point = (
            _point(record) if record.attributes.get("category") in settings.origin_categories else None
        )
        if point is None:
            updated.append(record)
            continue
        metres = nearest.distance(point)
        extra: Dict[str, Any] = dict(record.extra_attributes)
        extra[distance_column] = int(round(metres))
        for radius, column in radius_columns:
            inside = metres <= radius
            extra[column] = "ja" if inside else "nein"
            within[radius] += inside
        origins += 1
        updated.append(replace(record, extra_attributes=extra))

    issues: List[ValidationIssue] = []
    if not origins:
        issues.append(
            ValidationIssue(
                code="no-accessibility-origins",
                message=(
                    f"Es gibt keine {', '.join(settings.origin_categories)} im Gebiet, für die "
                    f"der Abstand zu „{label}“ berechnet werden kann."
                ),
                severity="warning",
                rule="Erreichbarkeit (Luftlinie)",
            )
        )
    else:
        shares = "; ".join(
            f"{round(100 * within[radius] / origins)} % höchstens {radius} m" for radius in settings.radii_m
        )
        issues.append(
            ValidationIssue(
                code="accessibility-summary",
                message=f"Erreichbarkeit „{label}“ (Luftlinie): {shares} vom nächsten Ziel entfernt.",
                severity="info",
                rule="Erreichbarkeit (Luftlinie)",
                details=(
                    f"Gemessen vom Mittelpunkt von {_count(origins)} Objekten zum nächsten von "
                    f"{_count(len(targets))} Zielen, als Luftlinie. Der echte Fußweg ist länger. "
                    "Ziele außerhalb des geladenen Gebiets fehlen; am Rand können Abstände "
                    "deshalb zu groß sein."
                ),
            )
        )
    return updated, issues
