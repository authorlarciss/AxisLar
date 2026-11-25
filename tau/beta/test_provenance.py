"""Провенанс фасетов: слияние при синхронизации (ADR-0018)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from nu.beta.public.sync import SyncPolicy, merge_entity, plan_sync
from nu.psi.contracts.alpha import (
    CategoricalValue,
    Entity,
    EntityId,
    FacetOwner,
    Origin,
    Provenance,
)

STAMP = datetime(2025, 11, 25, tzinfo=UTC)


def entity(
    facets: dict[str, str],
    owners: dict[str, FacetOwner] | None = None,
    *,
    content_hash: str = "h1",
    key: str = "a.mp4",
    derived_by: dict[str, Provenance] | None = None,
) -> Entity:
    return Entity(
        id=EntityId("e-1"),
        kind="video",
        facets={axis: (CategoricalValue(value=value),) for axis, value in facets.items()},
        owners=owners or {},
        origin=Origin(source_id="src", key=key, content_hash=content_hash, hash_algo="partial"),
        derived_by=derived_by or {},
    )


def scanned(**facets: str) -> Entity:
    """Объект источника: все фасеты принадлежат источнику."""
    return entity(facets, dict.fromkeys(facets, FacetOwner.SOURCE))


def values(entity_: Entity) -> dict[str, Any]:
    return {axis: getattr(item[0], "value", None) for axis, item in entity_.facets.items()}


# ---------------------------------------------------------------- слияние


def test_user_facet_survives_merge() -> None:
    existing = entity(
        {"theme": "old", "note": "manual"},
        {"theme": FacetOwner.SOURCE, "note": FacetOwner.USER},
    )
    merged = merge_entity(scanned(theme="new"), existing)

    assert values(merged) == {"theme": "new", "note": "manual"}
    assert merged.owners["note"] is FacetOwner.USER


def test_analysis_facet_survives_with_provenance() -> None:
    provenance = Provenance(plugin="cluster", version="1", at=STAMP)
    existing = entity(
        {"theme": "old", "cluster": "c-7"},
        {"theme": FacetOwner.SOURCE, "cluster": FacetOwner.ANALYSIS},
        derived_by={"cluster": provenance},
    )
    merged = merge_entity(scanned(theme="new"), existing)

    assert values(merged)["cluster"] == "c-7"
    assert merged.derived_by == {"cluster": provenance}


def test_source_facet_dropped_when_source_stops_producing_it() -> None:
    existing = entity({"author": "gutsu"}, {"author": FacetOwner.SOURCE})
    merged = merge_entity(scanned(theme="noir"), existing)

    assert "author" not in merged.facets, "источник авторитетен для своих осей"


def test_unowned_facet_is_treated_as_user() -> None:
    existing = entity({"note": "manual"}, {})
    merged = merge_entity(scanned(theme="noir"), existing)
    assert "note" in merged.facets
    assert merged.owners["note"] is FacetOwner.USER


def test_derived_by_dropped_for_dropped_facet() -> None:
    provenance = Provenance(plugin="p", version="1", at=STAMP)
    existing = entity(
        {"cluster": "c-1"}, {"cluster": FacetOwner.SOURCE}, derived_by={"cluster": provenance}
    )
    merged = merge_entity(scanned(theme="x"), existing)
    assert merged.derived_by == {}


def test_merge_clears_tombstone() -> None:
    existing = entity({"theme": "old"}).model_copy(update={"deleted_at": STAMP})
    assert merge_entity(scanned(theme="new"), existing).deleted_at is None


# ------------------------------------------------------------- план


def test_user_facet_does_not_trigger_update() -> None:
    stored = entity(
        {"theme": "noir", "note": "manual"},
        {"theme": FacetOwner.SOURCE, "note": FacetOwner.USER},
    )
    plan = plan_sync([scanned(theme="noir")], [stored], SyncPolicy(source_id="src"), now=STAMP)
    assert plan.actions == (), "ручная правка — не изменение источника"


def test_analysis_facet_does_not_trigger_update() -> None:
    provenance = Provenance(plugin="p", version="1", at=STAMP)
    stored = entity(
        {"theme": "noir", "cluster": "c-1"},
        {"theme": FacetOwner.SOURCE, "cluster": FacetOwner.ANALYSIS},
        derived_by={"cluster": provenance},
    )
    plan = plan_sync([scanned(theme="noir")], [stored], SyncPolicy(source_id="src"), now=STAMP)
    assert plan.actions == ()


def test_update_action_keeps_user_facets() -> None:
    stored = entity(
        {"theme": "old", "note": "manual"},
        {"theme": FacetOwner.SOURCE, "note": FacetOwner.USER},
    )
    plan = plan_sync([scanned(theme="new")], [stored], SyncPolicy(source_id="src"), now=STAMP)

    assert [action.kind.value for action in plan.actions] == ["update"]
    merged = plan.actions[0].entity
    assert values(merged) == {"theme": "new", "note": "manual"}


def test_move_keeps_user_facets() -> None:
    stored = entity(
        {"theme": "noir", "note": "manual"},
        {"theme": FacetOwner.SOURCE, "note": FacetOwner.USER},
        key="old.mp4",
    )
    renamed = entity({"theme": "noir"}, dict.fromkeys(("theme",), FacetOwner.SOURCE), key="new.mp4")
    plan = plan_sync([renamed], [stored], SyncPolicy(source_id="src"), now=STAMP)

    assert [action.kind.value for action in plan.actions] == ["move"]
    moved = plan.actions[0].entity
    assert moved.id == EntityId("e-1")
    assert values(moved)["note"] == "manual"


# ------------------------------------------------------------ валидация


def test_owner_for_missing_facet_is_rejected() -> None:
    with pytest.raises(ValueError, match="owners refer to missing facets"):
        entity({"theme": "noir"}, {"note": FacetOwner.USER})


def test_facet_owner_values_are_stable() -> None:
    assert FacetOwner.SOURCE.value == "source"
    assert FacetOwner.USER.value == "user"
    assert FacetOwner.ANALYSIS.value == "analysis"
