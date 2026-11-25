"""Тесты сноса template-обвязки (``eta/strip_template.py``)."""

from __future__ import annotations

from pathlib import Path

from eta.strip_template import main, strip_marker

PYPROJECT = """\
[tool.pytest.ini_options]
markers = [
    "unit: быстрый тест",
    "template: тесты шаблона",
]
"""


def project(tmp_path: Path) -> Path:
    """Временный проект с template-обвязкой."""
    tests = tmp_path / "tau" / "template"
    tests.mkdir(parents=True)
    (tests / "__init__.py").write_text('"""Tests."""\n', encoding="utf-8")
    (tests / "test_layout.py").write_text('"""Layout."""\n', encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    return tmp_path


def test_dry_run_changes_nothing(tmp_path: Path) -> None:
    root = project(tmp_path)
    assert main(["--root", str(root), "--dry-run"]) == 0
    assert (root / "tau" / "template").is_dir()
    assert "template: тесты шаблона" in (root / "pyproject.toml").read_text(encoding="utf-8")


def test_strip_removes_directory_and_marker(tmp_path: Path) -> None:
    root = project(tmp_path)
    assert main(["--root", str(root)]) == 0

    assert not (root / "tau" / "template").exists()
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "template:" not in text
    assert "unit: быстрый тест" in text


def test_strip_is_idempotent(tmp_path: Path) -> None:
    root = project(tmp_path)
    assert main(["--root", str(root)]) == 0
    assert main(["--root", str(root)]) == 0


def test_strip_without_marker_leaves_file(tmp_path: Path) -> None:
    root = project(tmp_path)
    pyproject = root / "pyproject.toml"
    pyproject.write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    assert main(["--root", str(root)]) == 0
    assert pyproject.read_text(encoding="utf-8") == "[tool.pytest.ini_options]\n"


def test_strip_marker_returns_false_when_absent(tmp_path: Path) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    assert strip_marker(pyproject) is False
