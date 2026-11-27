"""Обратный индекс ссылок в эталонном бэкенде (ADR-0021)."""

from __future__ import annotations

from datetime import UTC, datetime

from nu.psi.contracts.alpha import (
    AxisDefinition,
    AxisKind,
    Capability,
    CategoricalValue,
    Entity,
    EntityId,
    ReferenceLink,
    ReferenceValue,
    StorageSchema,
)
from nu.psi.contracts.delta import DeltaResolver, IReferenceIndex, IStorageEngine

SCHEMA = StorageSchema(
    axes=(
        AxisDefinition(name="links", kind=AxisKind.REFERENCE, multi=True, target="note"),
        AxisDefinition(name="mentions", kind=AxisKind.REFERENCE, multi=True, target="note"),
        AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL, multi=True),
    )
)


def make_engine() -> IStorageEngine:
    return DeltaResolver().make_memory_storage(schema=SCHEMA)


def note(entity_id: str, **facets: tuple[str, ...]) -> Entity:
    return Entity(
        id=EntityId(entity_id),
        kind="note",
        facets={
            axis: tuple(ReferenceValue(target=EntityId(value)) for value in values)
            for axis, values in facets.items()
        },
    )


def test_capability_is_declared() -> None:
    engine = DeltaResolver().make_memory_storage(schema=SCHEMA)
    assert Capability.TRAVERSE_REFERENCES in engine.capabilities()


async def test_incoming_link_carries_axis_and_source() -> None:
    engine = make_engine()
    assert isinstance(engine, IReferenceIndex), "эталон обязан уметь обход ссылок"
    await engine.bulk_upsert([note("a", links=("b",)), note("b")])

    assert await engine.references_to(EntityId("b")) == (
        ReferenceLink(axis="links", entity_id=EntityId("a")),
    )


async def test_unknown_target_has_no_links() -> None:
    engine = make_engine()
    assert isinstance(engine, IReferenceIndex), "эталон обязан уметь обход ссылок"
    await engine.upsert(note("a", links=("b",)))
    assert await engine.references_to(EntityId("nobody")) == ()


async def test_axes_filter_and_empty_axes_mean_none() -> None:
    engine = make_engine()
    assert isinstance(engine, IReferenceIndex), "эталон обязан уметь обход ссылок"
    await engine.bulk_upsert([note("a", links=("c",), mentions=("c",)), note("c")])

    only_links = await engine.references_to(EntityId("c"), ["links"])
    assert only_links == (ReferenceLink(axis="links", entity_id=EntityId("a")),)

    assert await engine.references_to(EntityId("c"), []) == (), "пустой список — «никаких осей»"
    everything = await engine.references_to(EntityId("c"))
    assert [link.axis for link in everything] == ["links", "mentions"]


async def test_reupsert_replaces_previous_links() -> None:
    engine = make_engine()
    assert isinstance(engine, IReferenceIndex), "эталон обязан уметь обход ссылок"
    await engine.bulk_upsert([note("a", links=("b",)), note("b"), note("c")])

    await engine.upsert(note("a", links=("c",)))
    assert await engine.references_to(EntityId("b")) == ()
    assert await engine.references_to(EntityId("c")) == (
        ReferenceLink(axis="links", entity_id=EntityId("a")),
    )


async def test_removed_facet_removes_link() -> None:
    engine = make_engine()
    assert isinstance(engine, IReferenceIndex), "эталон обязан уметь обход ссылок"
    await engine.bulk_upsert([note("a", links=("b",)), note("b")])

    await engine.upsert(Entity(id=EntityId("a"), kind="note"))
    assert await engine.references_to(EntityId("b")) == ()


async def test_bulk_upsert_sees_references_inside_the_batch() -> None:
    engine = make_engine()
    assert isinstance(engine, IReferenceIndex), "эталон обязан уметь обход ссылок"
    errors = await engine.bulk_upsert(
        [note("first", links=("second",)), note("second", links=("third",)), note("third")]
    )

    assert errors == []
    assert [str(link.entity_id) for link in await engine.references_to(EntityId("third"))] == [
        "second"
    ]


async def test_tombstone_source_is_hidden_unless_requested() -> None:
    engine = make_engine()
    assert isinstance(engine, IReferenceIndex), "эталон обязан уметь обход ссылок"
    await engine.bulk_upsert([note("a", links=("b",)), note("b")])

    await engine.upsert(note("a", links=("b",)).model_copy(update={"deleted_at": _now()}))
    assert await engine.references_to(EntityId("b")) == ()

    revived = await engine.references_to(EntityId("b"), include_deleted=True)
    assert revived == (ReferenceLink(axis="links", entity_id=EntityId("a")),)


async def test_order_is_deterministic_and_ignores_duplicates() -> None:
    engine = make_engine()
    assert isinstance(engine, IReferenceIndex), "эталон обязан уметь обход ссылок"
    await engine.bulk_upsert(
        [
            note("z", links=("t", "t")),
            note("m", mentions=("t",)),
            note("a", links=("t",)),
            note("t"),
        ]
    )

    links = await engine.references_to(EntityId("t"))
    assert [(link.axis, str(link.entity_id)) for link in links] == [
        ("links", "a"),
        ("links", "z"),
        ("mentions", "m"),
    ]


async def test_self_reference_is_recorded() -> None:
    engine = make_engine()
    assert isinstance(engine, IReferenceIndex), "эталон обязан уметь обход ссылок"
    await engine.upsert(note("a", links=("a",)))

    assert await engine.references_to(EntityId("a")) == (
        ReferenceLink(axis="links", entity_id=EntityId("a")),
    )


async def test_non_reference_facets_are_not_indexed() -> None:
    engine = make_engine()
    assert isinstance(engine, IReferenceIndex), "эталон обязан уметь обход ссылок"
    await engine.upsert(
        Entity(
            id=EntityId("a"),
            kind="note",
            facets={"theme": (CategoricalValue(value="x"),)},
        )
    )
    assert await engine.references_to(EntityId("a")) == ()


def _now() -> datetime:
    return datetime(2026, 11, 27, tzinfo=UTC)
