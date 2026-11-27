"""Обратные ссылки: кто указывает на объект (ADR-0021).

Ссылка в модели — не сущность, а фасет на оси с типом `reference`
(DOMAIN §1). Поэтому «входящее ребро» — это пара «ось + объект-источник»:
имя оси обязательно, иначе две разные ссылки на один объект было бы
невозможно различить.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from nu.alpha.public.ids import EntityId


class ReferenceLink(BaseModel):
    """Входящая ссылка: ось, по которой на объект сослались, и кто сослался."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    axis: str = Field(min_length=1)
    entity_id: EntityId = Field(min_length=1)


__all__ = ["ReferenceLink"]
