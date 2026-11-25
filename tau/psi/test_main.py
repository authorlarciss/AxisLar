"""Точка входа ядра печатает сводку и не падает."""

from __future__ import annotations

import pytest

from nu.main import main


def test_main_prints_kernel_summary(capsys: pytest.CaptureFixture[str]) -> None:
    main()
    out = capsys.readouterr().out
    assert "AxisLar" in out
    assert "contract" in out
    assert "objects: 0" in out
