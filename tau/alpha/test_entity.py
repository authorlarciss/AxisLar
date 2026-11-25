"""DTO объекта: фасеты, провенанс, сериализация (DOMAIN §3)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from nu.alpha.public import (
    CategoricalValue,
    Entity,
    EntityId,
    MeasurableValue,
    Provenance,
    ReferenceValue,
)


def test_facet_values_are_discriminated_by_kind() -> None:
    entity = Entity.model_validate(
        {
            "id": "edit-1",
            "kind": "edit",
            "facets": {
                "theme": [{"kind": "categorical", "value": "cyberpunk"}],
                "year": [{"kind": "measurable", "value": 2024, "unit": "year"}],
                "author": [{"kind": "reference", "target": "person-7"}],
            },
        }
    )
    assert isinstance(entity.facets["theme"][0], CategoricalValue)
    assert isinstance(entity.facets["year"][0], MeasurableValue)
    assert isinstance(entity.facets["author"][0], ReferenceValue)


def test_unknown_facet_kind_rejected() -> None:
    with pytest.raises(ValidationError):
        Entity.model_validate(
            {"id": "e", "kind": "edit", "facets": {"theme": [{"kind": "mystery", "value": "x"}]}}
        )


def test_empty_facet_list_rejected() -> None:
    with pytest.raises(ValidationError, match="has no values"):
        Entity(id=EntityId("e"), kind="edit", facets={"theme": ()})


def test_provenance_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        Provenance(plugin="cluster", version="0.1", at=datetime(2025, 1, 1))
    assert (
        Provenance(plugin="cluster", version="0.1", at=datetime(2025, 1, 1, tzinfo=UTC)).version
        == "0.1"
    )


def test_provenance_requires_existing_facet() -> None:
    with pytest.raises(ValidationError, match="missing facets"):
        Entity(
            id=EntityId("e"),
            kind="edit",
            derived_by={"cluster": Provenance(plugin="c", version="1", at=datetime.now(UTC))},
        )


def test_entity_rejects_unknown_axis_field_typos() -> None:
    """extra=forbid: опечатка в поле не должна молча исчезать."""
    with pytest.raises(ValidationError):
        Entity.model_validate({"id": "e", "kind": "edit", "fasset": {}})


def test_entity_round_trip() -> None:
    entity = Entity(
        id=EntityId("e-1"),
        kind="note",
        scalars={"title": "Заметка"},
        facets={"theme": (CategoricalValue(value="fantasy"),)},
        derived_by={},
    )
    restored = Entity.model_validate_json(entity.model_dump_json())
    assert restored == entity


def test_multivalued_facet_keeps_all_values() -> None:
    entity = Entity(
        id=EntityId("e-1"),
        kind="edit",
        facets={
            "theme": (
                CategoricalValue(value="cyberpunk"),
                CategoricalValue(value="noir"),
            )
        },
    )
    assert len(entity.facets["theme"]) == 2
