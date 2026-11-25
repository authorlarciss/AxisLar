"""Деплой-переименование пакета (eta/rename_package.py)."""

from __future__ import annotations

from pathlib import Path

import pytest

from eta.rename_package import (
    RenameError,
    copy_tree,
    leftover_imports,
    main,
    rename_package,
    rewrite_text,
    validate_target,
)


def project(root: Path) -> Path:
    """Минимальный проект с пакетом `nu`."""
    module = root / "nu" / "alpha" / "mod.py"
    module.parent.mkdir(parents=True)
    module.write_text("from nu.alpha.mod import X\n", encoding="utf-8")
    (root / "nu" / "__init__.py").write_text('"""Pkg."""\n', encoding="utf-8")
    (root / "tau").mkdir()
    (root / "tau" / "test_x.py").write_text("import nu\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[project]\nname = "demo"\n\n[tool.setuptools.packages.find]\ninclude = ["nu*"]\n',
        encoding="utf-8",
    )
    (root / "Makefile").write_text("lint:\n\truff check nu tau\n", encoding="utf-8")
    return root


def test_rewrite_keeps_foreign_words() -> None:
    assert rewrite_text("import nu\nmenu = 'nuance'", "core") == "import core\nmenu = 'nuance'"
    assert rewrite_text("ruff check nu tau", "core") == "ruff check core tau"
    assert rewrite_text("-m nu.main", "core") == "-m core.main"


def test_validate_target_rejects_bad_names() -> None:
    for bad in ("nu", "1core", "core-x", "_core"):
        with pytest.raises(RenameError):
            validate_target(bad)


def test_rename_updates_tree(tmp_path: Path) -> None:
    root = project(tmp_path)
    changed = rename_package(root, "demo_core")

    assert (root / "demo_core" / "alpha" / "mod.py").is_file()
    assert not (root / "nu").exists()
    assert (root / "demo_core" / "alpha" / "mod.py").read_text(encoding="utf-8") == (
        "from demo_core.alpha.mod import X\n"
    )
    assert "import demo_core" in (root / "tau" / "test_x.py").read_text(encoding="utf-8")
    assert 'include = ["demo_core*"]' in (root / "pyproject.toml").read_text(encoding="utf-8")
    assert "check demo_core" in (root / "Makefile").read_text(encoding="utf-8")
    assert changed
    assert leftover_imports(root) == []


def test_dry_run_changes_nothing(tmp_path: Path) -> None:
    root = project(tmp_path)
    rename_package(root, "demo_core", dry_run=True)
    assert (root / "nu" / "alpha" / "mod.py").is_file()
    assert not (root / "demo_core").exists()


def test_copy_tree_skips_service_dirs(tmp_path: Path) -> None:
    root = project(tmp_path)
    (root / ".venv").mkdir()
    (root / ".venv" / "marker").write_text("x", encoding="utf-8")
    target = tmp_path / "deploy"
    copy_tree(root, target)

    assert (target / "nu" / "alpha" / "mod.py").is_file()
    assert not (target / ".venv").exists()


def test_main_reports_conflict(tmp_path: Path) -> None:
    root = project(tmp_path)
    (root / "demo_core").mkdir()
    assert main(["--root", str(root), "--to", "demo_core"]) == 2


def test_main_dry_run(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    root = project(tmp_path)
    assert main(["--root", str(root), "--to", "demo_core", "--dry-run"]) == 0
    assert "would rename" in capsys.readouterr().out
