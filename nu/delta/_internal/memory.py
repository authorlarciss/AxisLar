"""In-memory бэкенд: словари и списки, никакого SQL (ADR-0013).

Эталон семантики: `tau/contract/` проверяет его так же, как любой
внешний бэкенд-плагин.
"""

from __future__ import annotations

from collections.abc import Sequence

from nu.delta.public.errors import StorageQueryError
from nu.delta.public.interfaces import IStorageEngine
from nu.psi.contracts.alpha import (
    AxisDefinition,
    AxisKind,
    Capability,
    DomainError,
    Entity,
    EntityId,
    Filter,
    MeasurableValue,
    Operator,
    Query,
    QueryResult,
    ReferenceValue,
    ScalarDefinition,
    StorageSchema,
)
from nu.psi.contracts.beta import (
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
    }
)


class MemoryStorage(IStorageEngine):
    """Хранилище в оперативной памяти.

    Разреженность честная: отсутствующая ось не материализуется ни во что
    (ADR-0010). Порядок выдачи — по `id`, чтобы контрактные тесты не
    зависели от порядка вставки.
    """

    def __init__(self, schema: StorageSchema | None = None) -> None:
        self._schema = schema or StorageSchema()
        self._entities: dict[EntityId, Entity] = {}

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
            capabilities=self.capabilities(),
        )
        if not errors:
            self._entities[entity.id] = entity
        return errors

    async def bulk_upsert(self, entities: Sequence[Entity]) -> list[DomainError]:
        """Записать пачку: ссылки могут указывать на любой объект пачки.

        Проверка ссылок идёт по множеству «уже сохранённые + все `id` из
        пачки», поэтому порядок объектов в пачке не важен. Гарантия
        существования цели действует после успешной записи пачки.
        """
        batch_ids = {entity.id for entity in entities}
        known_ids = {*self._entities, *batch_ids}
        errors: list[DomainError] = []
        accepted: list[Entity] = []
        for entity in entities:
            found = validate_entity(
                self._schema,
                entity,
                known_ids=known_ids,
                capabilities=self.capabilities(),
            )
            if found:
                errors.extend(found)
            else:
                accepted.append(entity)
        for entity in accepted:
            self._entities[entity.id] = entity
        return errors

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
