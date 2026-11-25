"""Точка входа проекта: CLI — тонкий клиент ядра."""

from __future__ import annotations

import sys

from nu.psi.contracts.gamma import main as cli_main


def main() -> int:
    """Запуск CLI. Возвращает код выхода."""
    return cli_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
