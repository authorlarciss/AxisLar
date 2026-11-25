"""Схема хранилища: оси и скаляры вместе (DOMAIN §1)."""

from __future__ import annotations

from typing import Self

from pydantic import BaseModel, ConfigDict, model_validator

from nu.alpha.public.axes import AxisDefinition, ScalarDefinition


class StorageSchema(BaseModel):
    """Набор измерений конкретного хранилища.

    Инварианты A1: имена осей уникальны; скаляры не пересекаются с осями
    и между собой. Порядок сохраняется как задан — он не влияет на
    семантику, но стабилен для диффов и отображения.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    axes: tuple[AxisDefinition, ...] = ()
    scalars: tuple[ScalarDefinition, ...] = ()

    @model_validator(mode="after")
    def _check_unique_names(self) -> Self:
        axis_names = [axis.name for axis in self.axes]
        duplicates = sorted({name for name in axis_names if axis_names.count(name) > 1})
        if duplicates:
            raise ValueError(f"duplicate axis names: {duplicates}")

        scalar_names = [scalar.name for scalar in self.scalars]
        duplicates = sorted({name for name in scalar_names if scalar_names.count(name) > 1})
        if duplicates:
            raise ValueError(f"duplicate scalar names: {duplicates}")

        clashes = sorted(set(axis_names) & set(scalar_names))
        if clashes:
            raise ValueError(f"names used as both axis and scalar: {clashes}")
        return self

    def axis(self, name: str) -> AxisDefinition | None:
        """Определение оси по имени или `None`."""
        return next((axis for axis in self.axes if axis.name == name), None)

    def scalar(self, name: str) -> ScalarDefinition | None:
        """Определение скаляра по имени или `None`."""
        return next((scalar for scalar in self.scalars if scalar.name == name), None)

    def with_axis(self, axis: AxisDefinition) -> StorageSchema:
        """Копия схемы с добавленной осью (динамические оси, ADR-0010)."""
        if self.axis(axis.name) is not None:
            raise ValueError(f"axis {axis.name!r} already exists")
        if self.scalar(axis.name) is not None:
            raise ValueError(f"name {axis.name!r} is already a scalar")
        return StorageSchema(axes=(*self.axes, axis), scalars=self.scalars)

    def with_scalar(self, scalar: ScalarDefinition) -> StorageSchema:
        """Копия схемы с добавленным скаляром."""
        if self.scalar(scalar.name) is not None:
            raise ValueError(f"scalar {scalar.name!r} already exists")
        if self.axis(scalar.name) is not None:
            raise ValueError(f"name {scalar.name!r} is already an axis")
        return StorageSchema(axes=self.axes, scalars=(*self.scalars, scalar))


__all__ = ["StorageSchema"]
