"""DTO фич и клиентов: имена, варианты, манифест (ADR-0020)."""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import ValidationError

from nu.alpha.public import ClientProfile, FeatureManifest, FeatureVariant


def variant(name: str = "table", **kwargs: Any) -> FeatureVariant:
    return FeatureVariant(name=name, **kwargs)


def manifest(*variants: FeatureVariant, provider: str = "ui") -> FeatureManifest:
    return FeatureManifest(provider=provider, feature="entity.list", variants=variants)


def test_client_profile_defaults() -> None:
    profile = ClientProfile(name="cli")
    assert profile.features == frozenset()
    assert profile.variants == frozenset(), "пустой variants = любой вариант"


def test_client_rejects_empty_names() -> None:
    with pytest.raises(ValidationError):
        ClientProfile.model_validate({"name": "cli", "features": [" "]})


def test_variant_self_fallback_is_rejected() -> None:
    with pytest.raises(ValidationError):
        FeatureVariant(name="table", fallback="table")


def test_variant_rejects_empty_fallback() -> None:
    with pytest.raises(ValidationError):
        FeatureVariant(name="table", fallback="   ")


def test_manifest_requires_variants() -> None:
    with pytest.raises(ValidationError):
        FeatureManifest(provider="ui", feature="entity.list", variants=())


def test_manifest_rejects_duplicate_variants() -> None:
    with pytest.raises(ValidationError):
        manifest(variant("table"), variant("table"))


def test_manifest_is_frozen() -> None:
    item = manifest(variant())
    with pytest.raises(ValidationError):
        item.provider = "other"
