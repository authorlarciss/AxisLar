"""Контрактный набор: проходит на эталоне и ловит нарушения."""

from __future__ import annotations

import pytest

from nu.contracts import run_storage_contract
from nu.delta._internal.memory import MemoryStorage
from nu.iota.public.contract_kit import CONTRACT_ENTITIES, CONTRACT_SCHEMA
from nu.psi.contracts.alpha import Capability, Query, QueryResult, StorageSchema
from nu.psi.contracts.delta import DeltaResolver


def memory(schema: StorageSchema | None = None) -> MemoryStorage:
    return MemoryStorage(schema=schema)


async def test_reference_backend_passes_contract() -> None:
    await run_storage_contract(memory)


async def test_kit_works_with_resolver_factory() -> None:
    await run_storage_contract(lambda schema: DeltaResolver().make_memory_storage(schema))


async def test_contract_data_matches_schema() -> None:
    assert {axis.name for axis in CONTRACT_SCHEMA.axes} >= {
        "theme",
        "genre",
        "year",
        "author",
    }
    assert all(entity.id for entity in CONTRACT_ENTITIES)
    assert len({entity.id for entity in CONTRACT_ENTITIES}) == len(CONTRACT_ENTITIES)


class _SilentCapabilities(MemoryStorage):
    def capabilities(self) -> frozenset[Capability]:
        return frozenset()


class _DescendingOrder(MemoryStorage):
    async def query(self, query: Query) -> QueryResult:
        result = await super().query(query)
        if query.limit is None:
            return result
        return result.model_copy(update={"ids": tuple(reversed(result.ids))})


async def test_kit_reports_missing_capabilities() -> None:
    with pytest.raises(AssertionError, match="must declare capabilities"):
        await run_storage_contract(_SilentCapabilities)


async def test_kit_reports_wrong_order() -> None:
    with pytest.raises(AssertionError, match="pagination must be deterministic"):
        await run_storage_contract(_DescendingOrder)
