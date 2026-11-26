"""Клиенты и фичи: язык договора «кто что умеет» (ADR-0020).

Фича — не данные модели, а точка расширения: `entity.list`, `artifact.view`,
`sync.report`. Вариант — конкретная форма фичи (`table`, `cards`, `json`).
Клиент объявляет, что он запрашивает и какие варианты умеет показать;
провайдер (плагин, UI-адаптер) объявляет, какие варианты он даёт и чем
заменять недоступный.

Здесь только DTO: сам выбор — в `beta` (`resolve_feature`), потому что это
логика с порядком и fallback-цепочками.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClientProfile(BaseModel):
    """Кто потребляет: имя клиента, его фичи и поддерживаемые варианты.

    Пустой `variants` означает «любой вариант, который даст провайдер» —
    так подключается консольный или скриптовый клиент, которому всё равно,
    как выглядит вывод.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    features: frozenset[str] = frozenset()
    variants: frozenset[str] = frozenset()

    @model_validator(mode="after")
    def _check_names(self) -> ClientProfile:
        for item in (*self.features, *self.variants):
            if not item.strip():
                raise ValueError(f"client {self.name!r}: empty feature or variant name")
        return self


class FeatureVariant(BaseModel):
    """Один вариант фичи у одного провайдера.

    `clients` — для кого вариант; пустое множество означает «для любых».
    `fallback` — имя варианта, к которому откатываться, если этот не
    подошёл клиенту (цепочка разрешается и проверяется на циклы в `beta`).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str = Field(min_length=1)
    clients: frozenset[str] = frozenset()
    fallback: str | None = None

    @model_validator(mode="after")
    def _check_fallback(self) -> FeatureVariant:
        if self.fallback is not None:
            if not self.fallback.strip():
                raise ValueError("fallback must be a non-empty variant name")
            if self.fallback == self.name:
                raise ValueError(f"variant {self.name!r}: fallback cannot point to itself")
        return self


class FeatureManifest(BaseModel):
    """Что провайдер предоставляет по одной фиче (ADR-0020)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    provider: str = Field(min_length=1)
    feature: str = Field(min_length=1)
    variants: tuple[FeatureVariant, ...]

    @model_validator(mode="after")
    def _check_variants(self) -> FeatureManifest:
        if not self.variants:
            raise ValueError(f"manifest {self.provider!r}: feature needs at least one variant")
        names = [variant.name for variant in self.variants]
        if len(set(names)) != len(names):
            raise ValueError(f"manifest {self.provider!r}: duplicate variant names {names}")
        return self


__all__ = ["ClientProfile", "FeatureManifest", "FeatureVariant"]
