"""Базовая реализация IApplication."""

from nu.psi.context import Context
from nu.psi.contracts.mu import __version__ as __version__
from nu.psi.contracts.sigma import get_logger
from nu.psi.interfaces import IApplication

logger = get_logger(__name__)


class Application(IApplication):
    """Базовое приложение с DI-контекстом.

    В шаблоне run() — заглушка. В проекте — наследование и переопределение:

        from nu.psi.application import Application
        from nu.psi.bootstrap import build_application

        class MyApp(Application):
            async def run(self) -> None:
                beta = self.context.resolve("beta_resolver")
                validator = beta.make_query_resolver()
                errors = await validator.check(query, schema, capabilities)
                if not errors:
                    result = await engine.query(query)

        app = MyApp(build_application().context)
        asyncio.run(app.run())

    Такой подход гарантирует, что:
    - резолвер получен из контекста (не создан напрямую);
    - реализация скрыта за интерфейсом (IQueryResolver, IStorageEngine);
    - движок и валидатор собираются в psi, а не в клиенте.
    """

    def __init__(self, context: Context) -> None:
        self.context = context

    async def run(self) -> None:
        """Запуск проекта. В шаблоне — заглушка."""
        logger.info("Application starting, version=%s", __version__)
        print(f"AxisLar v{__version__} — ядро готово к сборке бэкенда.")
        logger.info("Application finished")


__all__ = ["Application"]
