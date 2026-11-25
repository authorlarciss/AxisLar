#!/usr/bin/env python3
"""Деплой-переименование пакета: `nu` -> `<dist>`.

В разработке пакет всегда называется `nu` (простое `from nu import ...`).
Перед сборкой дистрибутива имя должно быть уникальным на PyPI/GitHub,
поэтому деплой прогоняет копию дерева через этот скрипт: переименовывает
каталог и переписывает импорты в коде, тестах и конфигах.

Просеивание — по смыслу: правится токен `nu` (граница слова), поэтому
`menu` или `nuance` не задеваются, а `nu.alpha`, `nu/alpha`, `"nu*"` и
`-m nu.main` — задеваются.

Использование::

    python -m eta.rename_package --to axislar_core --dry-run
    python -m eta.rename_package --to axislar_core
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

#: Имя пакета в разработке.
SOURCE_PACKAGE = "nu"

#: Расширения, в которых переписывается имя пакета.
TEXT_SUFFIXES = frozenset(
    {".py", ".pyi", ".toml", ".cfg", ".ini", ".yaml", ".yml", ".md", ".txt", ".sh", ".mk"}
)

#: Файлы без расширения, которые тоже правятся (сборка/CI).
TEXT_FILENAMES = frozenset({"Makefile", "makefile", "Dockerfile", "Justfile"})

#: Каталоги, которые не копируются и не правятся.
SKIP_DIRS = frozenset(
    {
        ".git",
        ".venv",
        ".dsh",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".import_linter_cache",
        "dist",
        "build",
        ".deploy",
    }
)

_WORD_NU = re.compile(r"(?<![\w.])nu(?![\w])")


class RenameError(RuntimeError):
    """Переименование невозможно: неверное имя или конфликт путей."""


def validate_target(target: str) -> None:
    """Имя пакета: идентификатор Python, не `nu`, не служебное."""
    if not target.isidentifier():
        raise RenameError(f"{target!r} is not a valid Python identifier")
    if target == SOURCE_PACKAGE:
        raise RenameError("target must differ from the source package name")
    if target.startswith("_"):
        raise RenameError("target must not start with an underscore")


def rewrite_text(text: str, target: str) -> str:
    """Заменить токен `nu` на `target`."""
    return _WORD_NU.sub(target, text)


def iter_files(root: Path) -> list[Path]:
    """Все текстовые файлы проекта, которые нужно править."""
    found: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.relative_to(root).parts):
            continue
        if path.suffix not in TEXT_SUFFIXES and path.name not in TEXT_FILENAMES:
            continue
        found.append(path)
    return sorted(found)


def rename_package(root: Path, target: str, *, dry_run: bool = False) -> list[Path]:
    """Переименовать пакет и переписать упоминания. Возвращает изменённые файлы."""
    validate_target(target)

    source = root / SOURCE_PACKAGE
    destination = root / target
    if not source.is_dir():
        raise RenameError(f"source package not found: {source}")
    if destination.exists():
        raise RenameError(f"target already exists: {destination}")

    if dry_run:
        return [path for path in iter_files(root) if _WORD_NU.search(_read(path))]

    source.rename(destination)

    changed: list[Path] = []
    for path in iter_files(root):
        text = _read(path)
        updated = rewrite_text(text, target)
        if updated != text:
            path.write_text(updated, encoding="utf-8")
            changed.append(path)
    return changed


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:  # бинарь с текстовым расширением — не трогаем
        return ""


def leftover_imports(root: Path) -> list[str]:
    """Строки, где ещё остались импорты старого пакета (диагностика)."""
    pattern = re.compile(rf"^\s*(from|import)\s+{SOURCE_PACKAGE}\b", re.MULTILINE)
    leftovers: list[str] = []
    for path in iter_files(root):
        if path.suffix not in {".py", ".pyi"}:
            continue
        if pattern.search(_read(path)):
            leftovers.append(str(path.relative_to(root)))
    return leftovers


def copy_tree(source: Path, destination: Path) -> None:
    """Скопировать проект для деплоя, пропустив служебные каталоги."""
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(*SKIP_DIRS),
        dirs_exist_ok=True,
    )


def main(argv: list[str] | None = None) -> int:
    """Точка входа."""
    parser = argparse.ArgumentParser(description="Rename the `nu` package for deployment")
    parser.add_argument("--to", required=True, help="target package name, e.g. axislar_core")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="project root (default: repository root)",
    )
    parser.add_argument("--dry-run", action="store_true", help="show what would change")
    parser.add_argument(
        "--from-dir",
        type=Path,
        help="copy the project into this directory first, then rename in the copy",
    )
    args = parser.parse_args(argv)

    root: Path = args.root
    if args.from_dir is not None:
        if args.dry_run:
            print(f"would copy {root} -> {args.from_dir}")
        else:
            copy_tree(root, args.from_dir)
            root = args.from_dir

    try:
        changed = rename_package(root, args.to, dry_run=args.dry_run)
    except RenameError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if args.dry_run:
        print(f"would rename {SOURCE_PACKAGE} -> {args.to} and touch {len(changed)} files")
        for path in changed[:20]:
            print(f"  {path.relative_to(root)}")
        return 0

    print(f"renamed {SOURCE_PACKAGE} -> {args.to}; touched {len(changed)} files")
    leftovers = leftover_imports(root)
    if leftovers:
        print("error: leftover imports found in:", file=sys.stderr)
        for item in leftovers:
            print(f"  {item}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
