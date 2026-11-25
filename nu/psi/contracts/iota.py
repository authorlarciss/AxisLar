"""Контракт iota для внешнего использования: контрактные наборы."""

from nu.iota.public import run_source_contract as run_source_contract
from nu.iota.public import run_storage_contract as run_storage_contract

__all__ = ["run_source_contract", "run_storage_contract"]
