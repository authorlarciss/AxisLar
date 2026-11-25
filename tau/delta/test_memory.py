"""Внутренние тесты in-memory бэкенда (то, что не покрывает контракт)."""

from __future__ import annotations

import pytest

from nu.psi.contracts.alpha import (
    AxisDefinition,
    AxisKind,
    Capability,
    Entity,
    EntityId,
    ErrorCode,
    MeasurableValue,
    Query,
    StorageSchema,
)
from nu.psi.contracts.delta import DeltaResolver, IStorageEngine, StorageQueryError

SCHEMA = StorageSchema(axes=(AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL),))


def engine_without_resolver() -> IStorageEngine:
    return DeltaResolver().make_memory_storage(schema=SCHEMA)


def test_capabilities_are_a_static_set() -> None:
    engine = engine_without_resolver()
    capabilities = engine.capabilities()
    assert isinstance(capabilities, frozenset)
    assert Capability.REFERENCE_CHECK in capabilities
    assert engine.capabilities() is capabilities, "набор не пересобирается на каждый вызов"


async def test_engine_validates_internally_without_resolver() -> None:
    """Движок обязан отказать, а не вернуть пустую выдачу."""
    engine = engine_without_resolver()
    query = Query.model_validate({"any": [{"axis": "theme", "op": "exists"}]})
    with pytest.raises(StorageQueryError) as error:
        await engine.query(query)
    assert {item.code for item in error.value.errors} == {ErrorCode.UNSUPPORTED_QUERY}


async def test_fetch_many_keeps_request_order() -> None:
    engine = engine_without_resolver()
    await engine.upsert(Entity(id=EntityId("z"), kind="edit"))
    await engine.upsert(Entity(id=EntityId("a"), kind="edit"))
    fetched = await engine.fetch_many((EntityId("z"), EntityId("a")))
    assert [str(item.id) for item in fetched] == ["z", "a"]


async def test_schema_is_not_shared_between_engines() -> None:
    first = engine_without_resolver()
    second = engine_without_resolver()
    await first.add_axis(AxisDefinition(name="year", kind=AxisKind.MEASURABLE))
    assert (await first.get_schema()).axis("year") is not None
    assert (await second.get_schema()).axis("year") is None


def test_private_comparison_helpers() -> None:
    from nu.delta._internal.memory import _equal

    assert _equal(MeasurableValue(value=2024.0), 2024.0, AxisKind.MEASURABLE) is True
    assert _equal(MeasurableValue(value=2024.0), 2024.0, AxisKind.CATEGORICAL) is False
