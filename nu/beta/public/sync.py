"""Синхронизация состояния хранилища с источником (ADR-0016).

`plan_sync` — чистая функция: сравнивает то, что отдал скан источника, с
тем, что уже лежит в хранилище, и возвращает план действий и конфликты.
Применение плана (`apply_plan`) — отдельный шаг, поэтому семантику можно
проверять без бэкенда.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from nu.psi.contracts.alpha import Entity, EntityId
from nu.psi.contracts.delta import IStorageEngine


class SyncError(ValueError):
    """План нельзя построить: нарушены предусловия."""


class ActionKind(StrEnum):
    """Что сделать с объектом."""

    CREATE = "create"
    UPDATE = "update"
    MOVE = "move"
    TOMBSTONE = "tombstone"
    RESURRECT = "resurrect"


@dataclass(frozen=True, slots=True)
class SyncPolicy:
    """Правила одного прогона синхронизации для одного источника."""

    source_id: str
    #: Искать переименования по `content_hash` (ADR-0016).
    detect_moves: bool = True
    #: Полон ли скан. Неполный скан не порождает tombstone — иначе сбой
    #: чтения превратился бы в массовое удаление.
    complete: bool = True


@dataclass(frozen=True, slots=True)
class SyncAction:
    """Одно действие плана."""

    kind: ActionKind
    entity: Entity
    previous_id: EntityId | None = None


@dataclass(frozen=True, slots=True)
class SyncConflict:
    """Ситуация, которую нельзя разрешить автоматически."""

    reason: str
    key: str | None = None


@dataclass(frozen=True, slots=True)
class SyncPlan:
    """План действий и конфликты."""

    actions: tuple[SyncAction, ...] = ()
    conflicts: tuple[SyncConflict, ...] = ()

    def kinds(self) -> dict[str, int]:
        result: dict[str, int] = {}
        for action in self.actions:
            result[action.kind.value] = result.get(action.kind.value, 0) + 1
        return result


def plan_sync(
    scanned: list[Entity] | tuple[Entity, ...],
    existing: list[Entity] | tuple[Entity, ...],
    policy: SyncPolicy,
    *,
    now: datetime | None = None,
) -> SyncPlan:
    """Построить план приведения хранилища к состоянию источника.

    `existing` — объекты этого источника, включая tombstone (иначе
    «вернувшийся» файл выглядел бы как новый).
    """
    moment = now or datetime.now(UTC)
    actions: list[SyncAction] = []
    conflicts: list[SyncConflict] = []

    source_entities = [
        entity
        for entity in existing
        if entity.origin is not None and entity.origin.source_id == policy.source_id
    ]
    by_key = {entity.origin.key: entity for entity in source_entities if entity.origin}
    matched: set[EntityId] = set()
    scanned_keys: set[str] = set()
    pending: list[Entity] = []

    for entity in scanned:
        origin = entity.origin
        if origin is None or origin.source_id != policy.source_id:
            conflicts.append(
                SyncConflict(
                    reason="scanned entity has no origin or belongs to another source",
                    key=origin.key if origin else None,
                )
            )
            continue
        if entity.deleted_at is not None:
            conflicts.append(
                SyncConflict(reason="scanned entity must not be tombstoned", key=origin.key)
            )
            continue
        if origin.key in scanned_keys:
            conflicts.append(SyncConflict(reason="duplicate key in scan", key=origin.key))
            continue
        scanned_keys.add(origin.key)

        previous = by_key.get(origin.key)
        if previous is None:
            pending.append(entity)
            continue

        if previous.id != entity.id:
            conflicts.append(
                SyncConflict(
                    reason="same key but different id: id must derive from (source_id, key)",
                    key=origin.key,
                )
            )
            continue

        matched.add(previous.id)
        if previous.deleted_at is not None:
            actions.append(SyncAction(ActionKind.RESURRECT, entity, previous_id=previous.id))
        elif _same_facts(previous, entity):
            continue
        else:
            actions.append(SyncAction(ActionKind.UPDATE, entity, previous_id=previous.id))

    for entity in pending:
        assert entity.origin is not None  # проверено выше
        target = (
            _find_move_candidate(entity, source_entities, matched, scanned_keys)
            if policy.detect_moves
            else []
        )
        if not target:
            actions.append(SyncAction(ActionKind.CREATE, entity))
            continue
        if len(target) > 1:
            # Кандидатов не удаляем: выбор делает человек, а tombstone
            # был бы разрушительным действием на основании догадки.
            matched.update(candidate.id for candidate in target)
            conflicts.append(
                SyncConflict(
                    reason="ambiguous move: content hash matches several objects",
                    key=entity.origin.key,
                )
            )
            continue
        previous = target[0]
        matched.add(previous.id)
        actions.append(
            SyncAction(
                ActionKind.MOVE,
                entity.model_copy(update={"id": previous.id}),
                previous_id=previous.id,
            )
        )

    if policy.complete:
        for entity in source_entities:
            if entity.id in matched or entity.deleted_at is not None:
                continue
            if entity.origin is None:  # pragma: no cover - отфильтровано выше
                continue
            if entity.origin.key in scanned_keys:
                continue
            actions.append(
                SyncAction(
                    ActionKind.TOMBSTONE,
                    entity.model_copy(update={"deleted_at": moment}),
                    previous_id=entity.id,
                )
            )

    return SyncPlan(tuple(actions), tuple(conflicts))


async def apply_plan(engine: IStorageEngine, plan: SyncPlan) -> int:
    """Применить план к хранилищу. Возвращает число выполненных действий."""
    applied = 0
    for action in plan.actions:
        errors = await engine.upsert(action.entity)
        if errors:
            raise SyncError(f"cannot apply {action.kind.value} for {action.entity.id}: {errors[0]}")
        applied += 1
    return applied


def _same_facts(previous: Entity, scanned: Entity) -> bool:
    """Совпадают ли факты источника (содержимое, фасеты, скаляры)."""
    prev_hash = previous.origin.content_hash if previous.origin else None
    next_hash = scanned.origin.content_hash if scanned.origin else None
    return (
        prev_hash == next_hash
        and previous.facets == scanned.facets
        and previous.scalars == scanned.scalars
        and previous.kind == scanned.kind
    )


def _find_move_candidate(
    entity: Entity,
    source_entities: list[Entity],
    matched: set[EntityId],
    scanned_keys: set[str],
) -> list[Entity]:
    """Кандидаты на переименование: тот же хэш, ключа нет в скане."""
    content_hash = entity.origin.content_hash if entity.origin else None
    if content_hash is None:
        return []
    return [
        candidate
        for candidate in source_entities
        if candidate.id not in matched
        and candidate.origin is not None
        and candidate.origin.content_hash == content_hash
        and candidate.origin.key not in scanned_keys
        and candidate.deleted_at is None
    ]


__all__ = [
    "ActionKind",
    "SyncAction",
    "SyncConflict",
    "SyncError",
    "SyncPlan",
    "SyncPolicy",
    "apply_plan",
    "plan_sync",
]
