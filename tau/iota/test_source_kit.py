"""Контрактный набор источников: проходит на корректном, ловит нарушения."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

import pytest

from nu.contracts import run_source_contract
from nu.delta.public.interfaces import IEntitySource
from nu.iota.public.contract_kit import CONTRACT_SCHEMA
from nu.psi.contracts.alpha import CategoricalValue, Entity, EntityId

ENTITIES: tuple[Entity, ...] = (
    Entity(
        id=EntityId("a-1"),
        kind="edit",
        facets={"theme": (CategoricalValue(value="cyberpunk"),)},
    ),
    Entity(id=EntityId("b-2"), kind="note"),
)


class ListSource(IEntitySource):
    """Источник поверх готового списка — эталон для набора."""

    def __init__(self, entities: Sequence[Entity] = ENTITIES, description: str = "list") -> None:
        self._entities = entities
        self._description = description

    def describe(self) -> str:
        return self._description

    async def scan(self) -> AsyncIterator[Entity]:
        for entity in self._entities:
            yield entity


async def test_reference_source_passes_contract() -> None:
    await run_source_contract(ListSource, CONTRACT_SCHEMA)


async def test_empty_description_is_reported() -> None:
    with pytest.raises(AssertionError, match="describe"):
        await run_source_contract(lambda: ListSource(description="   "), CONTRACT_SCHEMA)


async def test_duplicate_ids_are_reported() -> None:
    doubled = (ENTITIES[0], ENTITIES[0])
    with pytest.raises(AssertionError, match="duplicate entity id"):
        await run_source_contract(lambda: ListSource(doubled), CONTRACT_SCHEMA)


async def test_unknown_axis_is_reported() -> None:
    broken = (
        Entity(
            id=EntityId("x"),
            kind="edit",
            facets={"colour": (CategoricalValue(value="red"),)},
        ),
    )
    with pytest.raises(AssertionError, match="invalid against schema"):
        await run_source_contract(lambda: ListSource(broken), CONTRACT_SCHEMA)


class UnstableSource(IEntitySource):
    """Меняет id между сканированиями — импорт был бы неидемпотентным."""

    def __init__(self) -> None:
        self._call = 0

    def describe(self) -> str:
        return "unstable"

    async def scan(self) -> AsyncIterator[Entity]:
        self._call += 1
        yield Entity(id=EntityId(f"id-{self._call}"), kind="note")


async def test_non_deterministic_ids_are_reported() -> None:
    with pytest.raises(AssertionError, match="scan must be deterministic"):
        await run_source_contract(UnstableSource, CONTRACT_SCHEMA)
