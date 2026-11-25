"""Порт хранилища — контракт модуля `delta`.

`delta` владеет понятием «хранилище» целиком: и портом, и эталонной
реализацией. Модуль не является слоем и не задаёт шаблон для другого
модуля того же проекта; порт нужен для **внешних** реализаций (плагины
хранилищ), которые подключает продукт.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence

from nu.psi.contracts.alpha import (
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


class IStorageEngine(ABC):
    """Бэкенд хранения объектов в пространстве осей.

    Контракт один для всех бэкендов; поведение фиксирует
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
    async def add_scalar(self, scalar: ScalarDefinition) -> list[DomainError]:
        """Добавить текстовое поле в схему."""

    @abstractmethod
    async def upsert(self, entity: Entity) -> list[DomainError]:
        """Вставить или заменить объект по `id`."""

    @abstractmethod
    async def bulk_upsert(self, entities: Sequence[Entity]) -> list[DomainError]:
        """Пакетная запись. Возвращает ошибки по всем объектам пачки.

        Порядок в пачке не важен: ссылка может указывать на любой объект
        этой же пачки (проверка по множеству `id`, а не по префиксу).
        """

    @abstractmethod
    async def get(self, entity_id: EntityId) -> Entity | None:
        """Объект по идентификатору или `None`."""

    @abstractmethod
    async def fetch_many(self, ids: Sequence[EntityId]) -> tuple[Entity, ...]:
        """Объекты по идентификаторам; отсутствующие пропускаются."""

    @abstractmethod
    async def query(self, query: Query) -> QueryResult:
        """Исполнить запрос. Валидацию выполняет `validate_query` из `beta`."""

    @abstractmethod
    async def count(self) -> int:
        """Количество объектов в хранилище."""

    @abstractmethod
    def capabilities(self) -> frozenset[Capability]:
        """Возможности бэкенда (синхронно: это статическое свойство)."""


class IEntitySource(ABC):
    """Источник объектов: внешние данные, приведённые к модели ядра.

    Адаптер (файловое дерево, SQL, внешний API) сам отвечает за
    нормализацию: он решает, что станет осью, а что скаляром, и как
    строить стабильные `id`. Ядро лишь требует, чтобы результат был
    согласован со схемой (это проверяет `run_source_contract`).

    `scan` — асинхронный итератор: дерево может быть большим, и держать
    все объекты в памяти не нужно.
    """

    @abstractmethod
    def describe(self) -> str:
        """Человекочитаемое описание источника (путь, DSN, ...)."""

    @abstractmethod
    def scan(self) -> AsyncIterator[Entity]:
        """Отдать объекты источника. Повторный вызов даёт тот же набор `id`."""


__all__ = ["IEntitySource", "IStorageEngine"]
