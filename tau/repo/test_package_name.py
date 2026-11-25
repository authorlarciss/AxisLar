"""Инвариант деплой-модели: в рабочем дереве пакет называется `nu`.

Переименование делает `eta/rename_package.py` в копии дерева при сборке
(`make dist`). Если переименовать пакет в самом репозитории, ломается и
деплой, и привычные импорты.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_package_directory_is_nu() -> None:
    assert (ROOT / "nu" / "__init__.py").is_file()
    assert not (ROOT / "axislar_core").exists()


def test_pyproject_ships_nu_package() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    include = data["tool"]["setuptools"]["packages"]["find"]["include"]
    assert include == ["nu*"]


def test_distribution_name_is_unique() -> None:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert data["project"]["name"] == "axislar-core"


def test_py_typed_marker_is_shipped() -> None:
    """PEP 561: без маркера mypy у потребителей не видит типы ядра."""
    assert (ROOT / "nu" / "py.typed").is_file()
