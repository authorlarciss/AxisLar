"""Проверки модели: ось, объект, запрос против схемы (DOMAIN §1–§5)."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from nu.psi.contracts.alpha import (
    AxisDefinition,
    AxisKind,
    CategoricalValue,
    DomainError,
    Entity,
    EntityId,
    Filter,
    MeasurableValue,
    Operator,
    Query,
    ReferenceValue,
    ScalarDefinition,
    StorageSchema,
)
from nu.psi.contracts.beta import Capability, validate_axis, validate_entity, validate_query

SCHEMA = StorageSchema(
    axes=(
        AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL, multi=True),
        AxisDefinition(
            name="genre", kind=AxisKind.CATEGORICAL, strict=True, values=("noir", "epic")
        ),
        AxisDefinition(name="year", kind=AxisKind.MEASURABLE),
        AxisDefinition(name="author", kind=AxisKind.REFERENCE, target="person"),
    ),
    scalars=(ScalarDefinition(name="title", searchable=True),),
)

ALL_CAPS = frozenset(Capability)


def entity(**facets: object) -> Entity:
    """Объект с фасетами, заданными как kwargs."""
    return Entity.model_validate({"id": "e-1", "kind": "edit", "facets": facets})


def codes(errors: Sequence[DomainError]) -> set[str]:
    return {error.code.value for error in errors}


# --------------------------------------------------------------------- ось


def test_validate_axis_rejects_duplicate() -> None:
    errors = validate_axis(SCHEMA, AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL))
    assert codes(errors) == {"duplicate_axis"}


def test_validate_axis_rejects_name_taken_by_scalar() -> None:
    errors = validate_axis(SCHEMA, AxisDefinition(name="title", kind=AxisKind.CATEGORICAL))
    assert codes(errors) == {"duplicate_axis"}


def test_validate_axis_accepts_new_axis() -> None:
    assert validate_axis(SCHEMA, AxisDefinition(name="source", kind=AxisKind.CATEGORICAL)) == []


# ------------------------------------------------------------------ объект


def test_unknown_axis_is_reported() -> None:
    errors = validate_entity(SCHEMA, entity(colour=[{"kind": "categorical", "value": "red"}]))
    assert codes(errors) == {"unknown_axis"}


def test_type_mismatch_is_reported() -> None:
    errors = validate_entity(SCHEMA, entity(year=[{"kind": "categorical", "value": "2024"}]))
    assert codes(errors) == {"type_mismatch"}


def test_cardinality_violation_is_reported() -> None:
    errors = validate_entity(
        SCHEMA,
        entity(year=[{"kind": "measurable", "value": 1}, {"kind": "measurable", "value": 2}]),
    )
    assert codes(errors) == {"cardinality_violation"}


def test_multivalued_axis_allows_several_values() -> None:
    errors = validate_entity(
        SCHEMA,
        entity(
            theme=[
                {"kind": "categorical", "value": "cyberpunk"},
                {"kind": "categorical", "value": "noir"},
            ]
        ),
    )
    assert errors == []


def test_strict_vocabulary_is_enforced() -> None:
    errors = validate_entity(SCHEMA, entity(genre=[{"kind": "categorical", "value": "punk"}]))
    assert codes(errors) == {"unknown_category"}


def test_unknown_scalar_is_reported() -> None:
    obj = Entity(id=EntityId("e-1"), kind="edit", scalars={"why": "because"})
    assert codes(validate_entity(SCHEMA, obj)) == {"unknown_scalar"}


def test_dangling_reference_requires_capability_and_known_ids() -> None:
    obj = entity(author=[{"kind": "reference", "target": "person-404"}])

    assert validate_entity(SCHEMA, obj, known_ids={EntityId("person-1")}) == [], (
        "без Capability.REFERENCE_CHECK проверять ссылки нельзя"
    )
    errors = validate_entity(
        SCHEMA,
        obj,
        known_ids={EntityId("person-1")},
        capabilities=frozenset({Capability.REFERENCE_CHECK}),
    )
    assert codes(errors) == {"dangling_reference"}


def test_reference_to_known_id_passes() -> None:
    obj = entity(author=[{"kind": "reference", "target": "person-1"}])
    assert (
        validate_entity(
            SCHEMA,
            obj,
            known_ids={EntityId("person-1")},
            capabilities=frozenset({Capability.REFERENCE_CHECK}),
        )
        == []
    )


# ----------------------------------------------------------------- запрос


def test_query_with_unknown_axis() -> None:
    query = Query(all=(Filter(axis="colour", op=Operator.EXISTS),))
    assert codes(validate_query(SCHEMA, query, ALL_CAPS)) == {"unknown_axis"}


def test_numeric_operator_on_categorical_axis() -> None:
    query = Query(all=(Filter(axis="theme", op=Operator.GT, values=(1,)),))
    assert codes(validate_query(SCHEMA, query, ALL_CAPS)) == {"type_mismatch"}


def test_set_operator_on_measurable_axis() -> None:
    query = Query(all=(Filter(axis="year", op=Operator.CONTAINS, values=(2024,)),))
    assert codes(validate_query(SCHEMA, query, ALL_CAPS)) == {"type_mismatch"}


def test_missing_capability_makes_query_unsupported() -> None:
    query = Query(all=(Filter(axis="year", op=Operator.GTE, values=(2020,)),))
    errors = validate_query(SCHEMA, query, frozenset({Capability.QUERY_CATEGORICAL}))
    assert codes(errors) == {"unsupported_query"}


def test_exists_does_not_require_type_capability() -> None:
    query = Query(all=(Filter(axis="year", op=Operator.EXISTS),))
    assert validate_query(SCHEMA, query, frozenset()) == []


def test_scalar_search_requires_capability() -> None:
    query = Query(all=(Filter(axis="title", op=Operator.SCALAR_EQ, values=("Заметка",)),))
    assert validate_query(SCHEMA, query, frozenset()) != []
    assert validate_query(SCHEMA, query, ALL_CAPS) == []


def test_unknown_scalar_in_query() -> None:
    query = Query(all=(Filter(axis="subtitle", op=Operator.SCALAR_EQ, values=("x",)),))
    assert codes(validate_query(SCHEMA, query, ALL_CAPS)) == {"unknown_scalar"}


def test_strict_vocabulary_in_query() -> None:
    query = Query(all=(Filter(axis="genre", op=Operator.CONTAINS, values=("punk",)),))
    assert codes(validate_query(SCHEMA, query, ALL_CAPS)) == {"unknown_category"}


def test_any_is_unsupported_in_v0() -> None:
    query = Query.model_validate({"any": [{"axis": "year", "op": "exists"}]})
    assert codes(validate_query(SCHEMA, query, ALL_CAPS)) == {"unsupported_query"}


@pytest.mark.parametrize(
    ("kind", "value"),
    [
        ("theme", CategoricalValue(value="cyberpunk")),
        ("year", MeasurableValue(value=2024.0)),
        ("author", ReferenceValue(target=EntityId("person-1"))),
    ],
)
def test_valid_entity_has_no_errors(
    kind: str, value: CategoricalValue | MeasurableValue | ReferenceValue
) -> None:
    obj = entity(**{kind: [value.model_dump()]})
    assert validate_entity(SCHEMA, obj, capabilities=ALL_CAPS) == []
