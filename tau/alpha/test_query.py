"""DTO запроса: арность операторов, зарезервированные ветви, результат (DOMAIN §4, §6)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from nu.alpha.public import EntityId, Filter, Operator, Query, QueryResult


def test_nullary_operators_take_no_values() -> None:
    assert Filter(axis="theme", op=Operator.EXISTS).values == ()
    with pytest.raises(ValidationError, match="takes no values"):
        Filter(axis="theme", op=Operator.EXISTS, values=("x",))


def test_binary_operator_requires_two_values() -> None:
    assert Filter(axis="year", op=Operator.BETWEEN, values=(2020, 2024)).values == (2020, 2024)
    with pytest.raises(ValidationError, match="takes exactly 2 values"):
        Filter(axis="year", op=Operator.BETWEEN, values=(2020,))


def test_unary_operators_require_a_value() -> None:
    with pytest.raises(ValidationError, match="requires at least 1 value"):
        Filter(axis="theme", op=Operator.CONTAINS)


def test_numeric_operators_reject_strings() -> None:
    with pytest.raises(ValidationError, match="numeric values"):
        Filter(axis="year", op=Operator.GT, values=("2020",))
    assert Filter(axis="year", op=Operator.GT, values=(2020,)).values == (2020,)


def test_not_equal_operator_does_not_exist() -> None:
    """`!=` не вводится: на мультизначной оси неоднозначен (ADR-0012)."""
    with pytest.raises(ValidationError):
        Filter.model_validate({"axis": "theme", "op": "!=", "values": ["cyberpunk"]})


def test_any_and_not_are_reserved_but_parseable() -> None:
    query = Query.model_validate({"not": [{"axis": "theme", "op": "exists"}]})
    assert query.requires_unsupported is True
    assert query.model_dump(by_alias=True)["not"]


def test_conjunction_is_supported() -> None:
    query = Query(
        all=(
            Filter(axis="theme", op=Operator.CONTAINS, values=("cyberpunk",)),
            Filter(axis="year", op=Operator.GTE, values=(2020,)),
        )
    )
    assert query.requires_unsupported is False
    assert len(query.all) == 2


def test_pagination_bounds() -> None:
    with pytest.raises(ValidationError):
        Query(limit=0)
    with pytest.raises(ValidationError):
        Query(offset=-1)
    assert Query(limit=10, offset=20).offset == 20


def test_query_result_requires_total() -> None:
    with pytest.raises(ValidationError):
        QueryResult.model_validate({"ids": ["a"]})
    result = QueryResult(ids=(EntityId("a"), EntityId("b")), total=2, limit=10, offset=0)
    assert result.total == 2
    assert QueryResult.model_validate_json(result.model_dump_json()) == result
