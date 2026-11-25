"""Политика идентичности объектов источника (ADR-0016).

`id = UUIDv5(source_id, key)` — детерминированный: повторный импорт не
создаёт дублей, а переименование проекта не меняет `id`, пока не меняется
`source_id`. Адаптеры обязаны пользоваться этой функцией, а не изобретать
свою схему — иначе `plan_sync` не сможет сопоставлять объекты.
"""

from __future__ import annotations

from uuid import UUID, uuid5

from nu.psi.contracts.alpha import EntityId

#: Пространство имён AxisLar для детерминированных идентификаторов.
ENTITY_ID_NAMESPACE = UUID("2f8f7c1e-4a11-4a4b-9a2e-6d3f1c7b5e90")


def entity_id_for(source_id: str, key: str) -> EntityId:
    """Детерминированный `id` объекта источника."""
    if not source_id:
        raise ValueError("source_id must be non-empty")
    if not key:
        raise ValueError("key must be non-empty")
    return EntityId(str(uuid5(ENTITY_ID_NAMESPACE, f"{source_id}\x00{key}")))


__all__ = ["ENTITY_ID_NAMESPACE", "entity_id_for"]
