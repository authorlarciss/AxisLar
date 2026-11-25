"""Резолвер beta: фабрика валидатора запросов (resolver pattern)."""

from __future__ import annotations

import pytest

from nu.psi.contracts.alpha import (
    AxisDefinition,
    AxisKind,
    ErrorCode,
    Filter,
    Operator,
    Query,
    StorageSchema,
)
from nu.psi.contracts.beta import BetaResolver, Capability, IQueryResolver

SCHEMA = StorageSchema(axes=(AxisDefinition(name="year", kind=AxisKind.MEASURABLE),))


def test_factory_returns_interface_not_implementation() -> None:
    resolver = BetaResolver().make_query_resolver()
    assert isinstance(resolver, IQueryResolver)


@pytest.mark.asyncio
async def test_resolver_accepts_valid_query() -> None:
    resolver = BetaResolver().make_query_resolver()
    query = Query(all=(Filter(axis="year", op=Operator.GTE, values=(2020,)),))
    assert await resolver.check(query, SCHEMA, frozenset(Capability)) == []


@pytest.mark.asyncio
async def test_resolver_reports_unknown_axis() -> None:
    resolver = BetaResolver().make_query_resolver()
    query = Query(all=(Filter(axis="colour", op=Operator.EXISTS),))
    errors = await resolver.check(query, SCHEMA, frozenset(Capability))
    assert [error.code for error in errors] == [ErrorCode.UNKNOWN_AXIS]
