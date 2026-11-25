"""Публичный резолвер модуля beta.

Единственное место, которому разрешён доступ к `_internal/` (ADR-0002):
`psi.bootstrap` собирает фабрики отсюда, а не из реализации.
"""

from nu.beta.public.interfaces import IQueryResolver


class BetaResolver:
    """Фабрика исполнителей модуля beta.

    Расширяется по мере появления реализаций: фабрика на каждую, и тест на
    каждую фабрику (CONTRIBUTING).
    """

    def make_query_resolver(self) -> IQueryResolver:
        """Валидатор запросов против схемы и возможностей бэкенда."""
        # Lazy import: psi не должен тянуть реализации при импорте контрактов.
        from nu.beta._internal.query_resolver import QueryResolver

        return QueryResolver()


__all__ = ["BetaResolver"]
