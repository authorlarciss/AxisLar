"""Доменные ошибки как значения.

Ошибка — не исключение на границе API, а значение: клиент обязан
различать «нет данных» и «запрос невалиден» (DOMAIN §7).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from nu.alpha.public.ids import EntityId


class ErrorCode(StrEnum):
    """Код доменной ошибки."""

    UNKNOWN_AXIS = "unknown_axis"
    TYPE_MISMATCH = "type_mismatch"
    CARDINALITY_VIOLATION = "cardinality_violation"
    DANGLING_REFERENCE = "dangling_reference"
    UNKNOWN_CATEGORY = "unknown_category"
    UNKNOWN_SCALAR = "unknown_scalar"
    UNSUPPORTED_QUERY = "unsupported_query"
    DUPLICATE_AXIS = "duplicate_axis"
    DUPLICATE_SCALAR = "duplicate_scalar"
    UNSUPPORTED_ARTIFACT = "unsupported_artifact"
    DANGLING_ARTIFACT = "dangling_artifact"
    ARTIFACT_MISMATCH = "artifact_mismatch"
    ARTIFACT_IN_USE = "artifact_in_use"
    CONFLICT = "conflict"


@dataclass(frozen=True, slots=True)
class DomainError:
    """Одна доменная ошибка: код, пояснение и контекст."""

    code: ErrorCode
    detail: str
    axis: str | None = None
    scalar: str | None = None
    entity_id: EntityId | None = None

    def __str__(self) -> str:
        context = ", ".join(
            f"{name}={value}"
            for name, value in (
                ("axis", self.axis),
                ("scalar", self.scalar),
                ("entity", self.entity_id),
            )
            if value is not None
        )
        suffix = f" ({context})" if context else ""
        return f"{self.code}: {self.detail}{suffix}"


__all__ = ["DomainError", "ErrorCode"]
