"""DTO артефактов: адрес по хэшу, ссылка из объекта (DOMAIN §3.1, ADR-0019)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from nu.alpha.public import (
    Artifact,
    ArtifactRef,
    Entity,
    EntityId,
    Provenance,
    content_hash_of,
    make_artifact,
)


def test_make_artifact_addresses_content() -> None:
    artifact = make_artifact(b"preview-bytes", "image/png")
    assert artifact.content_hash == content_hash_of(b"preview-bytes")
    assert artifact.size == len(b"preview-bytes")
    assert artifact.media_type == "image/png"


def test_same_bytes_same_address() -> None:
    first = make_artifact(b"same", "image/png")
    second = make_artifact(b"same", "image/png")
    assert first.content_hash == second.content_hash


def test_hash_must_match_data() -> None:
    with pytest.raises(ValidationError):
        Artifact(content_hash="0" * 64, media_type="image/png", data=b"other")


def test_empty_media_type_rejected() -> None:
    with pytest.raises(ValidationError):
        ArtifactRef(content_hash="a" * 64, media_type="", size=1)


def test_negative_size_rejected() -> None:
    with pytest.raises(ValidationError):
        ArtifactRef(content_hash="a" * 64, media_type="image/png", size=-1)


def test_entity_keeps_artifact_reference() -> None:
    ref = ArtifactRef(content_hash="a" * 64, media_type="image/png", size=12)
    entity = Entity(id=EntityId("e-1"), kind="edit", artifacts={"preview": ref})
    assert entity.artifacts["preview"].size == 12

    restored = Entity.model_validate_json(entity.model_dump_json())
    assert restored == entity, "ссылка на артефакт переживает сериализацию"


def test_entity_rejects_empty_artifact_role() -> None:
    ref = ArtifactRef(content_hash="a" * 64, media_type="image/png", size=1)
    with pytest.raises(ValidationError):
        Entity(id=EntityId("e-1"), kind="edit", artifacts={"  ": ref})


def test_artifact_provenance_is_optional_but_checked() -> None:
    provenance = Provenance(plugin="analyzer", version="1.0", at=datetime(2025, 1, 1, tzinfo=UTC))
    ref = ArtifactRef(content_hash="a" * 64, media_type="image/png", size=1, derived_by=provenance)
    assert ref.derived_by is not None and ref.derived_by.version == "1.0"


def test_binary_artifact_survives_json_roundtrip() -> None:
    """Байты в JSON — base64: артефакт не обязан быть UTF-8."""
    import base64
    import json

    artifact = make_artifact(bytes(range(256)), "application/octet-stream")
    dumped = json.loads(artifact.model_dump_json())
    decoded = base64.urlsafe_b64decode(dumped["data"])
    assert decoded == artifact.data, "JSON несёт base64 (url-safe), а не utf8"
    assert Artifact.model_validate_json(artifact.model_dump_json()) == artifact
