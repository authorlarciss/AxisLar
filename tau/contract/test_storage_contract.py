"""Контрактные тесты бэкенда (DOMAIN §2–§6).

Один и тот же набор проверяет любой бэкенд: он подключается фабрикой в
`conftest.BACKENDS`. Расхождение между реализациями — дефект реализации,
а не теста.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

import pytest

from nu.psi.contracts.alpha import (
    AxisDefinition,
    AxisKind,
    Capability,
    CategoricalValue,
    DomainError,
    Entity,
    EntityId,
    ErrorCode,
    Filter,
    MeasurableValue,
    Operator,
    Query,
    QueryResult,
    ReferenceValue,
    ScalarDefinition,
    StorageSchema,
)
from nu.psi.contracts.delta import IStorageEngine, StorageQueryError

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

Backend = Callable[[StorageSchema], IStorageEngine]


def entity(entity_id: str, **facets: object) -> Entity:
    return Entity.model_validate({"id": entity_id, "kind": "edit", "facets": facets})


SEED: tuple[Entity, ...] = (
    Entity(
        id=EntityId("a-1"),
        kind="edit",
        scalars={"title": "Alpha"},
        facets={
            "theme": (CategoricalValue(value="cyberpunk"), CategoricalValue(value="noir")),
            "year": (MeasurableValue(value=2024.0),),
            "author": (ReferenceValue(target=EntityId("b-2")),),
        },
    ),
    Entity(
        id=EntityId("b-2"),
        kind="edit",
        scalars={"title": "Beta"},
        facets={
            "theme": (CategoricalValue(value="fantasy"),),
            "year": (MeasurableValue(value=2019.0),),
        },
    ),
    Entity(id=EntityId("c-3"), kind="note", scalars={"title": "Gamma"}),
)


async def seeded(backend: Backend) -> IStorageEngine:
    engine = backend(SCHEMA)
    assert await engine.bulk_upsert(SEED) == []
    return engine


def ids(result: QueryResult) -> list[str]:
    return [str(entity_id) for entity_id in result.ids]


def codes(errors: Sequence[DomainError]) -> set[str]:
    return {error.code.value for error in errors}


# ------------------------------------------------------------------ основа


async def test_schema_is_available(backend: Backend) -> None:
    engine = backend(SCHEMA)
    assert await engine.get_schema() == SCHEMA


async def test_empty_store_returns_nothing(backend: Backend) -> None:
    engine = backend(SCHEMA)
    result = await engine.query(Query())
    assert result.ids == ()
    assert result.total == 0
    assert await engine.count() == 0


async def test_seeded_objects_are_stored(backend: Backend) -> None:
    engine = await seeded(backend)
    assert await engine.count() == 3
    assert (await engine.get(EntityId("c-3"))) == SEED[2]


async def test_fetch_many_skips_missing(backend: Backend) -> None:
    engine = await seeded(backend)
    fetched = await engine.fetch_many((EntityId("a-1"), EntityId("nope"), EntityId("c-3")))
    assert [str(item.id) for item in fetched] == ["a-1", "c-3"]


# --------------------------------------------- таблица отсутствующих (DOMAIN §5)


@pytest.mark.parametrize(
    ("op", "axis", "values", "expected"),
    [
        (Operator.CONTAINS, "theme", ("cyberpunk",), False),
        (Operator.ANY_OF, "theme", ("cyberpunk", "fantasy"), False),
        (Operator.NONE_OF, "theme", ("cyberpunk",), True),
        (Operator.EXISTS, "theme", (), False),
        (Operator.NOT_EXISTS, "theme", (), True),
        (Operator.EQ, "year", (2019,), False),
        (Operator.GT, "year", (1900,), False),
        (Operator.LT, "year", (9999,), False),
        (Operator.GTE, "year", (1900,), False),
        (Operator.LTE, "year", (9999,), False),
        (Operator.BETWEEN, "year", (1900, 9999), False),
    ],
    ids=[
        "contains",
        "any_of",
        "none_of",
        "exists",
        "not_exists",
        "eq",
        "gt",
        "lt",
        "gte",
        "lte",
        "between",
    ],
)
async def test_missing_value_semantics(
    backend: Backend,
    op: Operator,
    axis: str,
    values: tuple[str | float, ...],
    expected: bool,
) -> None:
    """Объект без значения по оси: см. обязательную таблицу DOMAIN §5."""
    engine = await seeded(backend)
    result = await engine.query(Query(all=(Filter(axis=axis, op=op, values=values),)))
    assert ("c-3" in ids(result)) is expected


# ------------------------------------------------------ категориальные оси


async def test_contains_matches_any_of_multiple_values(backend: Backend) -> None:
    engine = await seeded(backend)
    result = await engine.query(
        Query(all=(Filter(axis="theme", op=Operator.CONTAINS, values=("noir",)),))
    )
    assert ids(result) == ["a-1"]


async def test_any_of_matches_objects_with_any_value(backend: Backend) -> None:
    engine = await seeded(backend)
    result = await engine.query(
        Query(all=(Filter(axis="theme", op=Operator.ANY_OF, values=("fantasy", "noir")),))
    )
    assert ids(result) == ["a-1", "b-2"]


async def test_none_of_excludes_matches_but_keeps_missing(backend: Backend) -> None:
    engine = await seeded(backend)
    result = await engine.query(
        Query(all=(Filter(axis="theme", op=Operator.NONE_OF, values=("noir",)),))
    )
    assert ids(result) == ["b-2", "c-3"]


async def test_exists_filters_by_axis_presence(backend: Backend) -> None:
    engine = await seeded(backend)
    result = await engine.query(Query(all=(Filter(axis="author", op=Operator.EXISTS),)))
    assert ids(result) == ["a-1"]


# --------------------------------------------------------- измеримые оси


async def test_numeric_between_is_inclusive(backend: Backend) -> None:
    engine = await seeded(backend)
    inside = await engine.query(
        Query(all=(Filter(axis="year", op=Operator.BETWEEN, values=(2019, 2024)),))
    )
    assert ids(inside) == ["a-1", "b-2"]

    outside = await engine.query(
        Query(all=(Filter(axis="year", op=Operator.BETWEEN, values=(2020, 2023)),))
    )
    assert ids(outside) == []


async def test_numeric_comparison(backend: Backend) -> None:
    engine = await seeded(backend)
    result = await engine.query(Query(all=(Filter(axis="year", op=Operator.GTE, values=(2020,)),)))
    assert ids(result) == ["a-1"]


# --------------------------------------------------------------- скаляры


async def test_scalar_eq(backend: Backend) -> None:
    engine = await seeded(backend)
    result = await engine.query(
        Query(all=(Filter(axis="title", op=Operator.SCALAR_EQ, values=("Beta",)),))
    )
    assert ids(result) == ["b-2"]


# ------------------------------------------------- разреженность и оси


async def test_add_axis_keeps_existing_objects_sparse(backend: Backend) -> None:
    """ADR-0010: старые объекты не переписываются, они разреженны по новой оси."""
    engine = await seeded(backend)
    errors = await engine.add_axis(AxisDefinition(name="language", kind=AxisKind.CATEGORICAL))
    assert errors == []

    schema = await engine.get_schema()
    assert schema.axis("language") is not None

    present = await engine.query(Query(all=(Filter(axis="language", op=Operator.EXISTS),)))
    assert present.ids == ()
    absent = await engine.query(Query(all=(Filter(axis="language", op=Operator.NOT_EXISTS),)))
    assert ids(absent) == ["a-1", "b-2", "c-3"]
    assert await engine.count() == 3, "объекты не материализуют новую ось"


async def test_add_scalar_enables_scalar_query(backend: Backend) -> None:
    engine = backend(StorageSchema())
    assert await engine.add_scalar(ScalarDefinition(name="title", searchable=True)) == []
    obj = Entity.model_validate({"id": "e-1", "kind": "edit", "scalars": {"title": "Alpha"}})
    assert await engine.upsert(obj) == []

    result = await engine.query(
        Query(all=(Filter(axis="title", op=Operator.SCALAR_EQ, values=("Alpha",)),))
    )
    assert ids(result) == ["e-1"]


async def test_add_duplicate_scalar_is_rejected(backend: Backend) -> None:
    engine = backend(StorageSchema())
    await engine.add_scalar(ScalarDefinition(name="title"))
    errors = await engine.add_scalar(ScalarDefinition(name="title"))
    assert codes(errors) == {ErrorCode.DUPLICATE_SCALAR.value}


async def test_add_duplicate_axis_is_rejected(backend: Backend) -> None:
    engine = backend(SCHEMA)
    errors = await engine.add_axis(AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL))
    assert codes(errors) == {ErrorCode.DUPLICATE_AXIS.value}


# ------------------------------------------------------------- запись


async def test_upsert_replaces_by_id(backend: Backend) -> None:
    engine = await seeded(backend)
    replacement = Entity.model_validate(
        {"id": "a-1", "kind": "edit", "scalars": {"title": "Alpha v2"}, "facets": {}}
    )
    assert await engine.upsert(replacement) == []
    assert await engine.count() == 3
    stored = await engine.get(EntityId("a-1"))
    assert stored is not None
    assert stored.scalars["title"] == "Alpha v2"
    assert stored.facets == {}


async def test_upsert_rejects_unknown_axis(backend: Backend) -> None:
    engine = backend(SCHEMA)
    errors = await engine.upsert(entity("x", colour=[{"kind": "categorical", "value": "red"}]))
    assert codes(errors) == {ErrorCode.UNKNOWN_AXIS.value}
    assert await engine.count() == 0


async def test_upsert_rejects_type_mismatch(backend: Backend) -> None:
    engine = backend(SCHEMA)
    errors = await engine.upsert(entity("x", year=[{"kind": "categorical", "value": "2024"}]))
    assert codes(errors) == {ErrorCode.TYPE_MISMATCH.value}


async def test_upsert_rejects_cardinality_violation(backend: Backend) -> None:
    engine = backend(SCHEMA)
    errors = await engine.upsert(
        entity(
            "x",
            year=[{"kind": "measurable", "value": 1}, {"kind": "measurable", "value": 2}],
        )
    )
    assert codes(errors) == {ErrorCode.CARDINALITY_VIOLATION.value}


async def test_upsert_rejects_value_outside_strict_vocabulary(backend: Backend) -> None:
    engine = backend(SCHEMA)
    errors = await engine.upsert(entity("x", genre=[{"kind": "categorical", "value": "punk"}]))
    assert codes(errors) == {ErrorCode.UNKNOWN_CATEGORY.value}


async def test_upsert_rejects_dangling_reference(backend: Backend) -> None:
    engine = await seeded(backend)
    errors = await engine.upsert(
        entity("x", author=[{"kind": "reference", "target": "person-404"}])
    )
    assert codes(errors) == {ErrorCode.DANGLING_REFERENCE.value}


async def test_upsert_accepts_reference_to_existing_object(backend: Backend) -> None:
    engine = await seeded(backend)
    errors = await engine.upsert(entity("x", author=[{"kind": "reference", "target": "b-2"}]))
    assert errors == []


async def test_bulk_upsert_reports_errors_and_keeps_valid_objects(backend: Backend) -> None:
    engine = backend(SCHEMA)
    errors = await engine.bulk_upsert(
        (
            entity("ok-1", theme=[{"kind": "categorical", "value": "noir"}]),
            entity("bad", unknown=[{"kind": "categorical", "value": "x"}]),
        )
    )
    assert codes(errors) == {ErrorCode.UNKNOWN_AXIS.value}
    assert await engine.count() == 1
    assert (await engine.get(EntityId("ok-1"))) is not None


# ------------------------------------------------------- выдача и пагинация


async def test_order_is_deterministic_and_pagination_applies(backend: Backend) -> None:
    engine = await seeded(backend)
    page = await engine.query(Query(limit=2, offset=1))
    assert ids(page) == ["b-2", "c-3"]
    assert page.total == 3
    assert page.limit == 2
    assert page.offset == 1


async def test_unsupported_branch_raises(backend: Backend) -> None:
    engine = await seeded(backend)
    query = Query.model_validate({"any": [{"axis": "year", "op": "exists"}]})
    with pytest.raises(StorageQueryError) as error:
        await engine.query(query)
    assert {item.code for item in error.value.errors} == {ErrorCode.UNSUPPORTED_QUERY}


async def test_capabilities_cover_query_kinds(backend: Backend) -> None:
    capabilities = backend(SCHEMA).capabilities()
    assert {
        Capability.QUERY_CATEGORICAL,
        Capability.QUERY_MEASURABLE,
        Capability.QUERY_REFERENCE,
        Capability.SCALAR_SEARCH,
    } <= capabilities
