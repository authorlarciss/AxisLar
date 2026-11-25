"""Тесты генератора белых списков import-linter (``eta/sync_contracts.py``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from eta.sync_contracts import (
    AXIS_MODULES,
    MarkerError,
    begin_marker,
    build_rules,
    diff_regions,
    end_marker,
    extract_region,
    imported_modules,
    main,
    module_name,
    replace_region,
    sync_text,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def write(root: Path, relative: str, body: str = "") -> Path:
    """Создать файл с содержимым внутри временного проекта."""
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def pyproject_with_markers(rule2: str = "", rule5: str = "") -> str:
    """Минимальный pyproject.toml с обеими парами маркеров."""
    return (
        "[tool.importlinter]\n"
        "ignore_imports = [\n"
        f"    {begin_marker('rule2')}\n"
        f"{rule2}"
        f"    {end_marker('rule2')}\n"
        "]\n"
        "ignore_imports_more = [\n"
        f"    {begin_marker('rule5')}\n"
        f"{rule5}"
        f"    {end_marker('rule5')}\n"
        "]\n"
    )


# ------------------------------------------------------------ разбор импортов


def test_module_name_drops_init_and_suffix(tmp_path: Path) -> None:
    path = write(tmp_path, "nu/psi/contracts/beta.py", "")
    assert module_name(path, tmp_path) == "nu.psi.contracts.beta"

    package = write(tmp_path, "nu/beta/public/__init__.py", "")
    assert module_name(package, tmp_path) == "nu.beta.public"


def test_imported_modules_absolute_relative_and_plain(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "nu/beta/public/resolver.py",
        "from nu.beta._internal.workflow import Job\n"
        "from .._internal.queue import Queue\n"
        "from .interfaces import IJob\n"
        "import nu.sigma._internal.formatters\n",
    )
    found = imported_modules(path, tmp_path)
    assert "nu.beta._internal.workflow" in found
    assert "nu.beta._internal.queue" in found
    assert "nu.beta.public.interfaces" in found
    assert "nu.sigma._internal.formatters" in found


def test_imported_modules_inside_type_checking(tmp_path: Path) -> None:
    path = write(
        tmp_path,
        "nu/beta/public/resolver.py",
        "from typing import TYPE_CHECKING\n"
        "if TYPE_CHECKING:\n"
        "    from nu.beta._internal.workflow import Job\n",
    )
    assert "nu.beta._internal.workflow" in imported_modules(path, tmp_path)


# ------------------------------------------------------------- правило 5


def test_rule5_reports_resolver_importing_internal(tmp_path: Path) -> None:
    write(tmp_path, "nu/beta/public/resolver.py", "from nu.beta._internal.workflow import Job\n")
    assert build_rules(tmp_path)["rule5"] == [
        "nu.beta.public.resolver -> nu.beta._internal.workflow"
    ]


def test_rule5_reports_package_level_import(tmp_path: Path) -> None:
    write(tmp_path, "nu/beta/public/resolver.py", "from nu.beta._internal import workflow\n")
    assert build_rules(tmp_path)["rule5"] == ["nu.beta.public.resolver -> nu.beta._internal"]


def test_rule5_deduplicates_imports(tmp_path: Path) -> None:
    write(
        tmp_path,
        "nu/beta/public/resolver.py",
        "from nu.beta._internal.workflow import Job\n"
        "from nu.beta._internal.workflow import Queue\n",
    )
    assert build_rules(tmp_path)["rule5"] == [
        "nu.beta.public.resolver -> nu.beta._internal.workflow"
    ]


def test_rule5_skips_resolver_without_internal_imports(tmp_path: Path) -> None:
    write(tmp_path, "nu/beta/public/resolver.py", "from nu.beta.public.interfaces import IJob\n")
    assert build_rules(tmp_path)["rule5"] == []


def test_rule5_skips_module_without_resolver(tmp_path: Path) -> None:
    write(tmp_path, "nu/delta/public/api.py", "from nu.delta._internal.store import Store\n")
    assert build_rules(tmp_path)["rule5"] == []


def test_rule5_ignores_foreign_internal(tmp_path: Path) -> None:
    write(tmp_path, "nu/beta/public/resolver.py", "from nu.sigma._internal.api import Api\n")
    assert build_rules(tmp_path)["rule5"] == []


# ------------------------------------------------------------- правило 2


def test_rule2_reports_contracts_imports(tmp_path: Path) -> None:
    write(
        tmp_path, "nu/psi/contracts/beta.py", "from nu.beta.public import IEventBus as IEventBus\n"
    )
    assert build_rules(tmp_path)["rule2"] == ["nu.psi.contracts.** -> nu.beta.**"]


def test_rule2_ignores_empty_stub(tmp_path: Path) -> None:
    write(tmp_path, "nu/psi/contracts/delta.py", '"""Пока пусто."""\n\n__all__ = []\n')
    assert build_rules(tmp_path)["rule2"] == []


def test_rules_follow_axis_order(tmp_path: Path) -> None:
    lower = AXIS_MODULES[1]
    higher = AXIS_MODULES[3]
    write(tmp_path, f"nu/psi/contracts/{higher}.py", f"from nu.{higher}.public import X as X\n")
    write(tmp_path, f"nu/psi/contracts/{lower}.py", f"from nu.{lower}.public import Y as Y\n")
    assert build_rules(tmp_path)["rule2"] == [
        f"nu.psi.contracts.** -> nu.{lower}.**",
        f"nu.psi.contracts.** -> nu.{higher}.**",
    ]


# ------------------------------------------------------- работа с регионами


def test_replace_region_renders_entries() -> None:
    text = pyproject_with_markers()
    updated = replace_region(text, "rule2", ["nu.psi.contracts.** -> nu.beta.**"])
    assert extract_region(updated, "rule2") == ["nu.psi.contracts.** -> nu.beta.**"]


def test_replace_region_is_idempotent() -> None:
    text = pyproject_with_markers()
    once = replace_region(text, "rule5", ["nu.beta.public.resolver -> nu.beta._internal.**"])
    twice = replace_region(once, "rule5", ["nu.beta.public.resolver -> nu.beta._internal.**"])
    assert once == twice


def test_missing_markers_raise() -> None:
    with pytest.raises(MarkerError):
        extract_region("[tool.importlinter]\n", "rule2")


def test_duplicated_markers_raise() -> None:
    text = pyproject_with_markers() + f"    {begin_marker('rule2')}\n"
    with pytest.raises(MarkerError):
        extract_region(text, "rule2")


def test_sync_text_and_diff_regions_agree(tmp_path: Path) -> None:
    write(tmp_path, "nu/beta/public/resolver.py", "from nu.beta._internal.workflow import Job\n")
    rules = build_rules(tmp_path)
    text = pyproject_with_markers()

    assert diff_regions(text, rules) != []
    synced = sync_text(text, rules)
    assert diff_regions(synced, rules) == []


def test_diff_regions_reports_extra_entries(tmp_path: Path) -> None:
    rules = build_rules(tmp_path)
    text = pyproject_with_markers(rule2='        "nu.psi.contracts.** -> nu.zeta.**",\n')
    problems = diff_regions(text, rules)
    assert any("nu.psi.contracts.** -> nu.zeta.**" in line for line in problems)


# ------------------------------------------------------------------------- CLI


def project_with(tmp_path: Path, *, resolvers: bool = True) -> Path:
    """Временный «проект»: pyproject с маркерами + минимальное дерево nu/."""
    if resolvers:
        write(
            tmp_path, "nu/beta/public/resolver.py", "from nu.beta._internal.workflow import Job\n"
        )
        write(
            tmp_path,
            "nu/psi/contracts/beta.py",
            "from nu.beta.public import IEventBus as IEventBus\n",
        )
    write(tmp_path, "pyproject.toml", pyproject_with_markers())
    return tmp_path


def test_main_writes_stale_blocks(tmp_path: Path) -> None:
    root = project_with(tmp_path)
    assert main(["--root", str(root)]) == 0

    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    assert extract_region(text, "rule2") == ["nu.psi.contracts.** -> nu.beta.**"]
    assert extract_region(text, "rule5") == [
        "nu.beta.public.resolver -> nu.beta._internal.workflow"
    ]


def test_main_check_fails_on_drift(tmp_path: Path) -> None:
    root = project_with(tmp_path)
    assert main(["--root", str(root), "--check"]) == 1
    assert main(["--root", str(root)]) == 0
    assert main(["--root", str(root), "--check"]) == 0


def test_main_reports_missing_pyproject(tmp_path: Path) -> None:
    assert main(["--root", str(tmp_path)]) == 2


def test_main_reports_broken_markers(tmp_path: Path) -> None:
    write(tmp_path, "pyproject.toml", "[tool.importlinter]\n")
    assert main(["--root", str(tmp_path)]) == 2


def test_repository_pyproject_is_in_sync() -> None:
    """`pyproject.toml` не должен расходиться с деревом `nu/`."""
    text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert diff_regions(text, build_rules(REPO_ROOT)) == []
