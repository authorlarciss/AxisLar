"""Артефакты в in-memory бэкенде: дедупликация, ссылки, удаление (ADR-0019)."""

from __future__ import annotations

from datetime import UTC, datetime

from nu.psi.contracts.alpha import (
    Artifact,
    ArtifactRef,
    Capability,
    Entity,
    EntityId,
    ErrorCode,
    make_artifact,
)
from nu.psi.contracts.delta import DeltaResolver, IStorageEngine

PREVIEW = make_artifact(b"preview-bytes", "image/png")


def engine() -> IStorageEngine:
    return DeltaResolver().make_memory_storage()


def ref(artifact: Artifact, role_size: int | None = None) -> ArtifactRef:
    return ArtifactRef(
        content_hash=artifact.content_hash,
        media_type=artifact.media_type,
        size=artifact.size if role_size is None else role_size,
    )


async def test_memory_declares_artifact_capability() -> None:
    assert Capability.ARTIFACTS in engine().capabilities()


async def test_put_is_idempotent_and_deduplicated() -> None:
    store = engine()
    assert await store.put_artifact(PREVIEW) == []
    assert await store.put_artifact(make_artifact(b"preview-bytes", "image/png")) == []
    assert len(await store.list_artifacts()) == 1, "одни байты — один артефакт"
    assert await store.get_artifact(PREVIEW.content_hash) == PREVIEW


async def test_same_hash_different_media_type_is_rejected() -> None:
    store = engine()
    await store.put_artifact(PREVIEW)
    other = Artifact(content_hash=PREVIEW.content_hash, media_type="image/jpeg", data=PREVIEW.data)
    errors = await store.put_artifact(other)
    assert {error.code for error in errors} == {ErrorCode.ARTIFACT_MISMATCH}


async def test_referenced_artifact_cannot_be_deleted() -> None:
    store = engine()
    await store.put_artifact(PREVIEW)
    entity = Entity(id=EntityId("e-1"), kind="edit", artifacts={"preview": ref(PREVIEW)})
    assert await store.upsert(entity) == []

    errors = await store.delete_artifact(PREVIEW.content_hash)
    assert {error.code for error in errors} == {ErrorCode.ARTIFACT_IN_USE}
    assert await store.get_artifact(PREVIEW.content_hash) is not None


async def test_tombstone_still_holds_the_reference() -> None:
    store = engine()
    await store.put_artifact(PREVIEW)
    entity = Entity(id=EntityId("e-1"), kind="edit", artifacts={"preview": ref(PREVIEW)})
    await store.upsert(entity)

    tombstone = entity.model_copy(update={"deleted_at": datetime.now(UTC)})
    assert await store.upsert(tombstone) == []

    errors = await store.delete_artifact(PREVIEW.content_hash)
    assert {error.code for error in errors} == {ErrorCode.ARTIFACT_IN_USE}, (
        "воскрешение объекта не должно оставлять его без данных"
    )


async def test_unreferenced_artifact_is_deleted() -> None:
    store = engine()
    await store.put_artifact(PREVIEW)
    assert await store.delete_artifact(PREVIEW.content_hash) == []
    assert await store.get_artifact(PREVIEW.content_hash) is None
    assert await store.list_artifacts() == ()


async def test_unknown_artifact_is_ignored_on_delete() -> None:
    store = engine()
    assert await store.delete_artifact("f" * 64) == [], "удаление несуществующего — идемпотентно"


async def test_entity_reference_must_point_to_stored_artifact() -> None:
    store = engine()
    entity = Entity(id=EntityId("e-1"), kind="edit", artifacts={"preview": ref(PREVIEW)})
    errors = await store.upsert(entity)
    assert {error.code for error in errors} == {ErrorCode.DANGLING_ARTIFACT}


async def test_list_artifacts_is_ordered_by_hash() -> None:
    store = engine()
    first = make_artifact(b"one", "text/plain")
    second = make_artifact(b"two", "text/plain")
    await store.put_artifact(second)
    await store.put_artifact(first)

    hashes = [item.content_hash for item in await store.list_artifacts()]
    assert hashes == sorted(hashes)
    assert {item.media_type for item in await store.list_artifacts()} == {"text/plain"}


async def test_entity_refs_survive_round_trip() -> None:
    store = engine()
    await store.put_artifact(PREVIEW)
    entity = Entity(id=EntityId("e-1"), kind="edit", artifacts={"preview": ref(PREVIEW)})
    await store.upsert(entity)

    fetched = await store.get(EntityId("e-1"))
    assert fetched is not None and fetched.artifacts == entity.artifacts
