"""Возможности бэкенда: словарь домена, а не деталь реализации.

Живут в `alpha`, потому что это часть языка модели: и валидация запросов,
и бэкенды, и клиенты говорят об одних и тех же возможностях. Если бы
`Capability` лежал в модуле-бэкенде, `beta` пришлось бы зависеть от
`delta` — то есть от реализации.
"""

from __future__ import annotations

from enum import StrEnum


class Capability(StrEnum):
    """Что бэкенд реально умеет.

    Запрос, требующий отсутствующей возможности, обязан быть отвергнут
    валидацией (`UnsupportedQuery`), а не исполнен полным перебором в
    обход индексов (ADR-0013).
    """

    QUERY_CATEGORICAL = "query_categorical"
    QUERY_MEASURABLE = "query_measurable"
    QUERY_REFERENCE = "query_reference"
    SCALAR_SEARCH = "scalar_search"
    REFERENCE_CHECK = "reference_check"
    WRITE_BULK = "write_bulk"
    DYNAMIC_AXES = "dynamic_axes"
    ARTIFACTS = "artifacts"
    TRAVERSE_REFERENCES = "traverse_references"


__all__ = ["Capability"]
