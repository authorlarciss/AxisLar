"""Контракт delta для внешнего использования: порт и эталон хранилища."""

from nu.delta.public import DeltaResolver as DeltaResolver
from nu.delta.public import IStorageEngine as IStorageEngine
from nu.delta.public import StorageQueryError as StorageQueryError

__all__ = ["DeltaResolver", "IStorageEngine", "StorageQueryError"]
