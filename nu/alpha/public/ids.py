"""Идентификаторы объектов.

`EntityId` — строка. Политика генерации (UUIDv5 от естественного ключа)
живёт в `iota`, а не здесь: `alpha` содержит только типы.
"""

from __future__ import annotations

from typing import NewType

#: Идентификатор объекта в хранилище.
EntityId = NewType("EntityId", str)

__all__ = ["EntityId"]
