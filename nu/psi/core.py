"""Ядро как объект: единственный вход для продукта и клиентов.

Продукт не собирает движок сам — он получает `Core` и работает через
него. Внутри `Core` нет бизнес-логики: это фасад над портом хранилища и
проверками `beta`.
"""

from __future__ import annotations

from dataclasses import dataclass

from nu.psi.contracts.alpha import (
    Artifact,
    ArtifactRef,
    AxisDefinition,
    Capability,
    DomainError,
    Entity,
    EntityId,
    Query,
    QueryResult,
    ScalarDefinition,
    StorageSchema,
)
from nu.psi.contracts.beta import validate_query
from nu.psi.contracts.delta import IStorageEngine


@dataclass(frozen=True, slots=True)
class Core:
    """Многомерное ядро поверх конкретного хранилища."""

    storage: IStorageEngine

    async def schema(self) -> StorageSchema:
        return await self.storage.get_schema()

    async def add_axis(self, axis: AxisDefinition) -> list[DomainError]:
        return await self.storage.add_axis(axis)

    async def add_scalar(self, scalar: ScalarDefinition) -> list[DomainError]:
        return await self.storage.add_scalar(scalar)

    async def upsert(self, entity: Entity) -> list[DomainError]:
        return await self.storage.upsert(entity)

    async def get(self, entity_id: EntityId) -> Entity | None:
        return await self.storage.get(entity_id)

    async def query(self, query: Query) -> QueryResult:
        return await self.storage.query(query)

    async def count(self) -> int:
        return await self.storage.count()

    async def put_artifact(self, artifact: Artifact) -> list[DomainError]:
        return await self.storage.put_artifact(artifact)

    async def get_artifact(self, content_hash: str) -> Artifact | None:
        return await self.storage.get_artifact(content_hash)

    async def list_artifacts(self) -> tuple[ArtifactRef, ...]:
        return await self.storage.list_artifacts()

    async def delete_artifact(self, content_hash: str) -> list[DomainError]:
        return await self.storage.delete_artifact(content_hash)

    def capabilities(self) -> frozenset[Capability]:
        return self.storage.capabilities()

    async def check_query(self, query: Query) -> list[DomainError]:
        """Проверить запрос, не исполняя его (ошибки — значениями)."""
        return validate_query(await self.storage.get_schema(), query, self.capabilities())


__all__ = ["Core"]
