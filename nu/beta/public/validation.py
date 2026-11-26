"""Проверки модели: объект, ось, запрос против схемы.

Чистые функции без состояния: возвращают список `DomainError`, ничего не
бросают и не пишут (DOMAIN §7). Движок обязан вызывать их перед записью и
исполнением — тогда семантика не зависит от бэкенда.

Почему это публичный API, а не `_internal`: скрывать нечего — функций
без состояния не бывает «реализации», которая могла бы измениться
независимо от контракта. Бэкенды (`delta`) вызывают их через
`psi.contracts.beta`.
"""

from __future__ import annotations

from collections.abc import Collection

from nu.psi.contracts.alpha import (
    Artifact,
    AxisDefinition,
    AxisKind,
    Capability,
    CategoricalValue,
    DomainError,
    Entity,
    EntityId,
    ErrorCode,
    Filter,
    Operator,
    Query,
    ReferenceValue,
    ScalarDefinition,
    StorageSchema,
)

#: Числовые операторы: только для измеримых осей.
NUMERIC_OPERATORS: frozenset[Operator] = frozenset(
    {
        Operator.EQ,
        Operator.GT,
        Operator.LT,
        Operator.GTE,
        Operator.LTE,
        Operator.BETWEEN,
    }
)

#: Операторы по множеству значений: категориальные и ссылочные оси.
SET_OPERATORS: frozenset[Operator] = frozenset(
    {Operator.CONTAINS, Operator.ANY_OF, Operator.NONE_OF}
)

#: Существование значения: любая ось.
EXISTENCE_OPERATORS: frozenset[Operator] = frozenset({Operator.EXISTS, Operator.NOT_EXISTS})

#: Какую возможность бэкенда требует тип оси.
KIND_CAPABILITY: dict[AxisKind, Capability] = {
    AxisKind.CATEGORICAL: Capability.QUERY_CATEGORICAL,
    AxisKind.MEASURABLE: Capability.QUERY_MEASURABLE,
    AxisKind.REFERENCE: Capability.QUERY_REFERENCE,
}


def validate_axis(schema: StorageSchema, axis: AxisDefinition) -> list[DomainError]:
    """Можно ли добавить ось в схему (A1, A4)."""
    if schema.axis(axis.name) is not None:
        return [
            DomainError(
                code=ErrorCode.DUPLICATE_AXIS,
                detail="axis already exists",
                axis=axis.name,
            )
        ]
    if schema.scalar(axis.name) is not None:
        return [
            DomainError(
                code=ErrorCode.DUPLICATE_AXIS,
                detail="name is already used by a scalar",
                axis=axis.name,
            )
        ]
    return []


def validate_scalar(schema: StorageSchema, scalar: ScalarDefinition) -> list[DomainError]:
    """Можно ли добавить скаляр в схему (уникальность имени)."""
    if schema.scalar(scalar.name) is not None:
        return [
            DomainError(
                code=ErrorCode.DUPLICATE_SCALAR,
                detail="scalar already exists",
                scalar=scalar.name,
            )
        ]
    if schema.axis(scalar.name) is not None:
        return [
            DomainError(
                code=ErrorCode.DUPLICATE_SCALAR,
                detail="name is already used by an axis",
                scalar=scalar.name,
            )
        ]
    return []


def validate_entity(
    schema: StorageSchema,
    entity: Entity,
    *,
    known_ids: Collection[EntityId] | None = None,
    known_artifacts: Collection[str] | None = None,
    capabilities: frozenset[Capability] = frozenset(),
) -> list[DomainError]:
    """Проверить объект против схемы (E2–E6, E7).

    `known_ids=None` означает «проверку ссылок не выполнять»; иначе
    ссылка на отсутствующий объект даёт `DanglingReference` — но только
    если бэкенд объявил `Capability.REFERENCE_CHECK` (иначе проверка
    невозможна, и это не ошибка объекта).

    `known_artifacts` работает так же для `Entity.artifacts`: адрес,
    которого нет в хранилище, даёт `DanglingArtifact`, если бэкенд умеет
    артефакты (`Capability.ARTIFACTS`).
    """
    errors: list[DomainError] = []

    for name in entity.scalars:
        if schema.scalar(name) is None:
            errors.append(
                DomainError(
                    code=ErrorCode.UNKNOWN_SCALAR,
                    detail="scalar is not declared in schema",
                    scalar=name,
                    entity_id=entity.id,
                )
            )

    check_references = known_ids is not None and (Capability.REFERENCE_CHECK in capabilities)
    check_artifacts = known_artifacts is not None and Capability.ARTIFACTS in capabilities

    for axis_name, values in entity.facets.items():
        axis = schema.axis(axis_name)
        if axis is None:
            errors.append(
                DomainError(
                    code=ErrorCode.UNKNOWN_AXIS,
                    detail="axis is not declared in schema",
                    axis=axis_name,
                    entity_id=entity.id,
                )
            )
            continue

        if not axis.multi and len(values) > 1:
            errors.append(
                DomainError(
                    code=ErrorCode.CARDINALITY_VIOLATION,
                    detail=f"axis accepts a single value, got {len(values)}",
                    axis=axis_name,
                    entity_id=entity.id,
                )
            )

        for value in values:
            if value.kind != axis.kind.value:
                errors.append(
                    DomainError(
                        code=ErrorCode.TYPE_MISMATCH,
                        detail=f"axis expects {axis.kind.value} value, got {value.kind}",
                        axis=axis_name,
                        entity_id=entity.id,
                    )
                )
                continue

            if (
                axis.strict
                and isinstance(value, CategoricalValue)
                and value.value not in axis.values
            ):
                errors.append(
                    DomainError(
                        code=ErrorCode.UNKNOWN_CATEGORY,
                        detail=f"value is not in the axis vocabulary: {value.value!r}",
                        axis=axis_name,
                        entity_id=entity.id,
                    )
                )

            if (
                isinstance(value, ReferenceValue)
                and check_references
                and known_ids is not None
                and value.target not in known_ids
            ):
                errors.append(
                    DomainError(
                        code=ErrorCode.DANGLING_REFERENCE,
                        detail=f"referenced entity does not exist: {value.target!r}",
                        axis=axis_name,
                        entity_id=entity.id,
                    )
                )

    if check_artifacts and known_artifacts is not None:
        for role, reference in entity.artifacts.items():
            if reference.content_hash not in known_artifacts:
                errors.append(
                    DomainError(
                        code=ErrorCode.DANGLING_ARTIFACT,
                        detail=(f"artifact {role!r} is not stored: {reference.content_hash!r}"),
                        entity_id=entity.id,
                    )
                )

    return errors


def validate_artifact(
    artifact: Artifact,
    capabilities: frozenset[Capability] = frozenset(),
) -> list[DomainError]:
    """Проверить, что бэкенд умеет хранить артефакты.

    Сам артефакт уже проверен DTO (хэш соответствует данным); здесь —
    только совместимость с возможностями хранилища. Молчаливая запись в
    бэкенд без `Capability.ARTIFACTS` запрещена: иначе артефакт «есть» у
    клиента и «нет» в хранилище.
    """
    if Capability.ARTIFACTS not in capabilities:
        return [
            DomainError(
                code=ErrorCode.UNSUPPORTED_ARTIFACT,
                detail="backend does not support artifacts",
            )
        ]
    return []


def validate_query(
    schema: StorageSchema,
    query: Query,
    capabilities: frozenset[Capability] = frozenset(),
) -> list[DomainError]:
    """Проверить запрос против схемы и возможностей бэкенда (ADR-0012)."""
    errors: list[DomainError] = []

    if query.requires_unsupported:
        errors.append(
            DomainError(
                code=ErrorCode.UNSUPPORTED_QUERY,
                detail="any/not are reserved in AST and not supported in v0",
            )
        )

    for condition in query.all:
        errors.extend(_check_condition(schema, capabilities, condition))

    return errors


def _check_condition(
    schema: StorageSchema,
    capabilities: frozenset[Capability],
    condition: Filter,
) -> list[DomainError]:
    errors: list[DomainError] = []

    if condition.op is Operator.SCALAR_EQ:
        if schema.scalar(condition.axis) is None:
            return [
                DomainError(
                    code=ErrorCode.UNKNOWN_SCALAR,
                    detail="scalar is not declared in schema",
                    scalar=condition.axis,
                )
            ]
        if Capability.SCALAR_SEARCH not in capabilities:
            return [
                DomainError(
                    code=ErrorCode.UNSUPPORTED_QUERY,
                    detail="backend does not support scalar search",
                    scalar=condition.axis,
                )
            ]
        return errors

    axis = schema.axis(condition.axis)
    if axis is None:
        return [
            DomainError(
                code=ErrorCode.UNKNOWN_AXIS,
                detail="axis is not declared in schema",
                axis=condition.axis,
            )
        ]

    if condition.op in NUMERIC_OPERATORS and axis.kind is not AxisKind.MEASURABLE:
        errors.append(
            DomainError(
                code=ErrorCode.TYPE_MISMATCH,
                detail=f"operator {condition.op.value!r} requires a measurable axis",
                axis=axis.name,
            )
        )
    elif condition.op in SET_OPERATORS and axis.kind is AxisKind.MEASURABLE:
        errors.append(
            DomainError(
                code=ErrorCode.TYPE_MISMATCH,
                detail=f"operator {condition.op.value!r} cannot be used on a measurable axis",
                axis=axis.name,
            )
        )

    if condition.op not in EXISTENCE_OPERATORS:
        required = KIND_CAPABILITY[axis.kind]
        if required not in capabilities:
            errors.append(
                DomainError(
                    code=ErrorCode.UNSUPPORTED_QUERY,
                    detail=f"backend lacks capability {required.value!r}",
                    axis=axis.name,
                )
            )

    if axis.kind is AxisKind.CATEGORICAL and axis.strict:
        unknown = [
            value
            for value in condition.values
            if isinstance(value, str) and value not in axis.values
        ]
        if unknown:
            errors.append(
                DomainError(
                    code=ErrorCode.UNKNOWN_CATEGORY,
                    detail=f"values are not in the axis vocabulary: {sorted(unknown)}",
                    axis=axis.name,
                )
            )

    return errors


__all__ = ["validate_axis", "validate_entity", "validate_query", "validate_scalar"]
