"""Общие фикстуры тестов и авто-маркировка уровня.

Раскладка ``tau/`` — по модулям (ADR-0008). Уровень теста выражается
маркером, а не каталогом: каталог ``tau/template`` даёт маркер
``template``, ``tau/contract`` — ``contract``, ``tau/e2e`` — ``e2e``,
всё остальное по умолчанию ``unit``. Файл может выставить уровень сам
(``pytestmark = pytest.mark.integration``) — авто-маркировка его не тронет.
"""

from __future__ import annotations

from pathlib import Path

import pytest

TAU_ROOT = Path(__file__).resolve().parent

#: Каталог tau/ -> маркер уровня.
DIRECTORY_LEVELS: dict[str, str] = {
    "template": "template",
    "contract": "contract",
    "e2e": "e2e",
}

#: Уровень по умолчанию, если файл не выставил свой.
DEFAULT_LEVEL = "unit"

#: Все легальные уровни.
LEVELS: tuple[str, ...] = ("unit", "integration", "contract", "e2e", "template")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Проставить маркер уровня, если файл не сделал этого сам."""
    for item in items:
        if any(item.get_closest_marker(level) for level in LEVELS):
            continue
        try:
            top = Path(str(item.path)).relative_to(TAU_ROOT).parts[0]
        except (ValueError, IndexError):
            continue
        level = DIRECTORY_LEVELS.get(top, DEFAULT_LEVEL)
        item.add_marker(getattr(pytest.mark, level))
