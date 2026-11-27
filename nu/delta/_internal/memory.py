"""In-memory бэкенд: словари и списки, никакого SQL (ADR-0013).

Эталон семантики: `tau/contract/` проверяет его так же, как любой
внешний бэкенд-плагин.
"""

from __future__ import annotations

from collections.abc import Sequence

from nu.delta.public.errors import StorageQueryError
from nu.delta.public.interfaces import IReferenceIndex, IStorageEngine
from nu.psi.contracts.alpha import (
    Artifact,
    ArtifactRef,
    AxisDefinition,
    AxisKind,
    Capability,
    DomainError,
    Entity,
    EntityId,
    ErrorCode,
    Filter,
    MeasurableValue,
    Operator,
    Query,
    QueryResult,
    ReferenceLink,
    ReferenceValue,
    ScalarDefinition,
    StorageSchema,
)
from nu.psi.contracts.beta import (
    validate_artifact,
    validate_axis,
    validate_entity,
    validate_query,
    validate_scalar,
)

#: Всё, что умеет память: полный перебор всегда доступен, ссылки проверяемы.
MEMORY_CAPABILITIES: frozenset[Capability] = frozenset(
    {
        Capability.QUERY_CATEGORICAL,
        Capability.QUERY_MEASURABLE,
        Capability.QUERY_REFERENCE,
        Capability.SCALAR_SEARCH,
        Capability.REFERENCE_CHECK,
        Capability.WRITE_BULK,
        Capability.DYNAMIC_AXES,
        Capability.ARTIFACTS,
        Capability.TRAVERSE_REFERENCES,
    }
)


class MemoryStorage(IStorageEngine, IReferenceIndex):
    """Хранилище в оперативной памяти.

    Разреженность честная: отсутствующая ось не материализуется ни во что
    (ADR-0010). Порядок выдачи — по `id`, чтобы контрактные тесты не
    зависели от порядка вставки.
    """

    def __init__(self, schema: StorageSchema | None = None) -> None:
        self._schema = schema or StorageSchema()
        self._entities: dict[EntityId, Entity] = {}
        self._artifacts: dict[str, Artifact] = {}
        #: Обратный индекс: цель -> ось -> источники (ADR-0021).
        self._incoming: dict[EntityId, dict[str, set[EntityId]]] = {}

    # ---------------------------------------------------------------- схема

    async def get_schema(self) -> StorageSchema:
        return self._schema

    async def add_axis(self, axis: AxisDefinition) -> list[DomainError]:
        errors = validate_axis(self._schema, axis)
        if not errors:
            self._schema = self._schema.with_axis(axis)
        return errors

    async def add_scalar(self, scalar: ScalarDefinition) -> list[DomainError]:
        errors = validate_scalar(self._schema, scalar)
        if not errors:
            self._schema = self._schema.with_scalar(scalar)
        return errors

    # --------------------------------------------------------------- запись

    async def upsert(self, entity: Entity) -> list[DomainError]:
        errors = validate_entity(
            self._schema,
            entity,
            known_ids={*self._entities, entity.id},
            known_artifacts={*self._artifacts},
            capabilities=self.capabilities(),
        )
        if not errors:
            self._index(previous=self._entities.get(entity.id), current=entity)
        return errors

    async def bulk_upsert(self, entities: Sequence[Entity]) -> list[DomainError]:
        """Записать пачку: ссылки могут указывать на любой объект пачки.

        Проверка ссылок идёт по множеству «уже сохранённые + все `id` из
        пачки», поэтому порядок объектов в пачке не важен. Пачка атомарна:
        при любой ошибке не пишется ничего — иначе ссылка на отвергнутый
        объект пачки стала бы висячей.
        """
        batch_ids = {entity.id for entity in entities}
        known_ids = {*self._entities, *batch_ids}
        errors: list[DomainError] = []
        for entity in entities:
            errors.extend(
                validate_entity(
                    self._schema,
                    entity,
                    known_ids=known_ids,
                    known_artifacts={*self._artifacts},
                    capabilities=self.capabilities(),
                )
            )
        if errors:
            return errors
        for entity in entities:
            self._index(previous=self._entities.get(entity.id), current=entity)
        return []

    # ------------------------------------------------------ обратные ссылки

    def _index(self, previous: Entity | None, current: Entity) -> None:
        """Заменить вклад объекта в обратный индекс (ADR-0021).

        Индекс строится по всем ссылкам, включая tombstone: видимость
        решается на чтении, иначе воскрешение объекта требовало бы
        переиндексации.
        """
        if previous is not None:
            self._unindex(previous)
        self._entities[current.id] = current
        for axis, values in current.facets.items():
            for value in values:
                if isinstance(value, ReferenceValue):
                    self._incoming.setdefault(value.target, {}).setdefault(axis, set()).add(
                        current.id
                    )

    def _unindex(self, entity: Entity) -> None:
        for axis, values in entity.facets.items():
            for value in values:
                if not isinstance(value, ReferenceValue):
                    continue
                by_axis = self._incoming.get(value.target)
                if by_axis is None:
                    continue
                sources = by_axis.get(axis)
                if sources is None:
                    continue
                sources.discard(entity.id)
                if not sources:
                    del by_axis[axis]
                if not by_axis:
                    del self._incoming[value.target]

    async def references_to(
        self,
        entity_id: EntityId,
        axes: Sequence[str] | None = None,
        *,
        include_deleted: bool = False,
    ) -> tuple[ReferenceLink, ...]:
        by_axis = self._incoming.get(entity_id, {})
        wanted = sorted(by_axis) if axes is None else sorted({*axes} & {*by_axis})
        links: list[ReferenceLink] = []
        for axis in wanted:
            for source in sorted(by_axis[axis]):
                if include_deleted or _visible(self._entities.get(source)):
                    links.append(ReferenceLink(axis=axis, entity_id=source))
        return tuple(links)

    # --------------------------------------------------------------- чтение

    async def get(self, entity_id: EntityId) -> Entity | None:
        entity = self._entities.get(entity_id)
        return entity if _visible(entity) else None

    async def fetch_many(self, ids: Sequence[EntityId]) -> tuple[Entity, ...]:
        found = (
            self._entities[entity_id]
            for entity_id in ids
            if entity_id in self._entities and _visible(self._entities[entity_id])
        )
        return tuple(found)

    async def count(self) -> int:
        return sum(1 for entity in self._entities.values() if _visible(entity))

    async def list_entities(self, include_deleted: bool = False) -> tuple[Entity, ...]:
        entities = (self._entities[entity_id] for entity_id in sorted(self._entities))
        return tuple(entity for entity in entities if include_deleted or _visible(entity))

    # --------------------------------------------------------------- запрос

    async def query(self, query: Query) -> QueryResult:
        errors = validate_query(self._schema, query, self.capabilities())
        if errors:
            raise StorageQueryError(errors)

        matched = [
            entity_id
            for entity_id in sorted(self._entities)
            if _visible(self._entities[entity_id])
            and all(
                _matches(self._entities[entity_id], condition, self._schema)
                for condition in query.all
            )
        ]
        total = len(matched)
        window = matched[query.offset :]
        if query.limit is not None:
            window = window[: query.limit]
        return QueryResult(ids=tuple(window), total=total, limit=query.limit, offset=query.offset)

    # ------------------------------------------------------------ артефакты

    async def put_artifact(self, artifact: Artifact) -> list[DomainError]:
        errors = validate_artifact(artifact, self.capabilities())
        if errors:
            return errors

        stored = self._artifacts.get(artifact.content_hash)
        if stored is not None and stored.media_type != artifact.media_type:
            return [
                DomainError(
                    code=ErrorCode.ARTIFACT_MISMATCH,
                    detail=(
                        f"artifact {artifact.content_hash!r} is already stored as "
                        f"{stored.media_type!r}, not {artifact.media_type!r}"
                    ),
                )
            ]
        self._artifacts[artifact.content_hash] = artifact
        return []

    async def get_artifact(self, content_hash: str) -> Artifact | None:
        return self._artifacts.get(content_hash)

    async def list_artifacts(self) -> tuple[ArtifactRef, ...]:
        return tuple(
            ArtifactRef(
                content_hash=artifact.content_hash,
                media_type=artifact.media_type,
                size=artifact.size,
            )
            for _, artifact in sorted(self._artifacts.items())
        )

    async def delete_artifact(self, content_hash: str) -> list[DomainError]:
        users = sorted(
            str(entity.id)
            for entity in self._entities.values()
            if content_hash in {ref.content_hash for ref in entity.artifacts.values()}
        )
        if users:
            return [
                DomainError(
                    code=ErrorCode.ARTIFACT_IN_USE,
                    detail=(
                        f"artifact {content_hash!r} is referenced by "
                        f"{', '.join(users)}; remove the references first"
                    ),
                    entity_id=EntityId(users[0]),
                )
            ]
        self._artifacts.pop(content_hash, None)
        return []

    def capabilities(self) -> frozenset[Capability]:
        return MEMORY_CAPABILITIES


def _visible(entity: Entity | None) -> bool:
    """Объект есть и не помечен удалённым."""
    return entity is not None and entity.deleted_at is None


def _matches(entity: Entity, condition: Filter, schema: StorageSchema) -> bool:
    """Один фильтр против объекта (DOMAIN §5: отсутствие — false, кроме none_of/not_exists)."""
    if condition.op is Operator.SCALAR_EQ:
        return entity.scalars.get(condition.axis) == str(condition.values[0])

    values = entity.facets.get(condition.axis)

    if condition.op is Operator.EXISTS:
        return bool(values)
    if condition.op is Operator.NOT_EXISTS:
        return not values
    if values is None:
        return condition.op is Operator.NONE_OF

    axis = schema.axis(condition.axis)
    kind = axis.kind if axis is not None else None

    if condition.op is Operator.CONTAINS:
        return any(_equal(value, condition.values[0], kind) for value in values)
    if condition.op is Operator.ANY_OF:
        return any(
            _equal(value, candidate, kind) for value in values for candidate in condition.values
        )
    if condition.op is Operator.NONE_OF:
        return not any(
            _equal(value, candidate, kind) for value in values for candidate in condition.values
        )

    numbers = [value.value for value in values if isinstance(value, MeasurableValue)]
    if not numbers:
        return False
    return any(_compare(number, condition) for number in numbers)


def _equal(value: object, candidate: str | float, kind: AxisKind | None) -> bool:
    if isinstance(value, MeasurableValue):
        return kind is AxisKind.MEASURABLE and value.value == float(candidate)
    if isinstance(value, ReferenceValue):
        return value.target == candidate
    return getattr(value, "value", None) == candidate


def _compare(number: float, condition: Filter) -> bool:
    """Числовое сравнение; `between` — inclusive с двух сторон."""
    first = float(condition.values[0])
    if condition.op is Operator.EQ:
        return number == first
    if condition.op is Operator.GT:
        return number > first
    if condition.op is Operator.LT:
        return number < first
    if condition.op is Operator.GTE:
        return number >= first
    if condition.op is Operator.LTE:
        return number <= first
    if condition.op is Operator.BETWEEN:
        second = float(condition.values[1])
        low, high = sorted((first, second))
        return low <= number <= high
    return False  # pragma: no cover - защита от неверного оператора


__all__ = ["MEMORY_CAPABILITIES", "MemoryStorage"]
