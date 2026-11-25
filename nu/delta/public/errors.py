"""Ошибки публичного API модуля delta."""

from __future__ import annotations


class SnapshotError(RuntimeError):
    """Файл состояния повреждён или несовместим по версии формата."""


__all__ = ["SnapshotError"]
