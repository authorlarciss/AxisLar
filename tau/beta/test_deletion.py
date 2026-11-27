"""Политика удаления: tombstone не оставляет висячих ссылок (ADR-0025)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast

import pytest

from nu.beta.public import cascade_order, collect_dangling, tombstone_entity
from nu.delta._internal.memory import MemoryStorage
from nu.iota.public.contract_kit import CONTRACT_SCHEMA
from nu.psi.contracts.alpha import (
    CategoricalValue,
    Entity,
    EntityId,
    ErrorCode,
    FacetValue,
    ReferenceValue,
)
from nu.psi.contracts.delta import IStorageEngine

pytestmark = pytest.mark.unit


def entity(entity_id: str, *, author: str | None = None) -> Entity:
    facets: dict[str, tuple[FacetValue, ...]] = {
        "theme": (CategoricalValue(value="noir"),),
    }
    if author is not None:
        facets["author"] = (ReferenceValue(target=EntityId(author)),)
    return Entity(id=EntityId(entity_id), kind="edit", facets=facets)


async def engine(*entities: Entity) -> MemoryStorage:
    storage = MemoryStorage(CONTRACT_SCHEMA)
    errors = await storage.bulk_upsert(entities)
    assert errors == [], errors
    return storage


async def test_tombstone_refuses_when_referenced() -> None:
    """Удаление цели со живыми ссылками — отказ, и ничего не пишется."""
    storage = await engine(entity("b-2"), entity("a-1", author="b-2"))
    before = await storage.get(EntityId("b-2"))

    errors = await tombstone_entity(storage, EntityId("b-2"))

    assert [error.code for error in errors] == [ErrorCode.REFERENCE_IN_USE]
    assert errors[0].axis == "author"
    assert errors[0].entity_id == EntityId("b-2")
    assert "a-1" not in errors[0].detail  # в тексте раскладка по осям, а не список id
    assert await storage.get(EntityId("b-2")) == before


async def test_tombstone_passes_when_reference_removed() -> None:
    storage = await engine(entity("b-2"), entity("a-1", author="b-2"))
    assert [error.code for error in await tombstone_entity(storage, EntityId("b-2"))] == [
        ErrorCode.REFERENCE_IN_USE
    ]

    assert await storage.upsert(entity("a-1")) == []
    assert await tombstone_entity(storage, EntityId("b-2")) == []

    assert await storage.get(EntityId("b-2")) is None
    stored = await storage.list_entities(include_deleted=True)
    assert [item.id for item in stored if item.deleted_at is not None] == [EntityId("b-2")]


async def test_self_reference_does_not_block() -> None:
    """Ссылка на себя висячей не станет: она исчезнет вместе с объектом."""
    storage = await engine(entity("c-3", author="c-3"))
    assert await tombstone_entity(storage, EntityId("c-3")) == []


async def test_tombstone_is_idempotent() -> None:
    storage = await engine(entity("d-4"))
    assert await tombstone_entity(storage, EntityId("d-4")) == []
    assert await tombstone_entity(storage, EntityId("d-4")) == []
    assert await tombstone_entity(storage, EntityId("no-such")) == []


async def test_conflict_wins_over_tombstone() -> None:
    """Устаревшая ревизия — CONFLICT, объект остаётся живым (ADR-0024)."""
    storage = await engine(entity("e-5"), entity("f-6", author="e-5"))
    errors = await tombstone_entity(storage, EntityId("f-6"), expected_rev=99)
    assert [error.code for error in errors] == [ErrorCode.CONFLICT]
    assert await storage.get(EntityId("f-6")) is not None


async def test_cascade_order_lists_referrers_first() -> None:
    """Порядок каскада: сначала ссылающиеся, цель — последней."""
    storage = await engine(
        entity("b-2"),
        entity("a-1", author="b-2"),
        entity("c-3", author="a-1"),
    )
    order = await cascade_order(storage, EntityId("b-2"))
    assert order[-1] == EntityId("b-2")
    assert order == (EntityId("c-3"), EntityId("a-1"), EntityId("b-2"))


async def test_cascade_order_survives_cycle() -> None:
    storage = await engine(entity("a-1", author="b-2"), entity("b-2", author="a-1"))
    order = await cascade_order(storage, EntityId("a-1"))
    assert set(order) == {EntityId("a-1"), EntityId("b-2")}
    assert len(order) == 2


async def test_collect_dangling_reports_links_left_by_sync() -> None:
    """Sync ставит tombstone сам; отчёт обязан это показать."""
    storage = await engine(entity("b-2"), entity("a-1", author="b-2"))
    tombstoned = await storage.get(EntityId("b-2"))
    assert tombstoned is not None
    gone = tombstoned.model_copy(update={"deleted_at": datetime.now(UTC)})
    assert await storage.upsert(gone) == []

    dangling = await collect_dangling(storage, (EntityId("b-2"),))
    assert len(dangling) == 1
    assert dangling[0].target == EntityId("b-2")
    assert [link.entity_id for link in dangling[0].links] == [EntityId("a-1")]

    assert await storage.upsert(entity("a-1")) == []
    assert await collect_dangling(storage, (EntityId("b-2"),)) == ()


class _NoIndex:
    """Бэкенд без `IReferenceIndex`: политику проверить нечем."""

    def __init__(self, inner: MemoryStorage) -> None:
        self._inner = inner

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)


async def test_backend_without_reference_index_refuses() -> None:
    storage = await engine(entity("g-7"))
    wrapped = cast(IStorageEngine, _NoIndex(storage))
    errors = await tombstone_entity(wrapped, EntityId("g-7"))
    assert [error.code for error in errors] == [ErrorCode.UNSUPPORTED_CAPABILITY]
    assert await storage.get(EntityId("g-7")) is not None


async def test_reference_in_use_message_is_declined() -> None:
    """Сообщение читает человек: «1 объект», «2 объекта», «5 объектов»."""
    one = await engine(entity("b-2"), entity("a-1", author="b-2"))
    [error] = await tombstone_entity(one, EntityId("b-2"))
    assert "ссылаются 1 объект:" in error.detail

    many = await engine(
        entity("b-2"),
        entity("a-1", author="b-2"),
        entity("c-3", author="b-2"),
        entity("d-4", author="b-2"),
        entity("e-5", author="b-2"),
        entity("f-6", author="b-2"),
    )
    [error] = await tombstone_entity(many, EntityId("b-2"))
    assert "ссылаются 5 объектов:" in error.detail
