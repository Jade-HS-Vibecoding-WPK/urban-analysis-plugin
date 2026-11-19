"""General map topics: catalog and classification (M25, E36, S16).

QGIS-free like ``data_pipeline.py``.  The topics, their classes, scales,
limits and source tips are data in ``topics_catalog.json``; this module only
reads them (``topic_catalog``) and sorts the harmonized records into the
classes the user ticked in step 7 (``classify_topics``).

Each record gets at most one class per selected topic
(``HarmonizedRecord.topic_classes``, topic_id -> class_id): the first class
of the topic whose rule matches wins.  Rules may check every attribute that
was read (source columns, all OSM tags in ``other_tags``) plus three own
keys: ``kategorie``, ``objektart`` and ``ebene`` (the source layer).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .contracts import (
    TOPIC_CLASS_EMPTY,
    TOPIC_LIMIT,
    PipelineResult,
    TopicClass,
    TopicInfo,
    TopicScale,
    TopicSelection,
    TopicStep,
    ValidationIssue,
)
from .data_pipeline import HarmonizedRecord
from .geometry import GeometryError, read_geometry
from .mapping import _matches, parse_tags
from .ui_contract import TOPIC_LABELS, TOPIC_NAMES

CATALOG_FILE = Path(__file__).with_name("topics_catalog.json")

# Own keys a rule may use besides the source columns and OSM tags.
OWN_KEYS = ("kategorie", "objektart", "ebene")

RULE_SOURCES = ("osm", "alkis")


@dataclass(frozen=True)
class Condition:
    """One part of a rule: ``key=pattern`` or ``key!=pattern``."""

    key: str
    pattern: str
    negated: bool = False

    def holds(self, values: Mapping[str, str]) -> bool:
        value = values.get(self.key, "")
        found = bool(value) and (self.pattern == "*" or _matches(value, self.pattern))
        return not found if self.negated else found


Rule = Tuple[Condition, ...]


@dataclass(frozen=True)
class _ClassRules:
    topic_class: TopicClass
    rules: Tuple[Rule, ...]


@dataclass(frozen=True)
class _Topic:
    info: TopicInfo
    classes: Tuple[_ClassRules, ...]


def parse_rule(text: str) -> Rule:
    """Read ``"a=b & c!=d"`` into conditions; raises ValueError if unreadable."""
    conditions = []
    for part in str(text).split("&"):
        part = part.strip()
        negated = "!=" in part
        key, sep, pattern = part.partition("!=" if negated else "=")
        key, pattern = key.strip(), pattern.strip()
        if not sep or not key or not pattern:
            raise ValueError(f"Themenregel nicht lesbar: „{text}“ (erwartet „Schlüssel=Wert“)")
        conditions.append(Condition(key, pattern, negated))
    return tuple(conditions)


def load_catalog(path: Optional[Path] = None) -> Dict[str, Any]:
    """The raw catalog file as a dictionary."""
    return json.loads(Path(path or CATALOG_FILE).read_text(encoding="utf-8"))


def _read_topics(path: Optional[Path] = None) -> List[_Topic]:
    topics: List[_Topic] = []
    for entry in load_catalog(path).get("themen", []):
        topic_id = str(entry["id"])
        if topic_id not in TOPIC_NAMES:
            raise ValueError(f"Thema „{topic_id}“ fehlt in ui_contract.TOPIC_NAMES")
        classes: List[_ClassRules] = []
        for item in entry.get("klassen", []):
            topic_class = TopicClass(
                class_id=str(item["id"]),
                name=str(item["name"]),
                geometry=str(item["geometrie"]),
                colour=str(item.get("farbe", "")),
                description=str(item.get("beschreibung", "")),
                uncertain=bool(item.get("vermutlich", False)),
            )
            rules = item.get("regeln", {})
            unknown = set(rules) - set(RULE_SOURCES)
            if unknown:
                raise ValueError(f"Klasse {topic_class.class_id}: unbekannte Regelquelle {sorted(unknown)}")
            parsed = tuple(parse_rule(text) for source in RULE_SOURCES for text in rules.get(source, ()))
            classes.append(_ClassRules(topic_class, parsed))
        ids = [item.topic_class.class_id for item in classes]
        if len(ids) != len(set(ids)):
            raise ValueError(f"Thema „{topic_id}“: Klassen-ids sind doppelt")
        scales = tuple(
            TopicScale(
                scale_id=str(scale["id"]),
                name=str(scale["name"]),
                field=str(scale["spalte"]),
                steps=tuple(
                    TopicStep(
                        name=str(step["name"]),
                        lower=step.get("von"),
                        upper=step.get("bis"),
                        colour=str(step.get("farbe", "")),
                    )
                    for step in scale.get("grenzen", ())
                ),
            )
            for scale in entry.get("stufen", ())
        )
        info = TopicInfo(
            topic_id=topic_id,
            name=TOPIC_NAMES[topic_id],
            description=str(entry.get("beschreibung", "")),
            classes=tuple(item.topic_class for item in classes),
            scales=scales,
            limits=tuple(str(text) for text in entry.get("grenzen", ())),
            source_tips=tuple(str(text) for text in entry.get("quellen_tipps", ())),
        )
        topics.append(_Topic(info, tuple(classes)))
    return topics


def topic_catalog(path: Optional[Path] = None) -> List[TopicInfo]:
    """All topics of the catalog in its order (read only, for the UI)."""
    return [topic.info for topic in _read_topics(path)]


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return str(value).strip()


def record_values(record: HarmonizedRecord) -> Dict[str, str]:
    """Everything a rule may check: OSM tags, source columns and own keys."""
    source = record.source_attributes or {}
    values = {key: _text(value) for key, value in parse_tags(source.get("other_tags")).items()}
    for key, value in source.items():
        text = _text(value)
        if text and key != "other_tags":
            values[str(key)] = text
    attributes = record.attributes or {}
    own = {
        "kategorie": attributes.get("category"),
        "objektart": attributes.get("object_type"),
        "ebene": record.source_layer or record.layer_id,
    }
    for key, value in own.items():
        values[key] = _text(value)
    return values


def geometry_kind(record: HarmonizedRecord) -> Optional[str]:
    """"Fläche", "Linie" or "Punkt"; None if there is no readable geometry."""
    try:
        geometry = read_geometry(record.geometry)
    except GeometryError:
        return None
    if geometry is None or geometry.is_empty:
        return None
    if geometry.polygons:
        return "Fläche"
    if geometry.lines:
        return "Linie"
    return "Punkt"


def _fits(class_geometry: str, kind: Optional[str]) -> bool:
    """Line classes take only lines; area and point classes take both."""
    if kind is None:
        return True
    return (class_geometry == "Linie") == (kind == "Linie")


def _class_of(topic: _Topic, values: Mapping[str, str], kind: Optional[str]) -> Optional[str]:
    for item in topic.classes:
        if not _fits(item.topic_class.geometry, kind):
            continue
        if any(all(condition.holds(values) for condition in rule) for rule in item.rules):
            return item.topic_class.class_id
    return None


def _has_value(record: HarmonizedRecord, field_name: str) -> bool:
    for source in (record.extra_attributes or {}, record.attributes or {}):
        if _text(source.get(field_name)):
            return True
    return False


def _check_selection(selection: TopicSelection, topics: Mapping[str, _Topic]) -> _Topic:
    topic = topics.get(selection.topic_id)
    if topic is None:
        raise ValueError(f"Unbekanntes Thema: {selection.topic_id}")
    for class_id in selection.class_ids:
        if topic.info.class_by_id(class_id) is None:
            raise ValueError(f"Thema {selection.topic_id}: unbekannte Klasse {class_id}")
    scale_ids = {scale.scale_id for scale in topic.info.scales}
    for scale_id in selection.scale_ids:
        if scale_id not in scale_ids:
            raise ValueError(f"Thema {selection.topic_id}: unbekannte Stufe {scale_id}")
    return topic


def _limit_issue(info: TopicInfo, selection: TopicSelection) -> ValidationIssue:
    lines = list(info.limits)
    guesses = [
        topic_class.name
        for topic_class in info.classes
        if topic_class.uncertain and topic_class.class_id in selection.class_ids
    ]
    if guesses:
        lines.append(
            f"„{TOPIC_LABELS['uncertain']}“ (nur Vorschlag, bitte prüfen): " + ", ".join(guesses) + "."
        )
    if info.source_tips:
        lines.append(f"{TOPIC_LABELS['source_tips']}: " + " ".join(info.source_tips))
    return ValidationIssue(
        code=TOPIC_LIMIT,
        message=f"Das Thema „{info.name}“ zeigt nicht alles.",
        severity="info",
        rule=info.name,
        details="\n".join(lines),
        action=info.source_tips[0] if info.source_tips else "",
    )


def _empty_class_issue(info: TopicInfo, topic_class: TopicClass) -> ValidationIssue:
    return ValidationIssue(
        code=TOPIC_CLASS_EMPTY,
        message=f"Im Gebiet gibt es keine Objekte der Klasse „{topic_class.name}“ (Thema „{info.name}“).",
        severity="info",
        rule=info.name,
        details=(
            "Die Klasse bleibt in der Karte leer. Entweder gibt es sie im Gebiet nicht, "
            "oder sie ist in den geladenen Daten nicht eingetragen."
        ),
        action="Klasse abwählen, eine andere Quelle laden oder das Gebiet vergrößern.",
    )


def _empty_scale_issue(info: TopicInfo, scale: TopicScale) -> ValidationIssue:
    return ValidationIssue(
        code=TOPIC_CLASS_EMPTY,
        message=(
            f"Für die Stufen „{scale.name}“ (Thema „{info.name}“) hat kein Objekt einen Wert "
            f"in der Spalte „{scale.field}“."
        ),
        severity="info",
        rule=info.name,
        details="Die Stufen bleiben in der Karte leer.",
        action="Die Spalte erst erzeugen (z. B. Erreichbarkeit berechnen) oder die Stufen abwählen.",
    )


def classify_topics(
    result: PipelineResult,
    selections: Optional[Sequence[TopicSelection]] = None,
    catalog_path: Optional[Path] = None,
) -> PipelineResult:
    """Sort the records into the chosen topic classes (step 7).

    ``selections`` default to ``result.selected_topics``.  Returns a new
    result (the input is not changed) whose records have ``topic_classes``
    set (only for the selected topics and ticked classes; earlier entries
    are replaced) and whose issues get one ``topic-limit`` hint per topic and
    one ``topic-class-empty`` hint per ticked class or scale without objects.
    Earlier topic hints are replaced, so the function can run again after
    the user changes the selection.  Unknown topic, class or scale ids raise
    ValueError.
    """
    chosen = list(result.selected_topics if selections is None else selections)
    topics = {topic.info.topic_id: topic for topic in _read_topics(catalog_path)}
    checked = [(selection, _check_selection(selection, topics)) for selection in chosen]

    counts: Dict[Tuple[str, str], int] = {}
    scale_filled: Dict[Tuple[str, str], bool] = {}
    records: List[object] = []
    for record in result.harmonized_records:
        if not isinstance(record, HarmonizedRecord):
            records.append(record)
            continue
        values = record_values(record)
        kind = geometry_kind(record)
        classes: Dict[str, str] = {}
        for selection, topic in checked:
            class_id = _class_of(topic, values, kind)
            if class_id is not None and class_id in selection.class_ids:
                classes[selection.topic_id] = class_id
                counts[(selection.topic_id, class_id)] = counts.get((selection.topic_id, class_id), 0) + 1
            for scale in topic.info.scales:
                if scale.scale_id in selection.scale_ids and _has_value(record, scale.field):
                    scale_filled[(selection.topic_id, scale.scale_id)] = True
        records.append(replace(record, topic_classes=classes))

    issues = [issue for issue in result.issues if issue.code not in (TOPIC_LIMIT, TOPIC_CLASS_EMPTY)]
    for selection, topic in checked:
        info = topic.info
        issues.append(_limit_issue(info, selection))
        for topic_class in info.classes:
            if topic_class.class_id in selection.class_ids and not counts.get((info.topic_id, topic_class.class_id)):
                issues.append(_empty_class_issue(info, topic_class))
        for scale in info.scales:
            if scale.scale_id in selection.scale_ids and not scale_filled.get((info.topic_id, scale.scale_id)):
                issues.append(_empty_scale_issue(info, scale))

    return replace(result, harmonized_records=records, issues=issues, selected_topics=chosen)
