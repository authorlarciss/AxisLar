"""Сборка: bootstrap поднимает движок и валидатор, а не заглушки."""

from __future__ import annotations

from nu.psi.bootstrap import build_application
from nu.psi.contracts.alpha import AxisDefinition, AxisKind, Filter, Operator, Query, StorageSchema
from nu.psi.contracts.beta import BetaResolver, IStorageEngine, StorageQueryError
from nu.psi.contracts.delta import DeltaResolver


def test_bootstrap_registers_storage_engine() -> None:
    app = build_application()
    storage: IStorageEngine = app.context.resolve("storage")
    assert isinstance(storage, IStorageEngine)


async def test_bootstrap_storage_is_usable() -> None:
    app = build_application()
    storage: IStorageEngine = app.context.resolve("storage")
    assert await storage.count() == 0
    assert (await storage.get_schema()) == StorageSchema()


async def test_bootstrap_engine_uses_query_resolver() -> None:
    """Движок из bootstrap валидирует запросы (не падает «как получится»)."""
    app = build_application()
    storage: IStorageEngine = app.context.resolve("storage")
    await storage.add_axis(AxisDefinition(name="theme", kind=AxisKind.CATEGORICAL))

    query = Query.model_validate({"any": [{"axis": "theme", "op": "exists"}]})
    try:
        await storage.query(query)
    except StorageQueryError as error:
        assert error.errors
    else:  # pragma: no cover - защита от тихой деградации
        raise AssertionError("query with any/not must be rejected")


async def test_bootstrap_accepts_custom_engine() -> None:
    custom = DeltaResolver().make_memory_storage(
        schema=StorageSchema(axes=(AxisDefinition(name="year", kind=AxisKind.MEASURABLE),)),
        resolver=BetaResolver().make_query_resolver(),
    )
    app = build_application(engine=custom)
    assert app.context.resolve("storage") is custom

    query = Query(all=(Filter(axis="year", op=Operator.GTE, values=(2020,)),))
    assert (await custom.query(query)).ids == ()
