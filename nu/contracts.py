"""Единственная поверхность ядра, на которую могут смотреть извне.

Плагины и продукт импортируют **только этот модуль**:

    from nu.contracts import Core, Entity, IStorageEngine, validate_query

Внутренняя раскладка (`psi.contracts.alpha`, `delta.public`, ...) вправе
меняться; этот фасад — стабильный контракт и версионируется через
`CONTRACT_VERSION`. После деплой-переименования модуль становится
`<dist>.contracts`.
"""

from nu.psi import Core as Core
from nu.psi import build_core as build_core
from nu.psi.contracts.alpha import AxisDefinition as AxisDefinition
from nu.psi.contracts.alpha import AxisKind as AxisKind
from nu.psi.contracts.alpha import Capability as Capability
from nu.psi.contracts.alpha import CategoricalValue as CategoricalValue
from nu.psi.contracts.alpha import DomainError as DomainError
from nu.psi.contracts.alpha import Entity as Entity
from nu.psi.contracts.alpha import EntityId as EntityId
from nu.psi.contracts.alpha import ErrorCode as ErrorCode
from nu.psi.contracts.alpha import FacetValue as FacetValue
from nu.psi.contracts.alpha import Filter as Filter
from nu.psi.contracts.alpha import MeasurableValue as MeasurableValue
from nu.psi.contracts.alpha import Operator as Operator
from nu.psi.contracts.alpha import Provenance as Provenance
from nu.psi.contracts.alpha import Query as Query
from nu.psi.contracts.alpha import QueryResult as QueryResult
from nu.psi.contracts.alpha import ReferenceValue as ReferenceValue
from nu.psi.contracts.alpha import ScalarDefinition as ScalarDefinition
from nu.psi.contracts.alpha import StorageSchema as StorageSchema
from nu.psi.contracts.beta import validate_axis as validate_axis
from nu.psi.contracts.beta import validate_entity as validate_entity
from nu.psi.contracts.beta import validate_query as validate_query
from nu.psi.contracts.beta import validate_scalar as validate_scalar
from nu.psi.contracts.delta import IEntitySource as IEntitySource
from nu.psi.contracts.delta import IStorageEngine as IStorageEngine
from nu.psi.contracts.delta import StorageQueryError as StorageQueryError
from nu.psi.contracts.iota import run_source_contract as run_source_contract
from nu.psi.contracts.iota import run_storage_contract as run_storage_contract
from nu.psi.contracts.mu import CONTRACT_VERSION as CONTRACT_VERSION
from nu.psi.contracts.mu import __version__ as __version__

__all__ = [
    "AxisDefinition",
    "AxisKind",
    "CONTRACT_VERSION",
    "Capability",
    "CategoricalValue",
    "Core",
    "DomainError",
    "Entity",
    "EntityId",
    "ErrorCode",
    "FacetValue",
    "Filter",
    "IEntitySource",
    "IStorageEngine",
    "MeasurableValue",
    "Operator",
    "Provenance",
    "Query",
    "QueryResult",
    "ReferenceValue",
    "ScalarDefinition",
    "StorageQueryError",
    "StorageSchema",
    "__version__",
    "build_core",
    "run_source_contract",
    "run_storage_contract",
    "validate_axis",
    "validate_entity",
    "validate_query",
    "validate_scalar",
]
