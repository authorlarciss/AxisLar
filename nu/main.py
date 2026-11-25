"""Точка входа ядра: собрать `Core` и показать состояние."""

from __future__ import annotations

import asyncio

from nu.psi.bootstrap import build_core
from nu.psi.contracts.mu import CONTRACT_VERSION, __version__


async def summarize() -> None:
    """Показать версию, контракт и текущее состояние ядра."""
    core = build_core()
    schema = await core.schema()
    print(f"AxisLar {__version__} (contract {CONTRACT_VERSION})")
    print(f"axes: {len(schema.axes)}, scalars: {len(schema.scalars)}")
    print(f"objects: {await core.count()}")


def main() -> None:
    """Запуск ядра."""
    asyncio.run(summarize())


if __name__ == "__main__":
    main()
