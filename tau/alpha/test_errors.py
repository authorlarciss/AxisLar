"""Доменные ошибки как значения (DOMAIN §7)."""

from __future__ import annotations

from nu.alpha.public import DomainError, EntityId, ErrorCode


def test_error_str_includes_context() -> None:
    error = DomainError(
        code=ErrorCode.TYPE_MISMATCH,
        detail="expected measurable value",
        axis="year",
        entity_id=EntityId("e-1"),
    )
    assert str(error) == "type_mismatch: expected measurable value (axis=year, entity=e-1)"


def test_error_str_without_context() -> None:
    error = DomainError(code=ErrorCode.UNSUPPORTED_QUERY, detail="any is not supported in v0")
    assert str(error) == "unsupported_query: any is not supported in v0"


def test_errors_are_comparable_values() -> None:
    first = DomainError(code=ErrorCode.UNKNOWN_AXIS, detail="no such axis", axis="colour")
    second = DomainError(code=ErrorCode.UNKNOWN_AXIS, detail="no such axis", axis="colour")
    assert first == second
    assert first != DomainError(code=ErrorCode.UNKNOWN_AXIS, detail="no such axis")


def test_error_codes_are_stable_strings() -> None:
    """Коды — часть контракта: их сравнивают клиенты, менять нельзя."""
    assert ErrorCode.DANGLING_REFERENCE.value == "dangling_reference"
    assert ErrorCode.CARDINALITY_VIOLATION.value == "cardinality_violation"
