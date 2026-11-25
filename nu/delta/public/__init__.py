"""Публичный API модуля delta: порт хранилища и эталонная реализация."""

from nu.delta.public.errors import StorageQueryError as StorageQueryError
from nu.delta.public.interfaces import IEntitySource as IEntitySource
from nu.delta.public.interfaces import IStorageEngine as IStorageEngine
from nu.delta.public.resolver import DeltaResolver as DeltaResolver

__all__ = ["DeltaResolver", "IEntitySource", "IStorageEngine", "StorageQueryError"]
