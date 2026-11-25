"""CLI AxisLar: тонкий клиент над контрактами ядра.

Здесь нет доменной логики: разбор аргументов, вызов контрактов и печать.
Состояние между вызовами процесса — снимок in-memory хранилища (файл),
а не бэкенд: фильтрация по файлу не выполняется (PLAN M6).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from pathlib import Path

from nu.psi.contracts.alpha import (
    AxisDefinition,
    AxisKind,
    CategoricalValue,
    DomainError,
    Entity,
    EntityId,
    FacetValue,
    Filter,
    MeasurableValue,
    Operator,
    Query,
    QueryResult,
    ReferenceValue,
    ScalarDefinition,
    StorageSchema,
)
from nu.psi.contracts.delta import DeltaResolver, SnapshotError

DEFAULT_STATE = Path(".axislar-state.json")

#: Числовые операторы: значения разбираются как float.
NUMERIC_OPERATORS = frozenset(
    {
        Operator.EQ,
        Operator.GT,
        Operator.LT,
        Operator.GTE,
        Operator.LTE,
        Operator.BETWEEN,
    }
)

#: Операторы без значений.
NULLARY_OPERATORS = frozenset({Operator.EXISTS, Operator.NOT_EXISTS})


class CliError(ValueError):
    """Ошибка ввода пользователя: печатается без трейсбека."""


# ------------------------------------------------------------------ разбор


def parse_filter(token: str) -> Filter:
    """`axis:op=v1,v2` → Filter."""
    head, separator, raw = token.partition("=")
    axis, colon, op_name = head.partition(":")
    if not colon or not axis or not op_name:
        raise CliError(f"bad filter {token!r}, expected axis:op=values")

    try:
        op = Operator(op_name)
    except ValueError as error:
        known = ", ".join(item.value for item in Operator)
        raise CliError(f"unknown operator {op_name!r}; known: {known}") from error

    if op in NULLARY_OPERATORS:
        return Filter(axis=axis, op=op)

    if not separator:
        raise CliError(f"filter {token!r} requires values")

    raw_values = [piece for piece in raw.split(",") if piece]
    if not raw_values:
        raise CliError(f"filter {token!r} requires at least one value")

    if op in NUMERIC_OPERATORS:
        try:
            values: tuple[str | float, ...] = tuple(float(piece) for piece in raw_values)
        except ValueError as error:
            raise CliError(f"operator {op.value!r} requires numbers") from error
    else:
        values = tuple(raw_values)
    return Filter(axis=axis, op=op, values=values)


def parse_scalar(token: str) -> tuple[str, str]:
    """`title=Alpha` → (name, value)."""
    name, separator, value = token.partition("=")
    if not separator or not name:
        raise CliError(f"bad scalar {token!r}, expected name=value")
    return name, value


def parse_facet(schema: StorageSchema, token: str) -> tuple[str, tuple[FacetValue, ...]]:
    """`theme=cyberpunk,noir` → фасет с типом, взятым из схемы."""
    name, separator, raw = token.partition("=")
    if not separator or not name:
        raise CliError(f"bad facet {token!r}, expected axis=value[,value]")

    axis = schema.axis(name)
    if axis is None:
        known = ", ".join(item.name for item in schema.axes) or "<нет осей>"
        raise CliError(f"unknown axis {name!r}; declared: {known}")

    raw_values = [piece for piece in raw.split(",") if piece]
    if not raw_values:
        raise CliError(f"facet {token!r} requires at least one value")

    values: list[FacetValue] = []
    for piece in raw_values:
        if axis.kind is AxisKind.MEASURABLE:
            try:
                values.append(MeasurableValue(value=float(piece)))
            except ValueError as error:
                raise CliError(f"axis {name!r} is measurable, got {piece!r}") from error
        elif axis.kind is AxisKind.REFERENCE:
            values.append(ReferenceValue(target=EntityId(piece)))
        else:
            values.append(CategoricalValue(value=piece))
    return name, tuple(values)


def build_entity(schema: StorageSchema, args: argparse.Namespace) -> Entity:
    facets: dict[str, tuple[FacetValue, ...]] = {}
    for token in args.facet:
        name, values = parse_facet(schema, token)
        if name in facets:
            raise CliError(f"facet {name!r} is given twice")
        facets[name] = values
    scalars = dict(parse_scalar(token) for token in args.scalar)
    return Entity(id=EntityId(args.id), kind=args.kind, scalars=scalars, facets=facets)


def build_query(args: argparse.Namespace) -> Query:
    filters = tuple(parse_filter(token) for token in args.filter)
    return Query(all=filters, limit=args.limit, offset=args.offset)


# ------------------------------------------------------------------- печать


def print_errors(errors: Sequence[DomainError]) -> None:
    for error in errors:
        print(str(error), file=sys.stderr)


def render_result(result: QueryResult, as_json: bool) -> str:
    if as_json:
        return result.model_dump_json(indent=2)
    ids = "\n".join(str(entity_id) for entity_id in result.ids)
    header = f"# total={result.total} limit={result.limit} offset={result.offset}"
    return f"{header}\n{ids}".rstrip()


def render_schema(schema: StorageSchema, as_json: bool) -> str:
    if as_json:
        return schema.model_dump_json(indent=2)
    if not schema.axes and not schema.scalars:
        return "<пустая схема>"
    lines = [
        f"axis {axis.name}: {axis.kind.value}"
        f"{' multi' if axis.multi else ''}"
        f"{f' target={axis.target}' if axis.target else ''}"
        f"{f' strict={list(axis.values)}' if axis.strict else ''}"
        for axis in schema.axes
    ]
    lines += [
        f"scalar {scalar.name}{' searchable' if scalar.searchable else ''}"
        for scalar in schema.scalars
    ]
    return "\n".join(lines)


# ------------------------------------------------------------------ работа


async def run(args: argparse.Namespace) -> int:
    resolver = DeltaResolver()
    state: Path = args.state
    engine = resolver.load_memory_snapshot(state)

    if args.command == "schema-show":
        print(render_schema(await engine.get_schema(), args.json))
        return 0

    if args.command == "schema-add-axis":
        axis = AxisDefinition(
            name=args.name,
            kind=args.kind,
            multi=args.multi,
            target=args.target,
            strict=args.strict,
            values=tuple(args.value),
        )
        errors = await engine.add_axis(axis)
        if errors:
            print_errors(errors)
            return 2
        resolver.save_memory_snapshot(engine, state)
        print(f"axis {axis.name} added")
        return 0

    if args.command == "schema-add-scalar":
        scalar = ScalarDefinition(name=args.name, searchable=args.searchable)
        errors = await engine.add_scalar(scalar)
        if errors:
            print_errors(errors)
            return 2
        resolver.save_memory_snapshot(engine, state)
        print(f"scalar {scalar.name} added")
        return 0

    if args.command == "put":
        entity = build_entity(await engine.get_schema(), args)
        errors = await engine.upsert(entity)
        if errors:
            print_errors(errors)
            return 2
        resolver.save_memory_snapshot(engine, state)
        print(f"stored {entity.id}")
        return 0

    if args.command == "show":
        found = await engine.get(EntityId(args.id))
        if found is None:
            print(f"not found: {args.id}", file=sys.stderr)
            return 1
        print(found.model_dump_json(indent=2) if args.json else found.model_dump_json())
        return 0

    if args.command == "query":
        result = await engine.query(build_query(args))
        print(render_result(result, args.json))
        return 0

    raise CliError(f"unknown command {args.command!r}")  # pragma: no cover


# ------------------------------------------------------------------ парсер


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="axislar", description="AxisLar — многомерное ядро")
    parser.add_argument("--state", type=Path, default=DEFAULT_STATE, help="файл состояния")
    subparsers = parser.add_subparsers(dest="command", required=True)

    schema = subparsers.add_parser("schema", help="работа со схемой")
    schema_sub = schema.add_subparsers(dest="schema_command", required=True)
    show = schema_sub.add_parser("show", help="показать схему")
    show.add_argument("--json", action="store_true")
    show.set_defaults(command="schema-show")

    add_axis = schema_sub.add_parser("add-axis", help="добавить ось")
    add_axis.add_argument("--name", required=True)
    add_axis.add_argument("--kind", required=True, choices=[item.value for item in AxisKind])
    add_axis.add_argument("--multi", action="store_true")
    add_axis.add_argument("--target")
    add_axis.add_argument("--strict", action="store_true")
    add_axis.add_argument("--value", action="append", default=[], help="значение словаря")
    add_axis.set_defaults(command="schema-add-axis")

    add_scalar = schema_sub.add_parser("add-scalar", help="добавить скаляр")
    add_scalar.add_argument("--name", required=True)
    add_scalar.add_argument("--searchable", action="store_true")
    add_scalar.set_defaults(command="schema-add-scalar")

    put = subparsers.add_parser("put", help="записать объект")
    put.add_argument("--id", required=True)
    put.add_argument("--kind", required=True, help="вид объекта: edit, note, ...")
    put.add_argument("--scalar", action="append", default=[], help="name=value")
    put.add_argument("--facet", action="append", default=[], help="axis=v1,v2")
    put.set_defaults(command="put")

    show_entity = subparsers.add_parser("show", help="показать объект")
    show_entity.add_argument("--id", required=True)
    show_entity.add_argument("--json", action="store_true")
    show_entity.set_defaults(command="show")

    query = subparsers.add_parser("query", help="выполнить запрос")
    query.add_argument("--filter", action="append", default=[], help="axis:op=v1,v2")
    query.add_argument("--limit", type=int)
    query.add_argument("--offset", type=int, default=0)
    query.add_argument("--json", action="store_true")
    query.set_defaults(command="query")

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Точка входа CLI. Возвращает код выхода."""
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        return asyncio.run(run(args))
    except (CliError, SnapshotError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    except ValueError as error:  # pydantic/DTO отказы на уровне ввода
        print(f"error: {error}", file=sys.stderr)
        return 2


__all__ = ["build_parser", "main", "parse_facet", "parse_filter", "parse_scalar"]
