"""Общие фикстуры контрактных тестов бэкендов.

Новый бэкенд подключается одной строкой в `BACKENDS`; он обязан пройти
все тесты пакета без правок в них (ADR-0013).
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from nu.psi.contracts.alpha import StorageSchema
from nu.psi.contracts.beta import IStorageEngine
from nu.psi.contracts.delta import DeltaResolver

#: Фабрики бэкендов: имя -> (схема) -> движок.
BACKENDS: dict[str, Callable[[StorageSchema], IStorageEngine]] = {
    "memory": lambda schema: DeltaResolver().make_memory_storage(schema=schema),
}


@pytest.fixture(params=sorted(BACKENDS), ids=sorted(BACKENDS))
def backend(request: pytest.FixtureRequest) -> Callable[[StorageSchema], IStorageEngine]:
    """Фабрика бэкенда, параметризованная по всем реализациям."""
    return BACKENDS[str(request.param)]
