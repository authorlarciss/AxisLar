"""Инварианты осей, скаляров и схемы (DOMAIN §1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nu.alpha.public import AxisDefinition, AxisKind, ScalarDefinition, StorageSchema


def test_axis_defaults() -> None:
    axis = AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL)
    assert axis.multi is False
    assert axis.strict is False
    assert axis.target is None


def test_axis_accepts_string_kind() -> None:
    """DTO обязан разбираться из JSON, где `kind` — строка."""
    parsed = AxisDefinition.model_validate({"name": "year", "kind": "measurable"})
    assert parsed.kind is AxisKind.MEASURABLE


@pytest.mark.parametrize("name", ["", "Theme", "1theme", "the me", "theme-1"])
def test_axis_name_rejected(name: str) -> None:
    with pytest.raises(ValidationError):
        AxisDefinition(name=name, kind=AxisKind.CATEGORICAL)


def test_target_only_for_reference() -> None:
    with pytest.raises(ValidationError, match="target is only allowed"):
        AxisDefinition(name="source", kind=AxisKind.CATEGORICAL, target="edit")
    assert AxisDefinition(name="source", kind=AxisKind.REFERENCE, target="edit").target == "edit"


def test_strict_only_for_categorical() -> None:
    with pytest.raises(ValidationError, match="strict is only allowed"):
        AxisDefinition(name="year", kind=AxisKind.MEASURABLE, strict=True)
    axis = AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL, strict=True, values=("noir",))
    assert axis.strict is True
    assert axis.values == ("noir",)


def test_vocabulary_rules() -> None:
    """A5: values только у categorical; strict требует непустого словаря."""
    with pytest.raises(ValidationError, match="values are only allowed"):
        AxisDefinition(name="year", kind=AxisKind.MEASURABLE, values=("2024",))
    with pytest.raises(ValidationError, match="requires a non-empty vocabulary"):
        AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL, strict=True)
    with pytest.raises(ValidationError, match="duplicate values in vocabulary"):
        AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL, values=("noir", "noir"))
    assert AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL, values=("noir",)).values == (
        "noir",
    )


def test_axis_is_frozen_and_rejects_extra() -> None:
    axis = AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL)
    with pytest.raises(ValidationError):
        axis.name = "other"
    with pytest.raises(ValidationError):
        AxisDefinition.model_validate({"name": "theme", "kind": "categorical", "unknown": True})


def test_schema_rejects_duplicates_and_clashes() -> None:
    theme = AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL)
    with pytest.raises(ValidationError, match="duplicate axis names"):
        StorageSchema(axes=(theme, theme))
    with pytest.raises(ValidationError, match="both axis and scalar"):
        StorageSchema(axes=(theme,), scalars=(ScalarDefinition(name="theme"),))


def test_schema_lookup_and_dynamic_axis() -> None:
    schema = StorageSchema(axes=(AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL),))
    assert schema.axis("theme") is not None
    assert schema.axis("year") is None

    extended = schema.with_axis(AxisDefinition(name="year", kind=AxisKind.MEASURABLE))
    assert extended.axis("year") is not None
    assert schema.axis("year") is None, "исходная схема не мутирует"
    with pytest.raises(ValueError, match="already exists"):
        extended.with_axis(AxisDefinition(name="year", kind=AxisKind.MEASURABLE))


def test_schema_round_trip() -> None:
    schema = StorageSchema(
        axes=(
            AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL, multi=True),
            AxisDefinition(name="year", kind=AxisKind.MEASURABLE),
            AxisDefinition(name="author", kind=AxisKind.REFERENCE, target="person"),
        ),
        scalars=(ScalarDefinition(name="title", searchable=True),),
    )
    restored = StorageSchema.model_validate_json(schema.model_dump_json())
    assert restored == schema
