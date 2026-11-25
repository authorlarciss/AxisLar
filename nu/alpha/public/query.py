"""Запросы: AST-дерево и результат (ADR-0012, DOMAIN §4, §6)."""

from __future__ import annotations

from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from nu.alpha.public.ids import EntityId


class Operator(StrEnum):
    """Операторы фильтра.

    `!=` намеренно отсутствует: на мультизначной оси он неоднозначен,
    вместо него `none_of` (ADR-0012).
    """

    CONTAINS = "contains"
    ANY_OF = "any_of"
    NONE_OF = "none_of"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"
    EQ = "eq"
    GT = "gt"
    LT = "lt"
    GTE = "gte"
    LTE = "lte"
    BETWEEN = "between"
    SCALAR_EQ = "scalar_eq"


#: Операторы без аргументов.
NULLARY_OPS: frozenset[Operator] = frozenset({Operator.EXISTS, Operator.NOT_EXISTS})

#: Операторы ровно с двумя аргументами.
BINARY_OPS: frozenset[Operator] = frozenset({Operator.BETWEEN})

#: Числовые операторы: аргументы обязаны быть числами.
NUMERIC_OPS: frozenset[Operator] = frozenset(
    {
        Operator.EQ,
        Operator.GT,
        Operator.LT,
        Operator.GTE,
        Operator.LTE,
        Operator.BETWEEN,
    }
)


class Filter(BaseModel):
    """Одно условие по оси (или скаляру для `scalar_eq`)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    axis: str = Field(min_length=1)
    op: Operator
    values: tuple[str | float, ...] = ()

    @model_validator(mode="after")
    def _check_arity_and_types(self) -> Self:
        count = len(self.values)
        if self.op in NULLARY_OPS and count:
            raise ValueError(f"operator {self.op.value!r} takes no values")
        if self.op in BINARY_OPS and count != 2:
            raise ValueError(f"operator {self.op.value!r} takes exactly 2 values")
        if self.op not in NULLARY_OPS and self.op not in BINARY_OPS and count < 1:
            raise ValueError(f"operator {self.op.value!r} requires at least 1 value")
        if self.op in NUMERIC_OPS and not all(
            isinstance(value, int | float) and not isinstance(value, bool) for value in self.values
        ):
            raise ValueError(f"operator {self.op.value!r} requires numeric values")
        return self


class Query(BaseModel):
    """Дерево фильтров. В v0 исполняется только `all` (конъюнкция).

    `any` и `not` зарезервированы в AST: запрос с ними не отвергается при
    разборе, но помечается как неподдерживаемый в v0 — движок обязан
    вернуть `UnsupportedQuery`, а не тихо проигнорировать.
    """

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    all: tuple[Filter, ...] = ()
    any: tuple[Filter, ...] = ()
    not_: tuple[Filter, ...] = Field(default=(), alias="not")
    limit: int | None = Field(default=None, ge=1)
    offset: int = Field(default=0, ge=0)

    @property
    def requires_unsupported(self) -> bool:
        """Исполнение невозможно в v0 (`any`/`not` не поддержаны)."""
        return bool(self.any or self.not_)


class QueryResult(BaseModel):
    """Выдача запроса: только идентификаторы и метаданные пагинации."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ids: tuple[EntityId, ...] = ()
    total: int = Field(ge=0)
    limit: int | None = None
    offset: int = Field(default=0, ge=0)


__all__ = [
    "BINARY_OPS",
    "Filter",
    "NULLARY_OPS",
    "NUMERIC_OPS",
    "Operator",
    "Query",
    "QueryResult",
]
