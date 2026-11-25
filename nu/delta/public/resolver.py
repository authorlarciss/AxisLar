"""Публичный резолвер модуля delta: фабрики бэкендов."""

from __future__ import annotations

from pathlib import Path

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

    def load_memory_snapshot(self, path: Path) -> IStorageEngine:
        """Прочитать снимок in-memory хранилища из файла состояния."""
        from nu.delta._internal.snapshot import load

        return load(path)

    def save_memory_snapshot(self, storage: IStorageEngine, path: Path) -> None:
        """Записать снимок in-memory хранилища в файл состояния."""
        from nu.delta._internal.memory import MemoryStorage
        from nu.delta._internal.snapshot import save

        if not isinstance(storage, MemoryStorage):
            raise TypeError(f"snapshot supports MemoryStorage only, got {type(storage).__name__}")
        save(storage, path)


__all__ = ["DeltaResolver"]
