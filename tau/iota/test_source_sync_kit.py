"""Набор синхронизации источников и политика идентичности (ADR-0016)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

import pytest

from nu.contracts import entity_id_for, run_source_sync_contract
from nu.delta.public.interfaces import IEntitySource
from nu.iota.public.contract_kit import CONTRACT_SCHEMA
from nu.psi.contracts.alpha import CategoricalValue, Entity, EntityId, Origin


def make_entity(
    key: str,
    *,
    source_id: str = "src-1",
    content_hash: str | None = "h1",
    use_policy_id: bool = True,
) -> Entity:
    entity_id = entity_id_for(source_id, key) if use_policy_id else EntityId(f"custom-{key}")
    return Entity(
        id=entity_id,
        kind="edit",
        facets={"theme": (CategoricalValue(value="cyberpunk"),)},
        origin=Origin(
            source_id=source_id,
            key=key,
            content_hash=content_hash,
            hash_algo="partial" if content_hash else None,
        ),
    )


class Source(IEntitySource):
    def __init__(self, entities: Sequence[Entity]) -> None:
        self._entities = entities

    def describe(self) -> str:
        return "test-source"

    async def scan(self) -> AsyncIterator[Entity]:
        for entity in self._entities:
            yield entity


def test_entity_id_is_stable_and_scoped() -> None:
    first = entity_id_for("src-1", "a.mp4")
    assert first == entity_id_for("src-1", "a.mp4")
    assert first != entity_id_for("src-2", "a.mp4"), "разные источники — разные id"
    assert first != entity_id_for("src-1", "b.mp4")


@pytest.mark.parametrize(("source_id", "key"), [("", "a"), ("s", "")])
def test_entity_id_rejects_empty_parts(source_id: str, key: str) -> None:
    with pytest.raises(ValueError):
        entity_id_for(source_id, key)


async def test_policy_compliant_source_passes() -> None:
    await run_source_sync_contract(lambda: Source([make_entity("a.mp4")]), CONTRACT_SCHEMA)


async def test_wrong_id_scheme_is_reported() -> None:
    source = Source([make_entity("a.mp4", use_policy_id=False)])
    with pytest.raises(AssertionError, match="does not follow entity_id_for"):
        await run_source_sync_contract(lambda: source, CONTRACT_SCHEMA)


async def test_missing_content_hash_is_reported() -> None:
    with pytest.raises(AssertionError, match="content_hash"):
        await run_source_sync_contract(
            lambda: Source([make_entity("a.mp4", content_hash=None)]), CONTRACT_SCHEMA
        )


class UnstableSource(Source):
    def __init__(self) -> None:
        self._call = 0

    async def scan(self) -> AsyncIterator[Entity]:
        self._call += 1
        yield make_entity(f"file-{self._call}.mp4")


async def test_unstable_objects_are_reported() -> None:
    """Один экземпляр источника: второй скан отдаёт другие объекты."""
    unstable = UnstableSource()
    with pytest.raises(AssertionError, match="must be stable"):
        await run_source_sync_contract(lambda: unstable, CONTRACT_SCHEMA)


async def test_missing_origin_is_reported() -> None:
    orphan = Entity(id=EntityId("x"), kind="edit")
    with pytest.raises(AssertionError, match="must set origin"):
        await run_source_sync_contract(lambda: Source([orphan]), CONTRACT_SCHEMA)
