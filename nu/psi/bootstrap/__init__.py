"""Сборка ядра: хранилище + фасад. Никаких продуктовых решений."""

from __future__ import annotations

from nu.psi.contracts.delta import DeltaResolver, IStorageEngine
from nu.psi.core import Core


def build_core(storage: IStorageEngine | None = None) -> Core:
    """Собрать ядро.

    `storage` позволяет подставить любой бэкенд (плагин) — ядро не знает,
    какой именно. По умолчанию — эталонное in-memory хранилище (ADR-0013):
    ядро обязано работать без файлов, сети и конфигурации.
    """
    return Core(storage=storage or DeltaResolver().make_memory_storage())


__all__ = ["build_core"]
