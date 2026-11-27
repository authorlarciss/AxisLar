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
    Artifact,
    ArtifactRef,
    AxisDefinition,
    Capability,
    DomainError,
    Entity,
    EntityId,
    Query,
    QueryResult,
    ReferenceLink,
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
    async def upsert(self, entity: Entity, *, expected_rev: int | None = None) -> list[DomainError]:
        """Вставить или заменить объект по `id`.

        `expected_rev` — оптимистичная блокировка (ADR-0024):
        `None` — без проверки; `0` — «должен быть создан» (объекта ещё нет);
        `N > 0` — «изменяю ревизию N». Несовпадение — ошибка `CONFLICT`,
        и в хранилище не пишется ничего. Ревизию ставит бэкенд: 1 при
        создании, `stored + 1` при обновлении; присланное клиентом значение
        `rev` игнорируется.
        """

    @abstractmethod
    async def bulk_upsert(self, entities: Sequence[Entity]) -> list[DomainError]:
        """Пакетная запись. Возвращает ошибки по всем объектам пачки.

        Порядок в пачке не важен: ссылка может указывать на любой объект
        этой же пачки (проверка по множеству `id`, а не по префиксу).

        Пачка атомарна: если хотя бы один объект не прошёл проверку,
        в хранилище не попадает ничего. Иначе ссылка на отвергнутый
        объект пачки осталась бы висячей — а модель её запрещает.
        """

    @abstractmethod
    async def get(self, entity_id: EntityId) -> Entity | None:
        """Объект по идентификатору или `None` (tombstone невидим)."""

    @abstractmethod
    async def fetch_many(self, ids: Sequence[EntityId]) -> tuple[Entity, ...]:
        """Объекты по идентификаторам; отсутствующие пропускаются."""

    @abstractmethod
    async def query(self, query: Query) -> QueryResult:
        """Исполнить запрос. Tombstone в выдачу не попадает."""

    @abstractmethod
    async def count(self) -> int:
        """Количество видимых объектов (tombstone не считается)."""

    @abstractmethod
    async def list_entities(self, include_deleted: bool = False) -> tuple[Entity, ...]:
        """Все объекты источника/хранилища в порядке `id`.

        `include_deleted=True` нужен синхронизации: без tombstone нельзя
        отличить «файл удалён» от «файл вернулся».
        """

    @abstractmethod
    async def put_artifact(self, artifact: Artifact) -> list[DomainError]:
        """Положить артефакт по адресу (idempotent, дедупликация по хэшу).

        Повторная запись тех же байтов — успех без второй копии. Тот же
        адрес с другим `media_type` — `ArtifactMismatch`: два разных
        описания одних байтов хранилище не разгадывает.
        """

    @abstractmethod
    async def get_artifact(self, content_hash: str) -> Artifact | None:
        """Артефакт по адресу или `None`."""

    @abstractmethod
    async def list_artifacts(self) -> tuple[ArtifactRef, ...]:
        """Метаданные всех артефактов в порядке адреса (без байтов)."""

    @abstractmethod
    async def delete_artifact(self, content_hash: str) -> list[DomainError]:
        """Удалить артефакт, на который никто не ссылается.

        Ссылка из любого сохранённого объекта (включая tombstone) даёт
        `ArtifactInUse`: воскрешение объекта не должно оставлять его без
        данных.
        """

    @abstractmethod
    def capabilities(self) -> frozenset[Capability]:
        """Возможности бэкенда (синхронно: это статическое свойство)."""


class IReferenceIndex(ABC):
    """Обратный индекс ссылок: кто указывает на объект (ADR-0021).

    Отдельный порт, а не метод `IStorageEngine`, по той же причине, что и
    `IEntitySource`: это другая роль, а не другая реализация хранения.
    Бэкенд может хранить объекты, но не уметь обход ссылок — тогда он не
    реализует этот порт и не объявляет `Capability.TRAVERSE_REFERENCES`.

    Отношений как сущности в модели нет: обход — это проекция
    reference-фасетов, а не второй вид данных.
    """

    @abstractmethod
    async def references_to(
        self,
        entity_id: EntityId,
        axes: Sequence[str] | None = None,
        *,
        include_deleted: bool = False,
    ) -> tuple[ReferenceLink, ...]:
        """Входящие ссылки на объект: `(ось, объект-источник)`.

        `axes=None` — по всем осям; пустая последовательность — ни по одной
        (пустой результат, а не «все»: явное «никаких» не должно совпадать
        с «не указано»). Ссылки из объектов-tombstone по умолчанию не
        отдаются; `include_deleted=True` возвращает их тоже. Порядок
        детерминирован: по оси, затем по `id` источника.
        """


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


__all__ = ["IEntitySource", "IReferenceIndex", "IStorageEngine"]
