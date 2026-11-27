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
from datetime import UTC, datetime

from nu.iota.public.ids import entity_id_for
from nu.psi.contracts.alpha import (
    Artifact,
    ArtifactRef,
    AxisDefinition,
    AxisKind,
    Capability,
    CategoricalValue,
    Entity,
    EntityId,
    ErrorCode,
    FacetOwner,
    Filter,
    MeasurableValue,
    Operator,
    Query,
    QueryResult,
    ReferenceLink,
    ReferenceValue,
    ScalarDefinition,
    StorageSchema,
    make_artifact,
)
from nu.psi.contracts.beta import validate_entity
from nu.psi.contracts.delta import (
    IEntitySource,
    IReferenceIndex,
    IStorageEngine,
    StorageQueryError,
)

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
    await _check_tombstones(engine)
    await _check_artifacts(engine)
    # Ревизии — последними: их объекты остаются в хранилище (удалять
    # нечего), и в файловом бэкенде они видны остальным проверкам.
    await _check_revisions(factory(schema))


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


async def _check_revisions(engine: IStorageEngine) -> None:
    """Ревизии и оптимистичная блокировка (ADR-0024)."""
    entity = _entity("rev-1")
    assert await engine.upsert(entity, expected_rev=0) == [], "create with expected_rev=0"
    stored = await engine.get(EntityId("rev-1"))
    assert stored is not None and stored.rev == 1, "new object must start at rev 1"

    assert await engine.upsert(entity, expected_rev=1) == [], "update with matching rev"
    stored = await engine.get(EntityId("rev-1"))
    assert stored is not None and stored.rev == 2, "rev must grow on update"

    errors = await engine.upsert(entity, expected_rev=1)
    assert [error.code for error in errors] == [ErrorCode.CONFLICT], (
        "stale expected_rev must be reported as CONFLICT"
    )
    stored = await engine.get(EntityId("rev-1"))
    assert stored is not None and stored.rev == 2, "CONFLICT must not change the object"

    errors = await engine.upsert(_entity("rev-2"), expected_rev=3)
    assert [error.code for error in errors] == [ErrorCode.CONFLICT], (
        "expected_rev for missing object must be CONFLICT"
    )
    assert await engine.get(EntityId("rev-2")) is None, "CONFLICT must not create anything"


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
    "run_source_sync_contract",
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

        assert set(entity.owners) == set(entity.facets), (
            f"source must declare owners for every facet: {sorted(entity.facets)}"
        )
        non_source = sorted(
            axis for axis, owner in entity.owners.items() if owner is not FacetOwner.SOURCE
        )
        assert not non_source, f"source facet owners must be SOURCE, got {non_source}"

        collected.append(entity)
    return tuple(collected)


async def _check_artifacts(engine: IStorageEngine) -> None:
    """Артефакты: адресация по хэшу, дедупликация, ссылки, удаление (ADR-0019)."""
    artifact = make_artifact(b"contract-preview-bytes", "image/png")

    if Capability.ARTIFACTS not in engine.capabilities():
        errors = await engine.put_artifact(artifact)
        assert {error.code for error in errors} == {ErrorCode.UNSUPPORTED_ARTIFACT}, (
            "backend without ARTIFACTS must reject put_artifact with UNSUPPORTED_ARTIFACT"
        )
        assert await engine.get_artifact(artifact.content_hash) is None, (
            "backend without ARTIFACTS must not return artifacts"
        )
        assert await engine.list_artifacts() == (), "backend without ARTIFACTS must list nothing"
        return

    assert await engine.put_artifact(artifact) == [], "put_artifact must accept a valid artifact"
    assert await engine.put_artifact(artifact) == [], "put_artifact must be idempotent"
    assert await engine.list_artifacts() == (
        ArtifactRef(
            content_hash=artifact.content_hash,
            media_type=artifact.media_type,
            size=artifact.size,
        ),
    ), "list_artifacts must report metadata of stored artifacts, deduplicated by hash"
    assert await engine.get_artifact(artifact.content_hash) == artifact, (
        "get_artifact must return the stored bytes"
    )

    same_bytes_other_type = Artifact(
        content_hash=artifact.content_hash, media_type="image/jpeg", data=artifact.data
    )
    mismatch = await engine.put_artifact(same_bytes_other_type)
    assert {error.code for error in mismatch} == {ErrorCode.ARTIFACT_MISMATCH}, (
        "same content hash with another media_type must be rejected"
    )

    reference = ArtifactRef(
        content_hash=artifact.content_hash,
        media_type=artifact.media_type,
        size=artifact.size,
    )
    holder = Entity(id=EntityId("art-1"), kind="edit", artifacts={"preview": reference})
    assert await engine.upsert(holder) == [], "entity may reference a stored artifact"

    in_use = await engine.delete_artifact(artifact.content_hash)
    assert {error.code for error in in_use} == {ErrorCode.ARTIFACT_IN_USE}, (
        "artifact referenced by an object must not be deleted"
    )

    missing = ArtifactRef(content_hash="0" * 64, media_type="image/png", size=1)
    errors = await engine.upsert(
        Entity(id=EntityId("art-2"), kind="edit", artifacts={"preview": missing})
    )
    assert {error.code for error in errors} == {ErrorCode.DANGLING_ARTIFACT}, (
        "reference to a missing artifact must be rejected"
    )

    assert await engine.upsert(holder.model_copy(update={"artifacts": {}})) == [], (
        "dropping the reference must succeed"
    )
    assert await engine.delete_artifact(artifact.content_hash) == [], (
        "unreferenced artifact must be deletable"
    )
    assert await engine.get_artifact(artifact.content_hash) is None, "deleted artifact must be gone"


async def _check_tombstones(engine: IStorageEngine) -> None:
    """Tombstone-семантика: объект скрыт из выдачи, но виден синхронизации."""
    target = EntityId("b-2")
    original = await engine.get(target)
    assert original is not None, "contract entity must exist before tombstone check"

    tombstone = original.model_copy(update={"deleted_at": datetime.now(UTC)})
    errors = await engine.upsert(tombstone)
    assert errors == [], f"tombstone write failed: {errors}"

    assert await engine.get(target) is None, "tombstone must be invisible via get"
    assert await engine.count() == 2, "tombstone must not be counted"

    visible = {str(entity.id) for entity in await engine.list_entities()}
    assert str(target) not in visible, "tombstone must be invisible in list_entities()"
    assert len(visible) == 2, "list_entities() must return visible objects only"

    everything = {str(entity.id) for entity in await engine.list_entities(include_deleted=True)}
    assert str(target) in everything and len(everything) == 3, (
        "list_entities(include_deleted=True) must expose tombstones"
    )

    result = await engine.query(Query())
    assert str(target) not in [str(entity_id) for entity_id in result.ids], (
        "tombstone must not appear in query results"
    )
    assert result.total == 2, "query total must exclude tombstones"

    restored = original.model_copy(update={"deleted_at": None})
    assert await engine.upsert(restored) == [], "resurrect failed"
    assert await engine.count() == 3, "resurrect must bring the object back"


async def run_source_sync_contract(
    factory: Callable[[], IEntitySource], schema: StorageSchema
) -> None:
    """Проверить, что источник пригоден для синхронизации (ADR-0016).

    Дополнительно к базовому набору: повторный скан даёт те же объекты
    целиком (не только те же `id`), `id` соответствует политике
    `entity_id_for(source_id, key)`, у каждого объекта есть
    `content_hash` — без него невозможно отследить переименование.
    """
    first = await _collect(factory(), schema)
    second = await _collect(factory(), schema)

    by_id_first = {str(entity.id): entity for entity in first}
    by_id_second = {str(entity.id): entity for entity in second}
    assert by_id_first == by_id_second, (
        "sync source must be stable: repeated scan produced different objects"
    )

    for entity in first:
        origin = entity.origin
        assert origin is not None, f"sync source must set origin: {entity.id!r}"
        assert str(entity.id) == str(entity_id_for(origin.source_id, origin.key)), (
            f"id {entity.id!r} does not follow entity_id_for(source_id, key)"
        )
        assert origin.content_hash and origin.hash_algo, (
            f"sync source must provide content_hash/hash_algo: {entity.id!r}"
        )


#: Схема для контракта обратных ссылок: две reference-оси и одна обычная.
REFERENCE_CONTRACT_SCHEMA = StorageSchema(
    axes=(
        AxisDefinition(name="links", kind=AxisKind.REFERENCE, multi=True, target="note"),
        AxisDefinition(name="mentions", kind=AxisKind.REFERENCE, multi=True, target="note"),
        AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL, multi=True),
    )
)


def _note(entity_id: str, **facets: object) -> Entity:
    """Объект вида «note» без скаляров: набору важны только ссылки."""
    return Entity.model_validate({"id": entity_id, "kind": "note", "facets": facets})


async def run_reference_index_contract(
    factory: _BACKEND, schema: StorageSchema | None = None
) -> None:
    """Прогнать контракт обратных ссылок (ADR-0021) против фабрики бэкенда.

    Набор имеет смысл только для бэкендов, объявивших
    `Capability.TRAVERSE_REFERENCES`; остальные его не проходят и не должны
    вызывать. Бросает `AssertionError` с описанием нарушения.
    """
    schema = schema or REFERENCE_CONTRACT_SCHEMA
    engine = factory(schema)
    assert isinstance(engine, IReferenceIndex), "backend must implement IReferenceIndex"
    assert Capability.TRAVERSE_REFERENCES in engine.capabilities(), (
        "backend must declare Capability.TRAVERSE_REFERENCES"
    )
    await _check_reference_basics(engine)
    await _check_reference_axes_filter(engine)
    await _check_reference_replace(engine)
    await _check_reference_batch(engine)
    await _check_reference_tombstone(engine)
    await _check_reference_order(engine)


async def _check_reference_basics(engine: IStorageEngine) -> None:
    assert isinstance(engine, IReferenceIndex), "reference checks need the port"
    assert await engine.references_to(EntityId("nobody")) == (), (
        "empty store must have no incoming links"
    )
    await engine.bulk_upsert(
        [_note("src", links=({"kind": "reference", "target": "dst"},)), _note("dst")]
    )
    assert await engine.references_to(EntityId("dst")) == (
        ReferenceLink(axis="links", entity_id=EntityId("src")),
    ), "incoming link must carry axis and source"

    await engine.upsert(_note("plain", theme=({"kind": "categorical", "value": "x"},)))
    assert await engine.references_to(EntityId("plain")) == (), (
        "non-reference facets must not be indexed"
    )


async def _check_reference_axes_filter(engine: IStorageEngine) -> None:
    assert isinstance(engine, IReferenceIndex), "reference checks need the port"
    target = await engine.references_to(EntityId("dst"))
    assert [link.axis for link in target] == ["links"], "only the linking axis is reported"

    await engine.upsert(
        _note(
            "mentions-src",
            mentions=({"kind": "reference", "target": "dst"},),
        )
    )
    both = await engine.references_to(EntityId("dst"))
    assert [link.axis for link in both] == ["links", "mentions"], "all axes by default"
    only = await engine.references_to(EntityId("dst"), ["mentions"])
    assert [link.axis for link in only] == ["mentions"], "axes filter must narrow the result"
    assert await engine.references_to(EntityId("dst"), []) == (), (
        "empty axes sequence means 'no axes', not 'all axes'"
    )
    assert await engine.references_to(EntityId("dst"), ["unknown-axis"]) == (), (
        "unknown axis yields nothing instead of an error"
    )


async def _check_reference_replace(engine: IStorageEngine) -> None:
    assert isinstance(engine, IReferenceIndex), "reference checks need the port"
    await engine.bulk_upsert([_note("mover"), _note("target-a"), _note("target-b")])
    await engine.upsert(_note("mover", links=({"kind": "reference", "target": "target-a"},)))
    assert (await engine.references_to(EntityId("target-a")))[0].entity_id == EntityId("mover")

    await engine.upsert(_note("mover", links=({"kind": "reference", "target": "target-b"},)))
    assert await engine.references_to(EntityId("target-a")) == (), (
        "re-upsert must drop the previous link"
    )
    assert (await engine.references_to(EntityId("target-b")))[0].entity_id == EntityId("mover")

    await engine.upsert(_note("mover"))
    assert await engine.references_to(EntityId("target-b")) == (), (
        "removing the facet must remove the link"
    )


async def _check_reference_batch(engine: IStorageEngine) -> None:
    assert isinstance(engine, IReferenceIndex), "reference checks need the port"
    errors = await engine.bulk_upsert(
        [
            _note("batch-a", links=({"kind": "reference", "target": "batch-b"},)),
            _note("batch-b", links=({"kind": "reference", "target": "batch-c"},)),
            _note("batch-c"),
        ]
    )
    assert errors == [], "batch references must validate across the whole batch"
    sources = await engine.references_to(EntityId("batch-c"))
    assert [str(link.entity_id) for link in sources] == ["batch-b"], (
        "batch must be visible in the reverse index"
    )


async def _check_reference_tombstone(engine: IStorageEngine) -> None:
    assert isinstance(engine, IReferenceIndex), "reference checks need the port"
    deleted = datetime(2026, 1, 1, tzinfo=UTC)
    await engine.bulk_upsert(
        [
            _note("ghost", links=({"kind": "reference", "target": "alive"},)),
            _note("alive"),
        ]
    )
    await engine.upsert(
        _note("ghost", links=({"kind": "reference", "target": "alive"},)).model_copy(
            update={"deleted_at": deleted}
        )
    )
    assert await engine.references_to(EntityId("alive")) == (), (
        "links from tombstone sources are hidden by default"
    )
    revived = await engine.references_to(EntityId("alive"), include_deleted=True)
    assert [str(link.entity_id) for link in revived] == ["ghost"], (
        "include_deleted=True must return tombstone sources"
    )


async def _check_reference_order(engine: IStorageEngine) -> None:
    assert isinstance(engine, IReferenceIndex), "reference checks need the port"
    await engine.bulk_upsert(
        [
            _note(
                "z",
                links=(
                    {"kind": "reference", "target": "hub"},
                    {"kind": "reference", "target": "hub"},
                ),
            ),
            _note("a", links=({"kind": "reference", "target": "hub"},)),
            _note("m", mentions=({"kind": "reference", "target": "hub"},)),
            _note("hub"),
        ]
    )
    links = await engine.references_to(EntityId("hub"))
    assert [(link.axis, str(link.entity_id)) for link in links] == [
        ("links", "a"),
        ("links", "z"),
        ("mentions", "m"),
    ], f"order must be deterministic (axis, then id), got {links}"
