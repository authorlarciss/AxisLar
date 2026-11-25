"""Объект и провенанс производных фасетов (DOMAIN §3)."""

from __future__ import annotations

from datetime import datetime
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from nu.alpha.public.facets import FacetValue
from nu.alpha.public.ids import EntityId


class Origin(BaseModel):
    """Происхождение объекта: источник, ключ внутри него и хэш содержимого.

    `key` — стабильный ключ (для файлового дерева — путь относительно корня
    источника); `source_id` не выводится из пути, иначе переименование
    папки проекта ломало бы идентичность (ADR-0016).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str = Field(min_length=1)
    key: str = Field(min_length=1)
    content_hash: str | None = None
    hash_algo: str | None = None

    @model_validator(mode="after")
    def _check_hash_pair(self) -> Self:
        if (self.content_hash is None) != (self.hash_algo is None):
            raise ValueError("content_hash and hash_algo must be set together")
        return self


class Provenance(BaseModel):
    """Кто и когда породил производный фасет.

    Нужен, чтобы отличать пользовательские значения от вычисленных и
    уметь инвалидировать последние при смене модели/версии плагина.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    plugin: str = Field(min_length=1)
    version: str = Field(min_length=1)
    at: datetime

    @model_validator(mode="after")
    def _require_timezone(self) -> Self:
        if self.at.tzinfo is None:
            raise ValueError("provenance.at must be timezone-aware")
        return self


class Entity(BaseModel):
    """Универсальная единица данных: скаляры + разреженные фасеты.

    Инварианты уровня DTO: фасет непустой список значений, провенанс
    указывает только на существующие фасеты. Проверки против схемы
    (тип оси, кардинальность, ссылки) — в `beta`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: EntityId = Field(min_length=1)
    kind: str = Field(min_length=1)
    scalars: dict[str, str] = {}
    facets: dict[str, tuple[FacetValue, ...]] = {}
    derived_by: dict[str, Provenance] = {}
    origin: Origin | None = None
    deleted_at: datetime | None = None

    @model_validator(mode="after")
    def _check_facets(self) -> Self:
        for axis, values in self.facets.items():
            if not values:
                raise ValueError(f"entity {self.id!r}: facet {axis!r} has no values")
        if self.deleted_at is not None and self.deleted_at.tzinfo is None:
            raise ValueError("deleted_at must be timezone-aware")

        unknown = sorted(set(self.derived_by) - set(self.facets))
        if unknown:
            raise ValueError(f"entity {self.id!r}: provenance refers to missing facets {unknown}")
        return self


__all__ = ["Entity", "Origin", "Provenance"]
