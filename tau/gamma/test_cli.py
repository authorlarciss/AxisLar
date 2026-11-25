"""CLI: разбор аргументов, сквозные сценарии на файле состояния."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from nu.gamma.public.cli import main, parse_facet, parse_filter, parse_scalar
from nu.psi.contracts.alpha import AxisDefinition, AxisKind, Operator, StorageSchema


def test_parse_filter_categorical() -> None:
    condition = parse_filter("theme:contains=cyberpunk,noir")
    assert condition.axis == "theme"
    assert condition.op is Operator.CONTAINS
    assert condition.values == ("cyberpunk", "noir")


def test_parse_filter_numeric() -> None:
    condition = parse_filter("year:between=2019,2024")
    assert condition.values == (2019.0, 2024.0)


def test_parse_filter_nullary() -> None:
    assert parse_filter("year:exists").values == ()


@pytest.mark.parametrize(
    "token",
    ["theme", "theme:contains", "theme:bogus=x", "year:gte=abc", "theme:contains="],
)
def test_parse_filter_rejects_bad_input(token: str) -> None:
    with pytest.raises(ValueError):
        parse_filter(token)


def test_parse_scalar() -> None:
    assert parse_scalar("title=Alpha") == ("title", "Alpha")
    with pytest.raises(ValueError):
        parse_scalar("title")


def test_parse_facet_uses_axis_kind() -> None:
    schema = StorageSchema(
        axes=(
            AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL, multi=True),
            AxisDefinition(name="year", kind=AxisKind.MEASURABLE),
            AxisDefinition(name="author", kind=AxisKind.REFERENCE),
        )
    )
    name, values = parse_facet(schema, "year=2024")
    assert name == "year"
    assert values[0].kind == "measurable"

    _, references = parse_facet(schema, "author=person-1")
    assert references[0].kind == "reference"

    with pytest.raises(ValueError, match="unknown axis"):
        parse_facet(schema, "colour=red")
    with pytest.raises(ValueError, match="measurable"):
        parse_facet(schema, "year=soon")


def state_file(tmp_path: Path) -> list[str]:
    return ["--state", str(tmp_path / "state.json")]


def test_schema_roundtrip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    state = state_file(tmp_path)
    assert main([*state, "schema", "add-axis", "--name", "theme", "--kind", "categorical"]) == 0
    assert main([*state, "schema", "add-scalar", "--name", "title", "--searchable"]) == 0

    capsys.readouterr()
    assert main([*state, "schema", "show"]) == 0
    output = capsys.readouterr().out
    assert "axis theme: categorical" in output
    assert "scalar title searchable" in output


def test_put_and_query_roundtrip(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    state = state_file(tmp_path)
    assert (
        main([*state, "schema", "add-axis", "--name", "theme", "--kind", "categorical", "--multi"])
        == 0
    )
    assert main([*state, "schema", "add-scalar", "--name", "title"]) == 0
    assert (
        main([*state, "put", "--id", "a-1", "--kind", "edit", "--facet", "theme=noir,cyberpunk"])
        == 0
    )
    assert main([*state, "put", "--id", "b-2", "--kind", "edit", "--facet", "theme=fantasy"]) == 0

    capsys.readouterr()
    assert main([*state, "query", "--filter", "theme:contains=noir"]) == 0
    assert "a-1" in capsys.readouterr().out

    assert main([*state, "query", "--filter", "theme:none_of=noir", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ids"] == ["b-2"]
    assert payload["total"] == 1


def test_put_reports_validation_errors(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    state = state_file(tmp_path)
    assert main([*state, "put", "--id", "x", "--kind", "edit", "--facet", "colour=red"]) == 2
    assert "unknown axis" in capsys.readouterr().err


def test_show_missing_object_returns_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([*state_file(tmp_path), "show", "--id", "nope"]) == 1
    assert "not found" in capsys.readouterr().err


def test_bad_filter_returns_two(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([*state_file(tmp_path), "query", "--filter", "theme"]) == 2
    assert "bad filter" in capsys.readouterr().err


def test_incompatible_snapshot_version(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = tmp_path / "state.json"
    path.write_text(json.dumps({"version": 99, "schema": {}, "entities": []}), encoding="utf-8")
    assert main(["--state", str(path), "schema", "show"]) == 2
    assert "snapshot version" in capsys.readouterr().err
