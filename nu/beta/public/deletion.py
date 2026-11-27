"""Политика удаления: tombstone без висячих ссылок (ADR-0025).

Удаления в модели нет — объект помечается tombstone. Проблема не в самом
tombstone, а в ссылках: их проверяют при записи источника
(`DANGLING_REFERENCE`), но не при удалении цели, поэтому висячая ссылка
возникала молча.

Здесь три операции, которых не хватало:

* `tombstone_entity` — пользовательский путь удаления: отказ, если на объект
  ссылаются живые объекты (`REFERENCE_IN_USE`);
* `cascade_order` — порядок, в котором цель можно удалить вместе со
  ссылающимися на неё (сначала ссылающиеся);
* `collect_dangling` — отчёт после синхронизации: какие ссылки стали
  висячими.

`sync` политику не проходит намеренно: источник — владелец своих фактов
(ADR-0016), и запрет на tombstone остановил бы синхронизацию навсегда. Но и
молчать о последствиях он не должен — отсюда `collect_dangling`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from nu.psi.contracts.alpha import (
    Capability,
    DomainError,
    EntityId,
    ErrorCode,
    ReferenceLink,
)
from nu.psi.contracts.delta import IReferenceIndex, IStorageEngine


@dataclass(frozen=True, slots=True)
class DanglingLinks:
    """Живые ссылки, оставшиеся на удалённый объект."""

    target: EntityId
    links: tuple[ReferenceLink, ...]


async def tombstone_entity(
    engine: IStorageEngine,
    entity_id: EntityId,
    *,
    expected_rev: int | None = None,
    now: datetime | None = None,
) -> list[DomainError]:
    """Пометить объект удалённым, если на него никто живой не ссылается.

    Возвращает доменные ошибки (пустой список — удалено). Ничего не пишется,
    если есть живые входящие ссылки (`REFERENCE_IN_USE`) или у бэкенда нет
    обратного индекса (`UNSUPPORTED_CAPABILITY`): политику нельзя проверить —
    значит нельзя и делать вид, что проверили.

    Повторное удаление и удаление неизвестного `id` — не ошибка: результат
    тот же, объекта нет.
    """
    index = _index(engine)
    if index is None:
        return [
            DomainError(
                code=ErrorCode.UNSUPPORTED_CAPABILITY,
                detail="бэкенд не умеет обратные ссылки: удаление нельзя проверить",
                entity_id=entity_id,
            )
        ]
    current = await engine.get(entity_id)
    if current is None:
        return []
    links = await _live_links(index, entity_id)
    if links:
        return [
            DomainError(
                code=ErrorCode.REFERENCE_IN_USE,
                detail=_reference_detail(links),
                axis=_single_axis(links),
                entity_id=entity_id,
            )
        ]
    staged = current.model_copy(update={"deleted_at": now or datetime.now(UTC)})
    rev = current.rev if expected_rev is None else expected_rev
    return await engine.upsert(staged, expected_rev=rev)


async def cascade_order(
    index: IReferenceIndex,
    entity_id: EntityId,
) -> tuple[EntityId, ...]:
    """Порядок удаления цели вместе со ссылающимися: сначала ссылающиеся.

    Обход в глубину с пост-порядком: объект попадает в результат только после
    всех, кто на него ссылается, поэтому пошаговое удаление не упирается в
    `REFERENCE_IN_USE`. Циклы не зацикливают обход (посещённые пропускаются).
    """
    order: list[EntityId] = []
    visited: set[EntityId] = set()
    stack: list[tuple[EntityId, bool]] = [(entity_id, False)]
    while stack:
        node, expanded = stack.pop()
        if expanded:
            order.append(node)
            continue
        if node in visited:
            continue
        visited.add(node)
        stack.append((node, True))
        for link in reversed(await index.references_to(node)):
            if link.entity_id not in visited:
                stack.append((link.entity_id, False))
    return tuple(order)


async def collect_dangling(
    engine: IStorageEngine,
    entity_ids: Sequence[EntityId],
) -> tuple[DanglingLinks, ...]:
    """Какие из указанных объектов оставили живые ссылки (отчёт sync).

    Бэкенд без обратного индекса отдаёт пустой кортеж: проверить нечем, и
    врать «всё чисто» нельзя — поэтому отчёт просто отсутствует.
    """
    index = _index(engine)
    if index is None:
        return ()
    found: list[DanglingLinks] = []
    for target in entity_ids:
        links = await _live_links(index, target)
        if links:
            found.append(DanglingLinks(target=target, links=links))
    return tuple(found)


def _index(engine: IStorageEngine) -> IReferenceIndex | None:
    """Обратный индекс бэкенда, если он объявил возможность (ADR-0021)."""
    if not isinstance(engine, IReferenceIndex):
        return None
    if Capability.TRAVERSE_REFERENCES not in engine.capabilities():
        return None
    return engine


async def _live_links(index: IReferenceIndex, entity_id: EntityId) -> tuple[ReferenceLink, ...]:
    """Живые входящие ссылки без само-ссылок.

    Само-ссылка висячей не станет: она исчезнет вместе с объектом.
    """
    links = await index.references_to(entity_id)
    return tuple(link for link in links if link.entity_id != entity_id)


def _single_axis(links: Sequence[ReferenceLink]) -> str | None:
    axes = {link.axis for link in links}
    return next(iter(axes)) if len(axes) == 1 else None


def _reference_detail(links: Sequence[ReferenceLink]) -> str:
    """«на объект ссылаются 3 объекта: tags=2, related=1»."""
    by_axis: dict[str, int] = {}
    for link in links:
        by_axis[link.axis] = by_axis.get(link.axis, 0) + 1
    sources = len({link.entity_id for link in links})
    layout = ", ".join(f"{axis}={count}" for axis, count in sorted(by_axis.items()))
    word = _plural(sources, "объект", "объекта", "объектов")
    return f"на объект ссылаются {sources} {word}: {layout}"


def _plural(count: int, one: str, few: str, many: str) -> str:
    """Русское склонение по числу: 1 объект, 2 объекта, 5 объектов."""
    if count % 10 == 1 and count % 100 != 11:
        return one
    if 2 <= count % 10 <= 4 and not 12 <= count % 100 <= 14:
        return few
    return many


__all__ = ["DanglingLinks", "cascade_order", "collect_dangling", "tombstone_entity"]
