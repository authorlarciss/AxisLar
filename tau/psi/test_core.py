"""Ядро как фасад: сборка, работа через `Core`, подмена хранилища."""

from __future__ import annotations

import pytest

from nu.psi import build_core
from nu.psi.contracts.alpha import (
    AxisDefinition,
    AxisKind,
    CategoricalValue,
    Entity,
    EntityId,
    ErrorCode,
    Filter,
    Operator,
    Query,
    ScalarDefinition,
    StorageSchema,
)
from nu.psi.contracts.delta import DeltaResolver


async def test_build_core_uses_memory_by_default() -> None:
    core = build_core()
    assert await core.count() == 0
    assert await core.schema() == StorageSchema()


async def test_core_roundtrip() -> None:
    core = build_core()
    assert await core.add_axis(AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL)) == []
    entity = Entity(
        id=EntityId("e-1"),
        kind="edit",
        facets={"theme": (CategoricalValue(value="cyberpunk"),)},
    )
    assert await core.upsert(entity) == []
    assert await core.count() == 1

    result = await core.query(
        Query(all=(Filter(axis="theme", op=Operator.CONTAINS, values=("cyberpunk",)),))
    )
    assert result.ids == (EntityId("e-1"),)


async def test_core_reports_domain_errors_as_values() -> None:
    core = build_core()
    errors = await core.upsert(Entity(id=EntityId("x"), kind="edit", scalars={"title": "T"}))
    assert {error.code for error in errors} == {ErrorCode.UNKNOWN_SCALAR}


async def test_core_check_query_does_not_execute() -> None:
    core = build_core()
    query = Query(all=(Filter(axis="colour", op=Operator.EXISTS),))
    errors = await core.check_query(query)
    assert {error.code for error in errors} == {ErrorCode.UNKNOWN_AXIS}


async def test_core_accepts_any_storage_implementation() -> None:
    storage = DeltaResolver().make_memory_storage(
        schema=StorageSchema(axes=(AxisDefinition(name="year", kind=AxisKind.MEASURABLE),))
    )
    core = build_core(storage=storage)
    assert core.storage is storage
    assert (await core.schema()).axis("year") is not None


async def test_core_capabilities_come_from_storage() -> None:
    core = build_core()
    assert core.capabilities() == build_core().capabilities()
    assert core.capabilities(), "эталонное хранилище объявляет возможности"


@pytest.mark.parametrize("method", ["upsert", "get", "query", "count", "schema"])
def test_core_exposes_use_cases(method: str) -> None:
    assert hasattr(build_core(), method)


async def test_core_write_and_read_paths() -> None:
    core = build_core()
    assert await core.add_scalar(ScalarDefinition(name="title", searchable=True)) == []
    entity = Entity(id=EntityId("e-1"), kind="edit", scalars={"title": "Alpha"})
    assert await core.upsert(entity) == []

    found = await core.get(EntityId("e-1"))
    assert found is not None and found.scalars["title"] == "Alpha"

    result = await core.query(Query())
    assert result.ids == (EntityId("e-1"),)
