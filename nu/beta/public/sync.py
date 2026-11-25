"""Синхронизация состояния хранилища с источником (ADR-0016).

`plan_sync` — чистая функция: сравнивает то, что отдал скан источника, с
тем, что уже лежит в хранилище, и возвращает план действий и конфликты.
Применение плана (`apply_plan`) — отдельный шаг, поэтому семантику можно
проверять без бэкенда.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from nu.psi.contracts.alpha import Entity, EntityId, FacetOwner, FacetValue, Provenance
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
            actions.append(
                SyncAction(
                    ActionKind.RESURRECT, merge_entity(entity, previous), previous_id=previous.id
                )
            )
        elif _same_source_facts(previous, entity):
            continue
        else:
            actions.append(
                SyncAction(
                    ActionKind.UPDATE,
                    inherit_derived(merge_entity(entity, previous), existing),
                    previous_id=previous.id,
                )
            )

    for entity in pending:
        assert entity.origin is not None  # проверено выше
        target = (
            _find_move_candidate(entity, source_entities, matched, scanned_keys)
            if policy.detect_moves
            else []
        )
        if not target:
            actions.append(SyncAction(ActionKind.CREATE, inherit_derived(entity, existing)))
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
                inherit_derived(
                    merge_entity(entity, previous).model_copy(update={"id": previous.id}),
                    existing,
                ),
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


def inherit_derived(target: Entity, donors: Iterable[Entity]) -> Entity:
    """Подхватить производные фасеты у объектов с тем же содержимым (ADR-0017).

    Отдельного кэша нет: им служит само хранилище. Ключ — `content_hash`,
    а версия анализатора берётся из `derived_by` донора: при смене версии
    её увидит сам анализатор, сверяя provenance.

    Копируются только фасеты с владельцем `analysis`. При нескольких
    донорах выигрывает самый свежий `Provenance.at`; если время совпадает,
    а значения разные — ось пропускается (неоднозначность не разгадываем).
    """
    origin = target.origin
    if origin is None or not origin.content_hash:
        return target

    best: dict[str, tuple[tuple[FacetValue, ...], Provenance]] = {}
    ambiguous: set[str] = set()

    for donor in donors:
        donor_origin = donor.origin
        if (
            donor.id == target.id
            or donor_origin is None
            or donor_origin.content_hash != origin.content_hash
            or donor.deleted_at is not None
        ):
            continue
        for axis, values in donor.facets.items():
            if axis in target.facets:
                continue
            provenance = donor.derived_by.get(axis)
            if donor.owners.get(axis) is not FacetOwner.ANALYSIS or provenance is None:
                continue

            current = best.get(axis)
            if current is None or provenance.at > current[1].at:
                best[axis] = (values, provenance)
                ambiguous.discard(axis)
            elif provenance.at == current[1].at and values != current[0]:
                ambiguous.add(axis)

    if not best:
        return target

    facets = dict(target.facets)
    owners = dict(target.owners)
    derived = dict(target.derived_by)
    for axis in sorted(best):
        if axis in ambiguous:
            continue
        values, provenance = best[axis]
        facets[axis] = values
        owners[axis] = FacetOwner.ANALYSIS
        derived[axis] = provenance

    return target.model_copy(update={"facets": facets, "owners": owners, "derived_by": derived})


def merge_entity(scanned: Entity, existing: Entity) -> Entity:
    """Слить объект источника с сохранёнными чужими фасетами (ADR-0018).

    Правила:
    - фасет источника обновляется значением из скана;
    - фасет, который источник больше не отдаёт (владелец `source`),
      удаляется — источник авторитетен для своих осей;
    - фасеты `user` и `analysis` сохраняются как есть;
    - `derived_by` сохраняется только для сохранившихся фасетов.
    """
    facets = dict(scanned.facets)
    owners = dict.fromkeys(facets, FacetOwner.SOURCE)
    for axis, values in existing.facets.items():
        if axis in facets:
            continue
        owner = existing.owners.get(axis, FacetOwner.USER)
        if owner is FacetOwner.SOURCE:
            continue
        facets[axis] = values
        owners[axis] = owner

    derived = {
        axis: provenance
        for axis, provenance in existing.derived_by.items()
        if axis in facets and owners.get(axis) is FacetOwner.ANALYSIS
    }
    return scanned.model_copy(
        update={
            "facets": facets,
            "owners": owners,
            "derived_by": derived,
            "deleted_at": None,
        }
    )


async def apply_plan(engine: IStorageEngine, plan: SyncPlan) -> int:
    """Применить план к хранилищу. Возвращает число выполненных действий."""
    applied = 0
    for action in plan.actions:
        errors = await engine.upsert(action.entity)
        if errors:
            raise SyncError(f"cannot apply {action.kind.value} for {action.entity.id}: {errors[0]}")
        applied += 1
    return applied


def _same_source_facts(previous: Entity, scanned: Entity) -> bool:
    """Совпадают ли факты источника: содержимое и его собственные фасеты.

    Фасеты `user`/`analysis` в сравнение не входят — иначе ручная правка
    выглядела бы как изменение источника и запускала бы перезапись.
    """
    prev_hash = previous.origin.content_hash if previous.origin else None
    next_hash = scanned.origin.content_hash if scanned.origin else None
    if prev_hash != next_hash or previous.scalars != scanned.scalars:
        return False
    if previous.kind != scanned.kind:
        return False
    return _source_facets(previous) == scanned.facets


def _source_facets(entity: Entity) -> dict[str, object]:
    """Фасеты, которыми владеет источник."""
    return {
        axis: values
        for axis, values in entity.facets.items()
        if entity.owners.get(axis, FacetOwner.SOURCE) is FacetOwner.SOURCE
    }


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
    "inherit_derived",
    "plan_sync",
]
