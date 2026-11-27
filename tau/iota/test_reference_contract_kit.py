"""Контракт обратных ссылок (ADR-0021): набор на эталонном бэкенде."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from nu.psi.contracts.delta import DeltaResolver, IStorageEngine
from nu.psi.contracts.iota import run_reference_index_contract


async def test_memory_backend_passes_reference_contract() -> None:
    resolver = DeltaResolver()
    await run_reference_index_contract(resolver.make_memory_storage)


async def test_backend_without_port_is_rejected() -> None:
    """Набор обязан ловить «объявил возможность, а порт не реализовал»."""
    without_port = MagicMock(spec=IStorageEngine)
    with pytest.raises(AssertionError, match="IReferenceIndex"):
        await run_reference_index_contract(lambda schema: without_port)
