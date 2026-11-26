"""Проверки артефактов: возможность бэкенда и ссылки объекта (ADR-0019)."""

from __future__ import annotations

from nu.psi.contracts.alpha import (
    ArtifactRef,
    Capability,
    Entity,
    EntityId,
    ErrorCode,
    StorageSchema,
    make_artifact,
)
from nu.psi.contracts.beta import validate_artifact, validate_entity

SCHEMA = StorageSchema()

ARTIFACTS = frozenset({Capability.ARTIFACTS})
HASH = "a" * 64


def reference() -> ArtifactRef:
    return ArtifactRef(content_hash=HASH, media_type="image/png", size=3)


def test_validate_artifact_requires_capability() -> None:
    artifact = make_artifact(b"abc", "image/png")
    errors = validate_artifact(artifact)
    assert {error.code for error in errors} == {ErrorCode.UNSUPPORTED_ARTIFACT}

    assert validate_artifact(artifact, ARTIFACTS) == []


def test_entity_with_stored_artifact_is_valid() -> None:
    entity = Entity(id=EntityId("e-1"), kind="edit", artifacts={"preview": reference()})
    assert validate_entity(SCHEMA, entity, known_artifacts={HASH}, capabilities=ARTIFACTS) == []


def test_dangling_artifact_is_reported() -> None:
    entity = Entity(id=EntityId("e-1"), kind="edit", artifacts={"preview": reference()})
    errors = validate_entity(SCHEMA, entity, known_artifacts=set(), capabilities=ARTIFACTS)
    assert {error.code for error in errors} == {ErrorCode.DANGLING_ARTIFACT}
    assert errors[0].entity_id == EntityId("e-1")


def test_no_check_without_capability() -> None:
    entity = Entity(id=EntityId("e-1"), kind="edit", artifacts={"preview": reference()})
    assert validate_entity(SCHEMA, entity, known_artifacts=set()) == [], (
        "без Capability.ARTIFACTS проверять нечего: хранилище артефактов не держит"
    )


def test_no_check_without_known_artifacts() -> None:
    entity = Entity(id=EntityId("e-1"), kind="edit", artifacts={"preview": reference()})
    assert validate_entity(SCHEMA, entity, capabilities=ARTIFACTS) == [], (
        "known_artifacts=None означает «проверку не выполнять»"
    )
