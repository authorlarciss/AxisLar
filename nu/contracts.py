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
from nu.psi.contracts.alpha import Artifact as Artifact
from nu.psi.contracts.alpha import ArtifactRef as ArtifactRef
from nu.psi.contracts.alpha import AxisDefinition as AxisDefinition
from nu.psi.contracts.alpha import AxisKind as AxisKind
from nu.psi.contracts.alpha import Capability as Capability
from nu.psi.contracts.alpha import CategoricalValue as CategoricalValue
from nu.psi.contracts.alpha import DomainError as DomainError
from nu.psi.contracts.alpha import Entity as Entity
from nu.psi.contracts.alpha import EntityId as EntityId
from nu.psi.contracts.alpha import ErrorCode as ErrorCode
from nu.psi.contracts.alpha import FacetOwner as FacetOwner
from nu.psi.contracts.alpha import FacetValue as FacetValue
from nu.psi.contracts.alpha import Filter as Filter
from nu.psi.contracts.alpha import MeasurableValue as MeasurableValue
from nu.psi.contracts.alpha import Operator as Operator
from nu.psi.contracts.alpha import Origin as Origin
from nu.psi.contracts.alpha import Provenance as Provenance
from nu.psi.contracts.alpha import Query as Query
from nu.psi.contracts.alpha import QueryResult as QueryResult
from nu.psi.contracts.alpha import ReferenceValue as ReferenceValue
from nu.psi.contracts.alpha import ScalarDefinition as ScalarDefinition
from nu.psi.contracts.alpha import StorageSchema as StorageSchema
from nu.psi.contracts.alpha import content_hash_of as content_hash_of
from nu.psi.contracts.alpha import make_artifact as make_artifact
from nu.psi.contracts.beta import ActionKind as ActionKind
from nu.psi.contracts.beta import SyncConflict as SyncConflict
from nu.psi.contracts.beta import SyncPlan as SyncPlan
from nu.psi.contracts.beta import SyncPolicy as SyncPolicy
from nu.psi.contracts.beta import apply_plan as apply_plan
from nu.psi.contracts.beta import inherit_derived as inherit_derived
from nu.psi.contracts.beta import merge_entity as merge_entity
from nu.psi.contracts.beta import plan_sync as plan_sync
from nu.psi.contracts.beta import validate_artifact as validate_artifact
from nu.psi.contracts.beta import validate_axis as validate_axis
from nu.psi.contracts.beta import validate_entity as validate_entity
from nu.psi.contracts.beta import validate_query as validate_query
from nu.psi.contracts.beta import validate_scalar as validate_scalar
from nu.psi.contracts.delta import IEntitySource as IEntitySource
from nu.psi.contracts.delta import IStorageEngine as IStorageEngine
from nu.psi.contracts.delta import StorageQueryError as StorageQueryError
from nu.psi.contracts.iota import entity_id_for as entity_id_for
from nu.psi.contracts.iota import run_source_contract as run_source_contract
from nu.psi.contracts.iota import run_source_sync_contract as run_source_sync_contract
from nu.psi.contracts.iota import run_storage_contract as run_storage_contract
from nu.psi.contracts.mu import CONTRACT_VERSION as CONTRACT_VERSION
from nu.psi.contracts.mu import __version__ as __version__

__all__ = [
    "ActionKind",
    "Artifact",
    "ArtifactRef",
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
    "FacetOwner",
    "FacetValue",
    "Filter",
    "IEntitySource",
    "IStorageEngine",
    "MeasurableValue",
    "Operator",
    "Origin",
    "Provenance",
    "Query",
    "QueryResult",
    "ReferenceValue",
    "ScalarDefinition",
    "StorageQueryError",
    "StorageSchema",
    "SyncConflict",
    "SyncPlan",
    "SyncPolicy",
    "__version__",
    "apply_plan",
    "build_core",
    "entity_id_for",
    "run_source_contract",
    "run_source_sync_contract",
    "run_storage_contract",
    "inherit_derived",
    "content_hash_of",
    "make_artifact",
    "merge_entity",
    "plan_sync",
    "validate_artifact",
    "validate_axis",
    "validate_entity",
    "validate_query",
    "validate_scalar",
]
