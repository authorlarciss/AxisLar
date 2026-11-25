"""Публичный резолвер модуля delta: фабрика эталонного хранилища.

Внешние бэкенды — отдельные проекты (плагины), которые реализуют порт
`IStorageEngine` и подключаются продуктом. Здесь — только референс.
"""

from __future__ import annotations

from nu.delta.public.interfaces import IStorageEngine
from nu.psi.contracts.alpha import StorageSchema


class DeltaResolver:
    """Фабрика бэкендов модуля delta."""

    def make_memory_storage(self, schema: StorageSchema | None = None) -> IStorageEngine:
        """Эталонный in-memory бэкенд (ADR-0013)."""
        # Lazy import: psi не должен тянуть реализацию при импорте контрактов.
        from nu.delta._internal.memory import MemoryStorage

        return MemoryStorage(schema=schema)


__all__ = ["DeltaResolver"]
