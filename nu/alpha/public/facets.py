"""Значения фасетов: дискриминированный union по типу оси (ADR-0009)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from nu.alpha.public.ids import EntityId


class CategoricalValue(BaseModel):
    """Значение категориальной оси."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["categorical"] = "categorical"
    value: str = Field(min_length=1)


class MeasurableValue(BaseModel):
    """Значение измеримой оси. Единица опциональна: 2024 и 12.5 kg."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["measurable"] = "measurable"
    value: float
    unit: str | None = None


class ReferenceValue(BaseModel):
    """Значение ссылочной оси: идентификатор другого объекта."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Literal["reference"] = "reference"
    target: EntityId = Field(min_length=1)


#: Любое значение фасета. Тег `kind` — единственный способ различения.
FacetValue = Annotated[
    CategoricalValue | MeasurableValue | ReferenceValue,
    Field(discriminator="kind"),
]

__all__ = ["CategoricalValue", "FacetValue", "MeasurableValue", "ReferenceValue"]
