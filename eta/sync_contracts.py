#!/usr/bin/env python3
"""Синхронизация белых списков import-linter с реальным деревом `nu/`.

Два контракта содержат механические белые списки, которые обязаны совпадать
с фактическими импортами (`unmatched_ignore_imports_alerting = "error"`):

* правило 2 (independence) — легальные импорты ``nu.psi.contracts.* -> nu.<axis>.**``;
* правило 5 (public) — легальные импорты резолверов в свой ``_internal``.

Оба списка выводятся из файловой системы, а не из замысла, поэтому они
генерируются. Источник истины — файлы; `pyproject.toml` — производная.

Правило 3 (`psi` не импортирует `_internal`) не нуждается в белом списке:
у него включён ``allow_indirect_imports``, поэтому легальная цепочка
``psi -> public.resolver -> _internal`` не является нарушением.

Использование::

    python -m eta.sync_contracts           # перезаписать блоки
    python -m eta.sync_contracts --check   # только проверить (exit 1 при расхождении)
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path
from typing import Final

#: Порядок осей — как в контрактах pyproject.toml (стабильный diff).
AXIS_MODULES: Final[tuple[str, ...]] = (
    "alpha",
    "beta",
    "gamma",
    "delta",
    "epsilon",
    "zeta",
    "iota",
    "sigma",
    "mu",
)

TAG_RULE2: Final = "rule2"
TAG_RULE5: Final = "rule5"


def begin_marker(tag: str) -> str:
    """Строка-маркер начала генерируемого блока."""
    return f"# >>> contracts:generated {tag}"


def end_marker(tag: str) -> str:
    """Строка-маркер конца генерируемого блока."""
    return f"# <<< contracts:generated {tag}"


class MarkerError(RuntimeError):
    """Маркеры генерируемого блока отсутствуют или испорчены."""


# ---------------------------------------------------------------- сканирование


def module_name(path: Path, root: Path) -> str:
    """Dotted-имя модуля по пути к файлу внутри `root`."""
    relative = path.resolve().relative_to(root.resolve()).with_suffix("")
    parts = list(relative.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _relative_base(package: str, level: int) -> str:
    """Пакет, от которого отсчитывается относительный импорт."""
    parts = package.split(".") if package else []
    if level <= 1:
        return ".".join(parts)
    return ".".join(parts[: len(parts) - (level - 1)])


def imported_modules(path: Path, root: Path) -> set[str]:
    """Полные dotted-имена модулей, импортируемых из файла `path`."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    own = module_name(path, root)
    package = own if path.name == "__init__.py" else own.rpartition(".")[0]
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = _relative_base(package, node.level) if node.level else ""
            tail = node.module or ""
            if base and tail:
                found.add(f"{base}.{tail}")
            elif base or tail:
                found.add(base or tail)
    return found


def _is_under(module: str, prefix: str) -> bool:
    """Модуль `module` лежит в пакете `prefix` (или совпадает с ним)."""
    return module == prefix or module.startswith(f"{prefix}.")


def build_rules(root: Path) -> dict[str, list[str]]:
    """Вычислить ожидаемые белые списки для правил 2 и 5."""
    nu = root / "nu"

    rule2: list[str] = []
    contracts = nu / "psi" / "contracts"
    contract_imports: set[str] = set()
    if contracts.is_dir():
        for contract_file in sorted(contracts.glob("*.py")):
            if contract_file.name == "__init__.py":
                continue
            contract_imports.update(imported_modules(contract_file, root))
    for axis in AXIS_MODULES:
        if any(_is_under(module, f"nu.{axis}") for module in contract_imports):
            rule2.append(f"nu.psi.contracts.** -> nu.{axis}.**")

    rule5: list[str] = []
    for axis in AXIS_MODULES:
        resolver = nu / axis / "public" / "resolver.py"
        if not resolver.is_file():
            continue
        internal = f"nu.{axis}._internal"
        targets = sorted(
            module for module in imported_modules(resolver, root) if _is_under(module, internal)
        )
        # Точные пути, без wildcard'ов: grimp трактует `**` как «потомки»,
        # поэтому `nu.X._internal.**` не покрывает сам пакет `nu.X._internal`.
        # Точная запись всегда матчится и не расширяет белый список.
        rule5.extend(f"nu.{axis}.public.resolver -> {target}" for target in targets)

    return {TAG_RULE2: rule2, TAG_RULE5: rule5}


# ------------------------------------------------------------ работа с текстом


def _region_bounds(lines: list[str], tag: str) -> tuple[int, int]:
    begin = begin_marker(tag).strip()
    end = end_marker(tag).strip()
    starts = [index for index, line in enumerate(lines) if line.strip() == begin]
    ends = [index for index, line in enumerate(lines) if line.strip() == end]
    if len(starts) != 1 or len(ends) != 1:
        raise MarkerError(
            f"expected exactly one pair of markers for {tag!r}, "
            f"found {len(starts)} begin / {len(ends)} end"
        )
    if starts[0] >= ends[0]:
        raise MarkerError(f"markers for {tag!r} are out of order")
    return starts[0], ends[0]


def _normalize_entry(line: str) -> str | None:
    """Привести строку TOML-массива к «голому» значению; None — пустая строка."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if stripped.endswith(","):
        stripped = stripped[:-1].rstrip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {'"', "'"}:
        stripped = stripped[1:-1]
    return stripped or None


def extract_region(text: str, tag: str) -> list[str]:
    """Текущее содержимое генерируемого блока (голые значения без кавычек)."""
    lines = text.splitlines()
    begin, end = _region_bounds(lines, tag)
    entries: list[str] = []
    for line in lines[begin + 1 : end]:
        entry = _normalize_entry(line)
        if entry is not None:
            entries.append(entry)
    return entries


def render_region(entries: list[str], tag: str, indent: str = "    ") -> list[str]:
    """Строки блока: маркеры + по строке на запись."""
    body = [f'{indent}"{entry}",' for entry in entries]
    return [f"{indent}{begin_marker(tag)}", *body, f"{indent}{end_marker(tag)}"]


def replace_region(text: str, tag: str, entries: list[str], indent: str = "    ") -> str:
    """Заменить содержимое блока `tag` на `entries`."""
    lines = text.splitlines()
    begin, end = _region_bounds(lines, tag)
    updated = [*lines[:begin], *render_region(entries, tag, indent), *lines[end + 1 :]]
    return "\n".join(updated) + "\n"


def sync_text(text: str, rules: dict[str, list[str]]) -> str:
    """Применить все правила к тексту pyproject.toml."""
    result = text
    for tag, entries in rules.items():
        result = replace_region(result, tag, entries)
    return result


def diff_regions(text: str, rules: dict[str, list[str]]) -> list[str]:
    """Человекочитаемые расхождения (пусто, если всё синхронно)."""
    problems: list[str] = []
    for tag, expected in rules.items():
        actual = extract_region(text, tag)
        missing = [entry for entry in expected if entry not in actual]
        extra = [entry for entry in actual if entry not in expected]
        if missing or extra:
            problems.append(f"{tag}: stale block")
            problems.extend(f"  + {entry}" for entry in missing)
            problems.extend(f"  - {entry}" for entry in extra)
    return problems


# ------------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    """Точка входа: перезапись или проверка блоков."""
    parser = argparse.ArgumentParser(description="Sync import-linter whitelists with nu/ tree")
    parser.add_argument("--check", action="store_true", help="only verify, do not write")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="project root (default: repository root)",
    )
    args = parser.parse_args(argv)

    pyproject = args.root / "pyproject.toml"
    if not pyproject.is_file():
        print(f"error: {pyproject} not found", file=sys.stderr)
        return 2

    rules = build_rules(args.root)
    original = pyproject.read_text(encoding="utf-8")

    if args.check:
        try:
            problems = diff_regions(original, rules)
        except MarkerError as error:
            print(f"error: {error}", file=sys.stderr)
            return 2
        if problems:
            print("import-linter whitelists are stale; run `make contracts`:")
            print("\n".join(problems))
            return 1
        print("import-linter whitelists are in sync")
        return 0

    try:
        updated = sync_text(original, rules)
    except MarkerError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2

    if updated == original:
        print("import-linter whitelists already in sync")
        return 0

    pyproject.write_text(updated, encoding="utf-8")
    total = sum(len(entries) for entries in rules.values())
    print(f"import-linter whitelists updated ({total} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
