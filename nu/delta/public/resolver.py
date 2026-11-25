"""Публичный резолвер модуля delta: фабрики бэкендов."""

from __future__ import annotations

from nu.psi.contracts.alpha import StorageSchema
from nu.psi.contracts.beta import IQueryResolver, IStorageEngine


class DeltaResolver:
    """Фабрика бэкендов.

    Каждый бэкенд — отдельная фабрика с отдельным тестом (CONTRIBUTING).
    """

    def make_memory_storage(
        self,
        schema: StorageSchema | None = None,
        resolver: IQueryResolver | None = None,
    ) -> IStorageEngine:
        """Эталонный in-memory бэкенд (ADR-0013)."""
        # Lazy import: psi не должен тянуть реализации при импорте контрактов.
        from nu.delta._internal.memory import MemoryStorage

        return MemoryStorage(schema=schema, resolver=resolver)


__all__ = ["DeltaResolver"]
