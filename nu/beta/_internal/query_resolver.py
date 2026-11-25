"""Реализация `IQueryResolver`: валидация запросов без исполнения."""

from __future__ import annotations

from nu.beta.public.interfaces import Capability, IQueryResolver
from nu.beta.public.validation import validate_query
from nu.psi.contracts.alpha import DomainError, Query, StorageSchema


class QueryResolver(IQueryResolver):
    """Проверяет запрос против схемы и объявленных возможностей бэкенда."""

    async def check(
        self,
        query: Query,
        schema: StorageSchema,
        capabilities: frozenset[Capability],
    ) -> list[DomainError]:
        return validate_query(schema, query, capabilities)


__all__ = ["QueryResolver"]
