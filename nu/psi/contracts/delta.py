"""Контракт delta для внешнего использования."""

from nu.delta.public import DeltaResolver as DeltaResolver
from nu.delta.public.errors import SnapshotError as SnapshotError

__all__ = ["DeltaResolver", "SnapshotError"]
