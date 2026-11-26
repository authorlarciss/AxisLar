"""Контрактный набор: бэкенд без артефактов отвергает их, а не молчит.

Третья сторона вправе не поддерживать артефакты (например, бэкенд только
для объектов). Контракт требует явного отказа, а не тихого «нет данных»
(ADR-0019).
"""

from __future__ import annotations

from collections.abc import Sequence

from nu.iota.public.contract_kit import run_storage_contract
from nu.psi.contracts.alpha import (
    Artifact,
    ArtifactRef,
    AxisDefinition,
    Capability,
    DomainError,
    Entity,
    EntityId,
    ErrorCode,
    Query,
    QueryResult,
    ScalarDefinition,
    StorageSchema,
)
from nu.psi.contracts.delta import DeltaResolver, IStorageEngine


class NoArtifactsStore(IStorageEngine):
    """Бэкенд без артефактов: всё остальное делегирует памяти."""

    def __init__(self, inner: IStorageEngine) -> None:
        self._inner = inner

    async def get_schema(self) -> StorageSchema:
        return await self._inner.get_schema()

    async def add_axis(self, axis: AxisDefinition) -> list[DomainError]:
        return await self._inner.add_axis(axis)

    async def add_scalar(self, scalar: ScalarDefinition) -> list[DomainError]:
        return await self._inner.add_scalar(scalar)

    async def upsert(self, entity: Entity) -> list[DomainError]:
        return await self._inner.upsert(entity)

    async def bulk_upsert(self, entities: Sequence[Entity]) -> list[DomainError]:
        return await self._inner.bulk_upsert(entities)

    async def get(self, entity_id: EntityId) -> Entity | None:
        return await self._inner.get(entity_id)

    async def fetch_many(self, ids: Sequence[EntityId]) -> tuple[Entity, ...]:
        return await self._inner.fetch_many(ids)

    async def query(self, query: Query) -> QueryResult:
        return await self._inner.query(query)

    async def count(self) -> int:
        return await self._inner.count()

    async def list_entities(self, include_deleted: bool = False) -> tuple[Entity, ...]:
        return await self._inner.list_entities(include_deleted=include_deleted)

    async def put_artifact(self, artifact: Artifact) -> list[DomainError]:
        return [
            DomainError(
                code=ErrorCode.UNSUPPORTED_ARTIFACT,
                detail="artifacts are not supported by this backend",
            )
        ]

    async def get_artifact(self, content_hash: str) -> Artifact | None:
        return None

    async def list_artifacts(self) -> tuple[ArtifactRef, ...]:
        return ()

    async def delete_artifact(self, content_hash: str) -> list[DomainError]:
        return [
            DomainError(
                code=ErrorCode.UNSUPPORTED_ARTIFACT,
                detail="artifacts are not supported by this backend",
            )
        ]

    def capabilities(self) -> frozenset[Capability]:
        return self._inner.capabilities() - {Capability.ARTIFACTS}


async def test_backend_without_artifacts_passes_contract() -> None:
    await run_storage_contract(
        lambda schema: NoArtifactsStore(DeltaResolver().make_memory_storage(schema=schema))
    )
