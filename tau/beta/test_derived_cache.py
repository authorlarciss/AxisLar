"""Content-addressed переиспользование производных фактов (ADR-0017)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from nu.beta.public.sync import SyncPolicy, inherit_derived, plan_sync
from nu.psi.contracts.alpha import (
    CategoricalValue,
    Entity,
    EntityId,
    FacetOwner,
    Origin,
    Provenance,
)

STAMP = datetime(2025, 11, 25, tzinfo=UTC)


def provenance(version: str = "1", at: datetime = STAMP) -> Provenance:
    return Provenance(plugin="cluster", version=version, at=at)


def entity(
    entity_id: str,
    *,
    source_id: str = "src-1",
    key: str = "a.mp4",
    content_hash: str | None = "h1",
    facets: dict[str, str] | None = None,
    owners: dict[str, FacetOwner] | None = None,
    derived_by: dict[str, Provenance] | None = None,
    deleted_at: datetime | None = None,
) -> Entity:
    return Entity(
        id=EntityId(entity_id),
        kind="video",
        facets={axis: (CategoricalValue(value=value),) for axis, value in (facets or {}).items()},
        owners=owners or {},
        derived_by=derived_by or {},
        origin=Origin(
            source_id=source_id,
            key=key,
            content_hash=content_hash,
            hash_algo="partial" if content_hash else None,
        ),
        deleted_at=deleted_at,
    )


def donor(axis_value: str = "c-1", *, version: str = "1", at: datetime = STAMP) -> Entity:
    prov = provenance(version=version, at=at)
    return entity(
        "donor",
        source_id="src-original",
        key="copy.mp4",
        facets={"cluster": axis_value},
        owners={"cluster": FacetOwner.ANALYSIS},
        derived_by={"cluster": prov},
    )


def target(**kwargs: object) -> Entity:
    return entity("target", source_id="src-copy", key="copy.mp4", **kwargs)  # type: ignore[arg-type]


# ------------------------------------------------------------ наследование


def test_analysis_facet_is_inherited_by_content_hash() -> None:
    inherited = inherit_derived(target(content_hash="h1"), [donor()])

    assert "cluster" in inherited.facets
    assert inherited.owners["cluster"] is FacetOwner.ANALYSIS
    assert inherited.derived_by["cluster"] == provenance()


def test_different_content_is_not_inherited() -> None:
    inherited = inherit_derived(target(content_hash="h2"), [donor()])
    assert "cluster" not in inherited.facets


def test_missing_hash_means_no_inheritance() -> None:
    inherited = inherit_derived(target(content_hash=None), [donor()])
    assert "cluster" not in inherited.facets


def test_tombstoned_donor_is_ignored() -> None:
    dead = donor().model_copy(update={"deleted_at": STAMP})
    assert "cluster" not in inherit_derived(target(), [dead]).facets


def test_user_and_source_facets_are_not_inherited() -> None:
    user_donor = entity(
        "user-donor",
        source_id="src-original",
        facets={"note": "руками"},
        owners={"note": FacetOwner.USER},
    )
    source_donor = entity(
        "src-donor",
        source_id="src-original",
        facets={"theme": "noir"},
        owners={"theme": FacetOwner.SOURCE},
    )
    inherited = inherit_derived(target(), [user_donor, source_donor])
    assert "note" not in inherited.facets
    assert "theme" not in inherited.facets


def test_existing_facet_wins_over_inherited() -> None:
    own = entity(
        "target",
        source_id="src-copy",
        facets={"cluster": "own"},
        owners={"cluster": FacetOwner.ANALYSIS},
        derived_by={"cluster": provenance(version="2")},
    )
    inherited = inherit_derived(own, [donor("c-1")])
    assert inherited.facets["cluster"][0].value == "own"  # type: ignore[union-attr]


def test_freshest_donor_wins() -> None:
    older = donor("old", at=STAMP - timedelta(days=1))
    newer = donor("new", at=STAMP)
    inherited = inherit_derived(target(), [older, newer])
    assert inherited.facets["cluster"][0].value == "new"  # type: ignore[union-attr]


def test_ambiguous_donors_are_skipped() -> None:
    first = donor("a", at=STAMP)
    second = donor("b", at=STAMP)
    inherited = inherit_derived(target(), [first, second])
    assert "cluster" not in inherited.facets, "при равенстве времени не угадываем"


def test_same_value_from_two_donors_is_not_ambiguous() -> None:
    inherited = inherit_derived(target(), [donor("same", at=STAMP), donor("same", at=STAMP)])
    assert inherited.facets["cluster"][0].value == "same"  # type: ignore[union-attr]


# ------------------------------------------------------------ в плане


def test_plan_create_carries_inherited_facets() -> None:
    existing = [donor()]
    scanned = [target(content_hash="h1")]
    plan = plan_sync(scanned, existing, SyncPolicy(source_id="src-copy"), now=STAMP)

    assert [action.kind.value for action in plan.actions] == ["create"]
    created = plan.actions[0].entity
    assert created.owners["cluster"] is FacetOwner.ANALYSIS
    assert created.derived_by["cluster"] == provenance()


def test_plan_update_after_content_change_inherits_new_analysis() -> None:
    stored = entity(
        "target",
        source_id="src-copy",
        key="copy.mp4",
        content_hash="h-old",
        facets={"theme": "old"},
        owners={"theme": FacetOwner.SOURCE},
    )
    donor_new = donor("fresh").model_copy(
        update={
            "origin": Origin(
                source_id="src-other", key="x.mp4", content_hash="h-new", hash_algo="partial"
            )
        }
    )
    scanned = entity(
        "target",
        source_id="src-copy",
        key="copy.mp4",
        content_hash="h-new",
        facets={"theme": "new"},
        owners={"theme": FacetOwner.SOURCE},
    )

    plan = plan_sync([scanned], [stored, donor_new], SyncPolicy(source_id="src-copy"), now=STAMP)
    assert [action.kind.value for action in plan.actions] == ["update"]
    updated = plan.actions[0].entity
    assert "cluster" in updated.facets
    assert updated.owners["cluster"] is FacetOwner.ANALYSIS
