"""Синхронизация источника: все шесть случаев ADR-0016 на чистом плане."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from nu.beta.public.sync import (
    ActionKind,
    SyncError,
    SyncPolicy,
    apply_plan,
    plan_sync,
)
from nu.delta._internal.memory import MemoryStorage
from nu.psi.contracts.alpha import (
    AxisDefinition,
    AxisKind,
    CategoricalValue,
    Entity,
    EntityId,
    Origin,
    StorageSchema,
)

SOURCE = "src-owner-media"
NOW = datetime(2025, 11, 25, tzinfo=UTC)


def entity(
    entity_id: str,
    key: str,
    content_hash: str | None = "h1",
    *,
    source: str = SOURCE,
    facets: dict[str, Any] | None = None,
    deleted_at: datetime | None = None,
) -> Entity:
    return Entity(
        id=EntityId(entity_id),
        kind="video",
        facets={name: (CategoricalValue(value=value),) for name, value in (facets or {}).items()},
        origin=Origin(
            source_id=source,
            key=key,
            content_hash=content_hash,
            hash_algo="partial" if content_hash else None,
        ),
        deleted_at=deleted_at,
    )


def policy(**kwargs: Any) -> SyncPolicy:
    return SyncPolicy(source_id=SOURCE, **kwargs)


def kinds(plan: Any) -> list[str]:
    return [action.kind.value for action in plan.actions]


# ------------------------------------------------------------------ создание


def test_new_object_is_created() -> None:
    plan = plan_sync([entity("a", "file-a.mp4")], [], policy(), now=NOW)
    assert kinds(plan) == ["create"]
    assert plan.conflicts == ()


def test_unchanged_object_produces_no_actions() -> None:
    same = entity("a", "file-a.mp4")
    plan = plan_sync([same], [same], policy(), now=NOW)
    assert plan.actions == ()


def test_changed_content_updates_entity() -> None:
    old = entity("a", "file-a.mp4", "h1")
    new = entity("a", "file-a.mp4", "h2")
    plan = plan_sync([new], [old], policy(), now=NOW)
    assert kinds(plan) == ["update"]
    assert plan.actions[0].entity.origin is not None
    assert plan.actions[0].entity.origin.content_hash == "h2"


# ------------------------------------------------------------ переименование


def test_rename_keeps_old_id() -> None:
    old = entity("a", "old.mp4", "h1")
    renamed = entity("b", "new.mp4", "h1")  # адаптер дал id по новому ключу
    plan = plan_sync([renamed], [old], policy(), now=NOW)

    assert kinds(plan) == ["move"]
    action = plan.actions[0]
    assert action.entity.id == EntityId("a"), "id должен сохраниться"
    assert action.previous_id == EntityId("a")
    assert action.entity.origin is not None
    assert action.entity.origin.key == "new.mp4"


def test_rename_without_hash_falls_back_to_create_and_tombstone() -> None:
    old = entity("a", "old.mp4", None)
    renamed = entity("b", "new.mp4", None)
    plan = plan_sync([renamed], [old], policy(), now=NOW)

    assert sorted(kinds(plan)) == ["create", "tombstone"]


def test_ambiguous_move_is_conflict() -> None:
    first = entity("a", "a.mp4", "h1")
    second = entity("b", "b.mp4", "h1")
    moved = entity("c", "c.mp4", "h1")

    plan = plan_sync([moved], [first, second], policy(), now=NOW)
    assert kinds(plan) == []
    assert "ambiguous move" in plan.conflicts[0].reason


def test_moves_can_be_disabled() -> None:
    old = entity("a", "old.mp4", "h1")
    renamed = entity("b", "new.mp4", "h1")
    plan = plan_sync([renamed], [old], policy(detect_moves=False), now=NOW)
    assert sorted(kinds(plan)) == ["create", "tombstone"]


# ------------------------------------------------------------------ удаление


def test_missing_object_is_tombstoned_on_complete_scan() -> None:
    old = entity("a", "a.mp4")
    plan = plan_sync([], [old], policy(), now=NOW)

    assert kinds(plan) == ["tombstone"]
    assert plan.actions[0].entity.deleted_at == NOW


def test_incomplete_scan_does_not_tombstone() -> None:
    old = entity("a", "a.mp4")
    plan = plan_sync([], [old], policy(complete=False), now=NOW)
    assert plan.actions == ()


def test_already_tombstoned_object_is_skipped() -> None:
    old = entity("a", "a.mp4", deleted_at=NOW)
    plan = plan_sync([], [old], policy(), now=NOW)
    assert plan.actions == ()


def test_returned_object_is_resurrected() -> None:
    old = entity("a", "a.mp4", "h1", deleted_at=NOW)
    back = entity("a", "a.mp4", "h1")
    plan = plan_sync([back], [old], policy(), now=NOW)

    assert kinds(plan) == ["resurrect"]
    assert plan.actions[0].entity.deleted_at is None


# ------------------------------------------------------------------ конфликты


def test_foreign_source_is_ignored_with_conflict() -> None:
    foreign = entity("x", "x.mp4", source="other-source")
    plan = plan_sync([foreign], [], policy(), now=NOW)
    assert kinds(plan) == []
    assert "another source" in plan.conflicts[0].reason


def test_missing_origin_is_conflict() -> None:
    orphan = Entity(id=EntityId("x"), kind="video")
    plan = plan_sync([orphan], [], policy(), now=NOW)
    assert "no origin" in plan.conflicts[0].reason


def test_tombstoned_scan_input_is_conflict() -> None:
    plan = plan_sync([entity("a", "a.mp4", deleted_at=NOW)], [], policy(), now=NOW)
    assert "must not be tombstoned" in plan.conflicts[0].reason


def test_duplicate_keys_are_conflict() -> None:
    plan = plan_sync(
        [entity("a", "same.mp4"), entity("b", "same.mp4", "h2")], [], policy(), now=NOW
    )
    assert kinds(plan) == ["create"]
    assert "duplicate key" in plan.conflicts[0].reason


def test_same_key_different_id_is_conflict() -> None:
    old = entity("a", "a.mp4")
    wrong = entity("b", "a.mp4")
    plan = plan_sync([wrong], [old], policy(), now=NOW)
    assert "different id" in plan.conflicts[0].reason


# ------------------------------------------------------------------ прочее


def test_other_sources_are_out_of_scope() -> None:
    other = entity("z", "z.mp4", source="another")
    plan = plan_sync([], [other], policy(), now=NOW)
    assert plan.actions == (), "чужой источник не трогаем"


def test_kinds_counter() -> None:
    old = entity("a", "a.mp4", "h1")
    plan = plan_sync(
        [entity("b", "b.mp4", "h1"), entity("c", "c.mp4", "h9")],
        [old],
        policy(),
        now=NOW,
    )
    assert plan.kinds() == {"move": 1, "create": 1}


async def test_apply_plan_writes_to_storage() -> None:
    schema = StorageSchema(axes=(AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL),))
    engine = MemoryStorage(schema=schema)
    await engine.add_axis(AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL))

    scanned = [
        entity("a", "a.mp4", facets={"theme": "noir"}),
        entity("b", "b.mp4", "h2", facets={"theme": "noir"}),
    ]
    plan = plan_sync(scanned, [], policy(), now=NOW)
    assert await apply_plan(engine, plan) == 2
    assert await engine.count() == 2


async def test_apply_plan_reports_invalid_entity() -> None:
    engine = MemoryStorage(schema=StorageSchema())
    plan = plan_sync([entity("a", "a.mp4", facets={"unknown": "x"})], [], policy(), now=NOW)
    with pytest.raises(SyncError, match="cannot apply"):
        await apply_plan(engine, plan)


def test_entity_requires_timezone_aware_deleted_at() -> None:
    with pytest.raises(ValueError):
        entity("a", "a.mp4", deleted_at=datetime(2025, 1, 1))


def test_action_kind_is_stable() -> None:
    assert ActionKind.TOMBSTONE.value == "tombstone"
