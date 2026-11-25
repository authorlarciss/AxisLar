"""Контрактный набор бэкендов: проверка сторонних реализаций.

Плагин хранилища обязан пройти этот набор целиком. Набор намеренно не
зависит от pytest: авторы плагинов оборачивают его в свой тест сами.

Использование::

    from nu.contracts import run_storage_contract

    async def test_my_backend() -> None:
        await run_storage_contract(lambda schema: MyStore(path, schema))

Функция проверяет семантику (`lambda/DOMAIN.md` ядра), а не реализацию:
таблицу отсутствующих значений, мультизначность, разреженность,
reference-фасеты, кардинальность, выдачу и пагинацию, отказ на
`any`/`not`.
"""

from __future__ import annotations

from collections.abc import Callable

from nu.psi.contracts.alpha import (
    AxisDefinition,
    AxisKind,
    CategoricalValue,
    Entity,
    EntityId,
    ErrorCode,
    Filter,
    MeasurableValue,
    Operator,
    Query,
    QueryResult,
    ReferenceValue,
    ScalarDefinition,
    StorageSchema,
)
from nu.psi.contracts.beta import validate_entity
from nu.psi.contracts.delta import IEntitySource, IStorageEngine, StorageQueryError

#: Схема, на которой проверяется бэкенд.
CONTRACT_SCHEMA = StorageSchema(
    axes=(
        AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL, multi=True),
        AxisDefinition(
            name="genre", kind=AxisKind.CATEGORICAL, strict=True, values=("noir", "epic")
        ),
        AxisDefinition(name="year", kind=AxisKind.MEASURABLE),
        AxisDefinition(name="author", kind=AxisKind.REFERENCE, target="person"),
    ),
    scalars=(ScalarDefinition(name="title", searchable=True),),
)


def _entity(entity_id: str, **facets: object) -> Entity:
    return Entity.model_validate({"id": entity_id, "kind": "edit", "facets": facets})


#: Объекты контрактного набора: два с фасетами, один разреженный.
CONTRACT_ENTITIES: tuple[Entity, ...] = (
    Entity(
        id=EntityId("a-1"),
        kind="edit",
        scalars={"title": "Alpha"},
        facets={
            "theme": (CategoricalValue(value="cyberpunk"), CategoricalValue(value="noir")),
            "year": (MeasurableValue(value=2024.0),),
            "author": (ReferenceValue(target=EntityId("b-2")),),
        },
    ),
    Entity(
        id=EntityId("b-2"),
        kind="edit",
        scalars={"title": "Beta"},
        facets={
            "theme": (CategoricalValue(value="fantasy"),),
            "year": (MeasurableValue(value=2019.0),),
        },
    ),
    Entity(id=EntityId("c-3"), kind="note", scalars={"title": "Gamma"}),
)

_BACKEND = Callable[[StorageSchema], IStorageEngine]


async def run_storage_contract(factory: _BACKEND, schema: StorageSchema | None = None) -> None:
    """Прогнать контрактный набор против фабрики бэкенда.

    Бросает `AssertionError` с описанием нарушения — пригодно и для pytest,
    и для самопроверки плагина скриптом.
    """
    schema = schema or CONTRACT_SCHEMA
    engine = factory(schema)
    await _check_schema(engine, schema)
    await _check_write(engine)
    await _check_missing_semantics(engine)
    await _check_facets(engine)
    await _check_sparsity(engine)
    await _check_pagination(engine)
    await _check_rejection(engine)


async def _check_schema(engine: IStorageEngine, schema: StorageSchema) -> None:
    assert await engine.get_schema() == schema, "get_schema must return the schema given to factory"
    assert await engine.count() == 0, "new backend must be empty"
    assert engine.capabilities(), "backend must declare capabilities"


async def _check_write(engine: IStorageEngine) -> None:
    errors = await engine.bulk_upsert(CONTRACT_ENTITIES)
    assert errors == [], f"bulk_upsert of valid entities failed: {errors}"
    assert await engine.count() == 3, "bulk_upsert must store all valid entities"

    fetched = await engine.get(EntityId("a-1"))
    assert fetched is not None and len(fetched.facets["theme"]) == 2, "multi-valued facet lost"

    assert await engine.fetch_many((EntityId("a-1"), EntityId("nope"))) == (fetched,), (
        "fetch_many must skip missing ids and keep order"
    )


async def _check_missing_semantics(engine: IStorageEngine) -> None:
    """Обязательная таблица DOMAIN §5."""
    cases: tuple[tuple[Operator, str, tuple[str | float, ...], bool], ...] = (
        (Operator.CONTAINS, "theme", ("cyberpunk",), False),
        (Operator.ANY_OF, "theme", ("cyberpunk", "fantasy"), False),
        (Operator.NONE_OF, "theme", ("cyberpunk",), True),
        (Operator.EXISTS, "theme", (), False),
        (Operator.NOT_EXISTS, "theme", (), True),
        (Operator.EQ, "year", (2019,), False),
        (Operator.GT, "year", (1900,), False),
        (Operator.LT, "year", (9999,), False),
        (Operator.GTE, "year", (1900,), False),
        (Operator.LTE, "year", (9999,), False),
        (Operator.BETWEEN, "year", (1900, 9999), False),
    )
    for op, axis, values, expected in cases:
        result = await engine.query(Query(all=(Filter(axis=axis, op=op, values=values),)))
        present = "c-3" in _ids(result)
        assert present is expected, (
            f"missing-value semantics broken for {op.value} on {axis}: "
            f"expected {'present' if expected else 'absent'}"
        )


async def _check_facets(engine: IStorageEngine) -> None:
    contains = await engine.query(
        Query(all=(Filter(axis="theme", op=Operator.CONTAINS, values=("noir",)),))
    )
    assert _ids(contains) == ["a-1"], "contains must match a multi-valued facet"

    any_of = await engine.query(
        Query(all=(Filter(axis="theme", op=Operator.ANY_OF, values=("fantasy", "noir")),))
    )
    assert _ids(any_of) == ["a-1", "b-2"], "any_of must match objects with any listed value"

    none_of = await engine.query(
        Query(all=(Filter(axis="theme", op=Operator.NONE_OF, values=("noir",)),))
    )
    assert _ids(none_of) == ["b-2", "c-3"], "none_of must keep objects without the axis"

    between = await engine.query(
        Query(all=(Filter(axis="year", op=Operator.BETWEEN, values=(2019, 2024)),))
    )
    assert _ids(between) == ["a-1", "b-2"], "between must be inclusive"

    scalar = await engine.query(
        Query(all=(Filter(axis="title", op=Operator.SCALAR_EQ, values=("Beta",)),))
    )
    assert _ids(scalar) == ["b-2"], "scalar_eq must match exactly"


async def _check_sparsity(engine: IStorageEngine) -> None:
    before = await engine.count()
    errors = await engine.add_axis(AxisDefinition(name="language", kind=AxisKind.CATEGORICAL))
    assert errors == [], f"add_axis on fresh axis failed: {errors}"
    assert await engine.count() == before, "add_axis must not materialise values on old objects"

    present = await engine.query(Query(all=(Filter(axis="language", op=Operator.EXISTS),)))
    assert _ids(present) == [], "old objects must be sparse on a new axis"

    absent = await engine.query(Query(all=(Filter(axis="language", op=Operator.NOT_EXISTS),)))
    assert _ids(absent) == ["a-1", "b-2", "c-3"], "all old objects must be not_exists on new axis"

    duplicate = await engine.add_axis(AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL))
    assert {error.code for error in duplicate} == {ErrorCode.DUPLICATE_AXIS}, (
        "add_axis must reject duplicates"
    )


async def _check_pagination(engine: IStorageEngine) -> None:
    page = await engine.query(Query(limit=2, offset=1))
    assert _ids(page) == ["b-2", "c-3"], "pagination must be deterministic and ordered by id"
    assert page.total == 3 and page.limit == 2 and page.offset == 1, "pagination metadata broken"


async def _check_rejection(engine: IStorageEngine) -> None:
    errors = await engine.upsert(_entity("dangling", author=[{"kind": "reference", "target": "x"}]))
    assert {error.code for error in errors} == {ErrorCode.DANGLING_REFERENCE}, (
        "dangling reference must be rejected on write"
    )

    errors = await engine.upsert(
        _entity(
            "cardinality",
            year=[{"kind": "measurable", "value": 1}, {"kind": "measurable", "value": 2}],
        )
    )
    assert {error.code for error in errors} == {ErrorCode.CARDINALITY_VIOLATION}, (
        "non-multi axis must reject several values"
    )

    errors = await engine.upsert(
        _entity("vocabulary", genre=[{"kind": "categorical", "value": "punk"}])
    )
    assert {error.code for error in errors} == {ErrorCode.UNKNOWN_CATEGORY}, (
        "strict vocabulary must be enforced"
    )

    unsupported = Query.model_validate({"any": [{"axis": "year", "op": "exists"}]})
    try:
        await engine.query(unsupported)
    except StorageQueryError as error:
        assert {item.code for item in error.errors} == {ErrorCode.UNSUPPORTED_QUERY}, (
            "any/not must fail with UNSUPPORTED_QUERY"
        )
    else:  # pragma: no cover - защита от тихой деградации
        raise AssertionError("query with any/not must be rejected, not executed")


def _ids(result: QueryResult) -> list[str]:
    return [str(entity_id) for entity_id in result.ids]


__all__ = [
    "CONTRACT_ENTITIES",
    "CONTRACT_SCHEMA",
    "run_source_contract",
    "run_storage_contract",
]


async def run_source_contract(factory: Callable[[], IEntitySource], schema: StorageSchema) -> None:
    """Проверить адаптер источника против схемы (а не реализацию).

    Требования: `describe()` непустой; `scan()` отдаёт объекты, валидные
    против схемы; `id` непустые и уникальные; повторное сканирование даёт
    тот же набор `id` (иначе импорт не идемпотентен).
    """
    source = factory()
    assert source.describe().strip(), "source.describe() must be non-empty"

    first = await _collect(source, schema)
    second = await _collect(source, schema)

    assert {entity.id for entity in first} == {entity.id for entity in second}, (
        "scan must be deterministic: repeated scan produced different ids"
    )


async def _collect(source: IEntitySource, schema: StorageSchema) -> tuple[Entity, ...]:
    seen: set[str] = set()
    collected: list[Entity] = []
    async for entity in source.scan():
        assert str(entity.id).strip(), "entity id must be non-empty"
        assert str(entity.id) not in seen, f"duplicate entity id in scan: {entity.id!r}"
        seen.add(str(entity.id))

        errors = validate_entity(schema, entity, capabilities=frozenset())
        assert errors == [], f"source produced entity invalid against schema: {errors[0]}"
        collected.append(entity)
    return tuple(collected)
