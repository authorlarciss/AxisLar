"""Инварианты раскладки тестов: ``tau/`` зеркалит ``nu/`` (ADR-0008).

Ось каталогов — модуль, уровень теста — маркер. Эти тесты не дают
раскладке снова расползтись на ``tau/unit`` + ``tau/<module>``, как это
случилось в VaultLar.
"""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
NU_ROOT = ROOT / "nu"
TAU_ROOT = ROOT / "tau"

#: Каталоги tau/ без модуля-владельца: тестируют отношения между модулями
#: или обслуживают репозиторий.
SHARED_DIRS: frozenset[str] = frozenset({"contract", "e2e", "support", "template", "eta"})

#: Раскладка «по уровню» вместо «по модулю» — запрещена.
LEVEL_DIRS: frozenset[str] = frozenset({"unit", "integration"})

pytestmark = pytest.mark.template


def directories(path: Path) -> set[str]:
    """Все каталоги первого уровня, кроме служебных."""
    return {
        child.name for child in path.iterdir() if child.is_dir() and child.name != "__pycache__"
    }


def packages(path: Path) -> set[str]:
    """Каталоги первого уровня, являющиеся пакетами."""
    return {name for name in directories(path) if (path / name / "__init__.py").is_file()}


def test_no_level_based_directories() -> None:
    """``tau/unit`` и ``tau/integration`` запрещены: ось раскладки — модуль."""
    assert sorted(directories(TAU_ROOT) & LEVEL_DIRS) == []


def test_every_test_directory_has_an_owner() -> None:
    """Каждому каталогу ``tau/`` соответствует модуль ``nu/`` или SHARED_DIRS."""
    orphans = directories(TAU_ROOT) - SHARED_DIRS - packages(NU_ROOT)
    assert sorted(orphans) == []


def test_module_test_directories_are_packages() -> None:
    """Каталог тестов модуля — пакет (иначе pytest-импорты разъезжаются)."""
    non_packages = sorted((directories(TAU_ROOT) & packages(NU_ROOT)) - packages(TAU_ROOT))
    assert non_packages == []


def test_no_tests_outside_directories() -> None:
    """Тесты живут только внутри каталогов, не в корне ``tau/``."""
    assert sorted(path.name for path in TAU_ROOT.glob("test_*.py")) == []


def test_shared_directories_are_packages() -> None:
    """Общие каталоги (contract/e2e/...) тоже пакеты, если существуют."""
    non_packages = sorted(SHARED_DIRS & directories(TAU_ROOT) - packages(TAU_ROOT))
    assert non_packages == []
