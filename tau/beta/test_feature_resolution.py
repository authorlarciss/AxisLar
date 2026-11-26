"""Разрешение фич: фильтр по клиенту, fallback-цепочки, детерминизм (ADR-0020)."""

from __future__ import annotations

from nu.psi.contracts.alpha import ClientProfile, FeatureManifest, FeatureVariant
from nu.psi.contracts.beta import FeatureResolution, fits, resolve_feature, resolve_features


def profile(*features: str, name: str = "web", variants: set[str] | None = None) -> ClientProfile:
    return ClientProfile(
        name=name,
        features=frozenset(features),
        variants=frozenset(variants or ()),
    )


def manifest(*variants: FeatureVariant, provider: str = "ui") -> FeatureManifest:
    return FeatureManifest(provider=provider, feature="entity.list", variants=variants)


def test_no_variant_for_unrequested_feature() -> None:
    result = resolve_feature("entity.list", profile(), [manifest(FeatureVariant(name="table"))])
    assert not result.resolved
    assert result.reason == "client does not request this feature"


def test_no_provider() -> None:
    result = resolve_feature("entity.list", profile("entity.list"), [])
    assert not result.resolved
    assert result.reason == "no provider declares this feature"


def test_picks_first_compatible_variant() -> None:
    item = manifest(FeatureVariant(name="table"), FeatureVariant(name="cards"))
    result = resolve_feature("entity.list", profile("entity.list"), [item])
    assert result.variant == "table" and result.provider == "ui"
    assert not result.fallback_used


def test_client_variants_filter_candidates() -> None:
    item = manifest(FeatureVariant(name="table"), FeatureVariant(name="cards"))
    result = resolve_feature("entity.list", profile("entity.list", variants={"cards"}), [item])
    assert result.variant == "cards"


def test_variant_clients_filter_candidates() -> None:
    item = manifest(
        FeatureVariant(name="table", clients=frozenset({"cli"})),
        FeatureVariant(name="cards"),
    )
    assert (
        resolve_feature("entity.list", profile("entity.list", name="cli"), [item]).variant
        == "table"
    )
    assert resolve_feature("entity.list", profile("entity.list", name="tg"), [item]).variant == (
        "cards"
    )


def test_fallback_is_used_when_primary_does_not_fit() -> None:
    item = manifest(
        FeatureVariant(name="table", clients=frozenset({"cli"}), fallback="cards"),
        FeatureVariant(name="cards"),
    )
    result = resolve_feature("entity.list", profile("entity.list", name="web"), [item])
    assert result.variant == "cards"
    assert result.fallback_used is True, "откат должен быть виден в результате"


def test_fallback_chain_is_followed() -> None:
    item = manifest(
        FeatureVariant(name="table", clients=frozenset({"cli"}), fallback="cards"),
        FeatureVariant(name="cards", clients=frozenset({"x"}), fallback="json"),
        FeatureVariant(name="json"),
    )
    result = resolve_feature("entity.list", profile("entity.list", name="web"), [item])
    assert result.variant == "json" and result.fallback_used is True


def test_fallback_cycle_is_reported_not_looped() -> None:
    item = manifest(
        FeatureVariant(name="table", clients=frozenset({"cli"}), fallback="cards"),
        FeatureVariant(name="cards", clients=frozenset({"cli"}), fallback="table"),
    )
    result = resolve_feature("entity.list", profile("entity.list", name="web"), [item])
    assert not result.resolved
    assert "fallback cycle" in (result.reason or "")


def test_unknown_fallback_target_is_not_resolved() -> None:
    item = manifest(
        FeatureVariant(name="table", clients=frozenset({"cli"}), fallback="absent"),
    )
    result = resolve_feature("entity.list", profile("entity.list", name="web"), [item])
    assert not result.resolved
    assert result.reason == "no compatible variant"


def test_providers_are_visited_deterministically() -> None:
    first = FeatureManifest(
        provider="b-ui", feature="entity.list", variants=(FeatureVariant(name="table"),)
    )
    second = FeatureManifest(
        provider="a-ui", feature="entity.list", variants=(FeatureVariant(name="cards"),)
    )
    result = resolve_feature("entity.list", profile("entity.list"), [first, second])
    assert result.provider == "a-ui", "порядок обхода — по имени провайдера"


def test_resolve_features_sorts_by_feature_name() -> None:
    items = [
        FeatureManifest(
            provider="ui", feature="artifact.view", variants=(FeatureVariant(name="inline"),)
        ),
        FeatureManifest(
            provider="ui", feature="entity.list", variants=(FeatureVariant(name="table"),)
        ),
    ]
    results = resolve_features(profile("entity.list", "artifact.view"), items)
    assert [item.feature for item in results] == ["artifact.view", "entity.list"]
    assert all(item.resolved for item in results)


def test_fits_ignores_unknown_variants_for_open_client() -> None:
    open_client = profile("entity.list")
    assert fits(open_client, FeatureVariant(name="table"))
    closed = profile("entity.list", variants={"cards"})
    assert not fits(closed, FeatureVariant(name="table"))
    assert fits(closed, FeatureVariant(name="cards"))


def test_resolution_describe_is_readable() -> None:
    resolved = FeatureResolution(feature="entity.list", variant="table", provider="ui")
    assert resolved.describe() == "entity.list: table от ui"
    failed = FeatureResolution(feature="entity.list", reason="no provider declares this feature")
    assert "не разрешена" in failed.describe()
