"""Публичный фасад: beta-возможности обязаны быть видны снаружи (ядро).

Продукт и плагины импортируют только `nu.contracts`, поэтому новая операция,
не попавшая в фасад, для них не существует. Тест ловит именно этот промах:
набор имён в `__all__` и наличие атрибута.
"""

from __future__ import annotations

from nu import contracts


def test_deletion_api_is_exported() -> None:
    """ADR-0025: политика удаления доступна потребителям через фасад."""
    for name in ("tombstone_entity", "cascade_order", "collect_dangling", "DanglingLinks"):
        assert hasattr(contracts, name), name


def test_all_names_exist() -> None:
    missing = [name for name in contracts.__all__ if not hasattr(contracts, name)]
    assert missing == []


def test_error_codes_are_exported() -> None:
    """Коды ошибок — часть контракта: клиенты сравнивают значения."""
    assert contracts.ErrorCode.REFERENCE_IN_USE.value == "reference_in_use"
    assert contracts.ErrorCode.UNSUPPORTED_CAPABILITY.value == "unsupported_capability"
