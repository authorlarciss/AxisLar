"""Контракты модуля beta: движок хранилища и резолвер запросов.

Все интерфейсы async — future-proof. Синхронная реализация просто не
содержит `await` (ADR-0014 заменил pipeline-scaffold доменными
контрактами).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from enum import StrEnum

from nu.psi.contracts.alpha import (
    AxisDefinition,
    DomainError,
    Entity,
    EntityId,
    Query,
    QueryResult,
    StorageSchema,
)


class Capability(StrEnum):
    """Что бэкенд реально умеет.

    Запрос, требующий отсутствующей возможности, обязан быть отвергнут
    резолвером (`UnsupportedQuery`), а не исполнен полным перебором в
    обход индексов (ADR-0013).
    """

    QUERY_CATEGORICAL = "query_categorical"
    QUERY_MEASURABLE = "query_measurable"
    QUERY_REFERENCE = "query_reference"
    SCALAR_SEARCH = "scalar_search"
    REFERENCE_CHECK = "reference_check"
    WRITE_BULK = "write_bulk"
    DYNAMIC_AXES = "dynamic_axes"


class IStorageEngine(ABC):
    """Бэкенд хранения объектов в пространстве осей.

    Контракт один для всех бэкендов; его поведение фиксирует
    `tau/contract/`. Ошибки домена возвращаются значениями: пустой список
    означает успех.
    """

    @abstractmethod
    async def get_schema(self) -> StorageSchema:
        """Текущая схема хранилища."""

    @abstractmethod
    async def add_axis(self, axis: AxisDefinition) -> list[DomainError]:
        """Добавить ось. Существующие объекты становятся разреженными (ADR-0010)."""

    @abstractmethod
    async def upsert(self, entity: Entity) -> list[DomainError]:
        """Вставить или заменить объект по `id`."""

    @abstractmethod
    async def bulk_upsert(self, entities: Sequence[Entity]) -> list[DomainError]:
        """Пакетная запись. Возвращает ошибки по всем объектам пачки."""

    @abstractmethod
    async def get(self, entity_id: EntityId) -> Entity | None:
        """Объект по идентификатору или `None`."""

    @abstractmethod
    async def fetch_many(self, ids: Sequence[EntityId]) -> tuple[Entity, ...]:
        """Объекты по идентификаторам; отсутствующие пропускаются."""

    @abstractmethod
    async def query(self, query: Query) -> QueryResult:
        """Исполнить запрос. Валидацию выполняет `IQueryResolver`."""

    @abstractmethod
    async def count(self) -> int:
        """Количество объектов в хранилище."""

    @abstractmethod
    def capabilities(self) -> frozenset[Capability]:
        """Возможности бэкенда (синхронно: это статическое свойство)."""


class IQueryResolver(ABC):
    """Валидация запросов против схемы и возможностей бэкенда.

    Отдельный контракт, а не метод движка: клиент может проверить запрос
    до обращения к хранилищу и получить те же ошибки, что и движок.
    """

    @abstractmethod
    async def check(
        self,
        query: Query,
        schema: StorageSchema,
        capabilities: frozenset[Capability],
    ) -> list[DomainError]:
        """Список ошибок; пустой — запрос исполним."""


__all__ = ["Capability", "IQueryResolver", "IStorageEngine"]
