"""Оси и скаляры: измерения схемы хранилища (ADR-0009, DOMAIN §1)."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: Имя оси/скаляра: латиница в нижнем регистре, цифры, подчёркивание.
NAME_PATTERN = r"^[a-z][a-z0-9_]*$"


class AxisKind(StrEnum):
    """Тип значения оси."""

    CATEGORICAL = "categorical"
    MEASURABLE = "measurable"
    REFERENCE = "reference"


class AxisDefinition(BaseModel):
    """Именованное измерение схемы.

    Инварианты A1–A5 (DOMAIN §1): имя непустое и уникально в схеме
    (уникальность проверяет `StorageSchema`), `target` — только у
    `reference`, `strict` и `values` — только у `categorical`,
    `strict` требует непустого словаря значений.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(pattern=NAME_PATTERN)
    kind: AxisKind
    multi: bool = False
    target: str | None = None
    strict: bool = False
    values: tuple[str, ...] = ()
    description: str | None = None

    @model_validator(mode="after")
    def _check_kind_specific_fields(self) -> Self:
        if self.kind is not AxisKind.REFERENCE and self.target is not None:
            raise ValueError(f"axis {self.name!r}: target is only allowed for reference axes")
        if self.kind is not AxisKind.CATEGORICAL and self.strict:
            raise ValueError(f"axis {self.name!r}: strict is only allowed for categorical axes")
        if self.kind is not AxisKind.CATEGORICAL and self.values:
            raise ValueError(f"axis {self.name!r}: values are only allowed for categorical axes")
        if self.strict and not self.values:
            raise ValueError(f"axis {self.name!r}: strict axis requires a non-empty vocabulary")
        if len(set(self.values)) != len(self.values):
            raise ValueError(f"axis {self.name!r}: duplicate values in vocabulary")
        return self


class ScalarDefinition(BaseModel):
    """Текстовое поле объекта: для показа и поиска, не для аналитики."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(pattern=NAME_PATTERN)
    searchable: bool = False
    description: str | None = None


__all__ = ["AxisDefinition", "AxisKind", "NAME_PATTERN", "ScalarDefinition"]
