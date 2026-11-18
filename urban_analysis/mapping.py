"""Category and object-type rules for the data pipeline (QGIS-free).

The rules live in ``mapping_rules.json`` next to this module, so the team can
adjust them without changing code.  Keys starting with ``_`` are comments.

* **Profiles** describe known data models such as ALKIS.  A layer uses a
  profile when its table name is listed there and it has all
  ``requires_fields``.  The profile decides the category, which column holds
  the object type, how that value splits into main type and detail, and
  whether the layer is split into one result layer per category.
* **Name categories** are the fallback for unknown data: only the layer name
  is used.  Values inside the data are never scanned for keywords.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping, Optional, Sequence, Tuple


RULES_FILE = Path(__file__).with_name("mapping_rules.json")


class MappingRulesError(ValueError):
    """Raised when ``mapping_rules.json`` is missing or malformed."""


def _without_comments(data: Mapping[str, Any]) -> Dict[str, Any]:
    return {key: value for key, value in data.items() if not str(key).startswith("_")}


def _matches(value: str, pattern: str) -> bool:
    """True if ``value`` equals ``pattern`` or continues it with ``', '``."""
    return value == pattern or value.startswith(pattern + ", ")


@dataclass(frozen=True)
class CategoryRule:
    category: str
    layer_suffix: str
    values: Tuple[str, ...] = ()

    def matches(self, value: str) -> bool:
        return any(_matches(value, pattern) for pattern in self.values)


@dataclass(frozen=True)
class Classification:
    """Result of applying a layer profile to one row."""

    category: Optional[str]
    object_type: Optional[str] = None
    object_detail: Optional[str] = None
    layer_suffix: Optional[str] = None


@dataclass(frozen=True)
class LayerProfile:
    """Rules for one table of a known data model."""

    profile_name: str
    table_name: str
    requires_fields: Tuple[str, ...]
    category: Optional[str] = None
    object_type_field: Optional[str] = None
    main_types: Tuple[str, ...] = ()
    category_rules: Tuple[CategoryRule, ...] = ()
    default_rule: Optional[CategoryRule] = None
    object_id_field: Optional[str] = None
    street_field: Optional[str] = None
    house_number_field: Optional[str] = None

    @property
    def address_fields(self) -> Tuple[str, ...]:
        """Columns that may differ between rows of one object (its addresses)."""
        return tuple(field for field in (self.street_field, self.house_number_field) if field)

    def address(self, row: Mapping[str, Any]) -> Optional[str]:
        """One address from a row, e.g. ``Hauptstraße 2``; ``None`` if both are empty."""
        parts = []
        for field in (self.street_field, self.house_number_field):
            value = row.get(field) if field else None
            if value not in (None, "") and str(value).strip():
                parts.append(str(value).strip())
        return " ".join(parts) or None

    @property
    def splits_layer(self) -> bool:
        return bool(self.category_rules or self.default_rule)

    def uses_field(self, fields: Sequence[str]) -> bool:
        return self.object_type_field is not None and self.object_type_field in fields

    def split_type(self, value: str) -> Tuple[str, Optional[str]]:
        """Split ``value`` into main type and detail using ``main_types``."""
        for main_type in sorted(self.main_types, key=len, reverse=True):
            if value == main_type:
                return main_type, None
            if value.startswith(main_type + ", "):
                return main_type, value[len(main_type) + 2 :] or None
        return value, None

    def classify(self, row: Mapping[str, Any], fields: Sequence[str]) -> Classification:
        raw = row.get(self.object_type_field) if self.uses_field(fields) else None
        value = str(raw).strip() if raw not in (None, "") else None
        object_type = object_detail = None
        if value is not None:
            object_type, object_detail = self.split_type(value)

        if not self.splits_layer:
            return Classification(self.category, object_type, object_detail)
        rule = next(
            (rule for rule in self.category_rules if value is not None and rule.matches(value)),
            self.default_rule,
        )
        if rule is None:
            return Classification(None, object_type, object_detail)
        return Classification(rule.category, object_type, object_detail, rule.layer_suffix)


@dataclass(frozen=True)
class MappingRules:
    profiles: Tuple[LayerProfile, ...]
    name_categories: Tuple[Tuple[str, Tuple[str, ...]], ...]
    field_labels: Mapping[str, str]
    layer_labels: Mapping[str, str] = field(default_factory=dict)
    target_field_labels: Mapping[str, str] = field(default_factory=dict)
    target_field_explanations: Mapping[str, str] = field(default_factory=dict)

    def profile_for(self, table_name: str, fields: Iterable[str]) -> Optional[LayerProfile]:
        available = set(fields)
        for profile in self.profiles:
            if profile.table_name == table_name and set(profile.requires_fields) <= available:
                return profile
        return None

    def category_from_name(self, table_name: str) -> Optional[str]:
        name = table_name.casefold()
        for category, terms in self.name_categories:
            if any(term in name for term in terms):
                return category
        return None

    def label(self, field: str) -> str:
        """Readable field name with its code, e.g. ``Hausnummer (hnr)``."""
        text = self.field_labels.get(field)
        return f"{text} ({field})" if text else field

    def field_name(self, field: str) -> str:
        """Readable field name only, e.g. ``Hausnummer``; unknown fields stay as they are."""
        return self.field_labels.get(field, field)

    def layer_name(self, table_name: str) -> str:
        """Readable layer name, e.g. ``Gebäude`` for ``gebaeude``."""
        return self.layer_labels.get(table_name, table_name)

    def target_field_name(self, field: str) -> str:
        """German name of a target field, e.g. ``Objektart`` for ``object_type``."""
        return self.target_field_labels.get(field, field)

    def target_field_explanation(self, field: str) -> Optional[str]:
        """One sentence explaining a target field (for the ⓘ symbol), or ``None``."""
        return self.target_field_explanations.get(field)


def _rule(data: Mapping[str, Any], where: str) -> CategoryRule:
    try:
        return CategoryRule(
            category=str(data["category"]),
            layer_suffix=str(data["layer_suffix"]),
            values=tuple(str(value) for value in data.get("values", ())),
        )
    except (KeyError, TypeError) as exc:
        raise MappingRulesError(f"Ungültige Regel in {where}: {exc}") from exc


def parse_mapping_rules(data: Mapping[str, Any]) -> MappingRules:
    """Build ``MappingRules`` from the decoded JSON content."""
    profiles = []
    for profile in data.get("profiles", ()):
        profile = _without_comments(profile)
        name = str(profile.get("name", "Profil"))
        requires = tuple(str(field) for field in profile.get("requires_fields", ()))
        object_id_field = profile.get("object_id_field")
        street_field = profile.get("street_field")
        house_number_field = profile.get("house_number_field")
        for table_name, layer in _without_comments(profile.get("layers", {})).items():
            layer = _without_comments(layer)
            where = f"{name}/{table_name}"
            default = layer.get("default_rule")
            profiles.append(
                LayerProfile(
                    profile_name=name,
                    table_name=str(table_name),
                    requires_fields=requires,
                    category=layer.get("category"),
                    object_type_field=layer.get("object_type_field"),
                    main_types=tuple(str(value) for value in layer.get("main_types", ())),
                    category_rules=tuple(
                        _rule(rule, where) for rule in layer.get("category_rules", ())
                    ),
                    default_rule=_rule(default, where) if default else None,
                    object_id_field=str(object_id_field) if object_id_field else None,
                    street_field=str(street_field) if street_field else None,
                    house_number_field=str(house_number_field) if house_number_field else None,
                )
            )
    name_categories = tuple(
        (str(category), tuple(str(term).casefold() for term in terms))
        for category, terms in _without_comments(data.get("name_categories", {})).items()
    )
    def _labels(key: str) -> Dict[str, str]:
        return {
            str(name): str(label)
            for name, label in _without_comments(data.get(key, {})).items()
        }

    return MappingRules(
        tuple(profiles),
        name_categories,
        _labels("field_labels"),
        _labels("layer_labels"),
        _labels("target_field_labels"),
        _labels("target_field_explanations"),
    )


def load_mapping_rules(path: Optional[Path] = None) -> MappingRules:
    """Read the rules file; errors are reported instead of silently ignored."""
    file_path = Path(path) if path is not None else RULES_FILE
    try:
        data = json.loads(file_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MappingRulesError(f"Regeldatei {file_path.name} ist nicht lesbar: {exc}") from exc
    return parse_mapping_rules(data)


@lru_cache(maxsize=1)
def default_mapping_rules() -> MappingRules:
    return load_mapping_rules()


def readable_field(field: str) -> str:
    """For the user guidance: ``gfk__bez`` -> ``Gebäudefunktion``."""
    return default_mapping_rules().field_name(field)


def readable_layer(layer_id: str) -> str:
    """For the user guidance: ``gebaeude`` -> ``Gebäude``."""
    return default_mapping_rules().layer_name(layer_id)


def readable_target_field(field: str) -> str:
    """For the user guidance: ``object_type`` -> ``Objektart``."""
    return default_mapping_rules().target_field_name(field)


def target_field_explanation(field: str) -> Optional[str]:
    """For the user guidance (ⓘ symbol): one sentence explaining a target field."""
    return default_mapping_rules().target_field_explanation(field)
