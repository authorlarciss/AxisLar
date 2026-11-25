#!/usr/bin/env python3
"""Удаление template-обвязки при форке BaseLar в новый проект.

Сносит то, что имеет смысл только в самом шаблоне:

* ``tau/template/`` — инварианты раскладки и scaffold-тесты;
* маркер ``template`` из ``pyproject.toml``.

Остальное (``eta/``, ``tau/eta/``, ADR 0001–0008) остаётся: это
рабочая инфраструктура, а не обвязка шаблона.

Использование::

    python -m eta.strip_template --dry-run
    python -m eta.strip_template
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

TEMPLATE_TESTS = Path("tau") / "template"
MARKER_PREFIX = "template:"


def strip_marker(pyproject: Path) -> bool:
    """Удалить строку маркера ``template`` из списка markers."""
    lines = pyproject.read_text(encoding="utf-8").splitlines(keepends=True)
    kept = [line for line in lines if MARKER_PREFIX not in line]
    if len(kept) == len(lines):
        return False
    pyproject.write_text("".join(kept), encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    """Точка входа."""
    parser = argparse.ArgumentParser(description="Remove BaseLar template-only scaffolding")
    parser.add_argument("--dry-run", action="store_true", help="show what would be removed")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="project root (default: repository root)",
    )
    args = parser.parse_args(argv)

    target = args.root / TEMPLATE_TESTS
    pyproject = args.root / "pyproject.toml"

    if args.dry_run:
        print(f"would remove directory: {target}")
        print(f"would strip marker line: {pyproject} ({MARKER_PREFIX})")
        return 0

    if target.is_dir():
        shutil.rmtree(target)
        print(f"removed {target}")
    else:
        print(f"nothing to remove: {target} not found")

    if pyproject.is_file() and strip_marker(pyproject):
        print(f"stripped {MARKER_PREFIX} marker from {pyproject}")

    print("next: update README/CONTRIBUTING references to tau/template and run `make check`")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
