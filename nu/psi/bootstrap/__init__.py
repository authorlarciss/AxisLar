"""Сборка приложения: создание контекста и регистрация модулей."""

from nu.psi.application import Application
from nu.psi.context import Context
from nu.psi.contracts.beta import BetaResolver, IStorageEngine
from nu.psi.contracts.delta import DeltaResolver
from nu.psi.contracts.sigma import LoggingConfig, SigmaResolver


def build_application(engine: IStorageEngine | None = None) -> Application:
    """Создать Application со всеми зарегистрированными модулями.

    `engine` позволяет подставить готовый бэкенд (тесты, миграции, CLI с
    файловым хранилищем). По умолчанию собирается in-memory движок,
    связанный с валидатором запросов (ADR-0013).
    """
    context = Context()

    # 1. Логирование — первым, до всех остальных модулей
    sigma_resolver = SigmaResolver()
    sigma_resolver.setup_logging(LoggingConfig(level="INFO", format="text"))
    context.register("sigma_resolver", sigma_resolver)

    # 2. Контракты домена: валидатор запросов и бэкенд
    beta_resolver = BetaResolver()
    context.register("beta_resolver", beta_resolver)

    delta_resolver = DeltaResolver()
    context.register("delta_resolver", delta_resolver)

    storage = engine or delta_resolver.make_memory_storage(
        resolver=beta_resolver.make_query_resolver()
    )
    context.register("storage", storage)

    return Application(context)


__all__ = ["build_application"]
