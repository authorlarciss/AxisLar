# Changelog

All notable changes to AxisLar are documented in this file.

Format based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

Проект ответвлён от шаблона BaseLar v0.6.1 (см. историю там). Первый
релиз AxisLar — `0.1.0`.

## [Unreleased]

## [0.2.2] - 2025-11-25

### Fixed

- CI: job `dist` получил `permissions: contents: write` — без этого
  прикрепление артефактов к релизу GitHub падало бы на токене с
  read-only правами. Теперь wheel и sdist появляются в релизе тега.

## [0.2.1] - 2025-11-25

### Added

- CI: на тег `v*` собирается дистрибутив (`make dist`) и артефакты
  прикрепляются к релизу; основной job гоняет `make check`.
- `tau/repo/test_package_name.py` — страж деплой-модели: в рабочем дереве
  пакет называется `nu`, дистрибутив — `axislar-core`.
- README: раздел «Установка» (только артефакты релиза) и актуальный статус.

### Changed

- `lambda/CONTRIBUTING.md` переписан под ядро: модуль-не-слой, связи через
  `psi.contracts`, фасад `nu/contracts.py`, деплой, тесты, ошибки.
- `lambda/VERSIONING.md`: раздел «Релиз и деплой» — `omega` содержит
  dev-имя пакета, установка из git не поддерживается.
- `lambda/PLAN.md`: статус 0.2.0, CLI вынесен в продукт AgoraLar.
- Удалён `eta/strip_template.py` и `make strip-template`: ядро не шаблон.

### Changed

- **Ядро отделено от продукта (ADR-0015).** Из пакета удалены `gamma`
  (CLI), `epsilon`, `zeta`, `iota`; `psi.application`/`context`/`interfaces`
  и снимок состояния удалены — это продуктовые сущности.
- Порт `IStorageEngine` и `StorageQueryError` переехали из `beta` в
  `delta`: модуль владеет понятием целиком, порт нужен только внешним
  бэкендам-плагинам. `IQueryResolver` и `BetaResolver` удалены;
  валидация — чистые функции `validate_*` в `beta`.
- `Capability` переехал в `alpha`: это словарь домена, а не деталь
  бэкенда.
- Новый фасад `Core` + `build_core()` — единственный вход в ядро.
- `CONTRACT_VERSION = "2"`: публичная поверхность изменилась ломающе.
- Дистрибутив переименован в `axislar-core`; консольный скрипт `axislar`
  удалён (CLI будет в продукте).

## [0.2.0] - 2025-11-25

Ядро выделено в самостоятельный проект (ADR-0015).

## [0.1.0] - 2025-11-25

Первый релиз: модель зафиксирована, семантика проверена контрактом.

### Added

- Документы самоопределения: `README.md`, `lambda/DOMAIN.md` (нормативная
  модель, включая обязательную таблицу семантики отсутствующих значений),
  `lambda/PLAN.md` (этапы M0–M6).
- ADR-0009…ADR-0014: многомерная модель; разреженность и семантика
  отсутствующих значений; reference-фасеты вместо relations; модель
  запросов (`none_of` вместо `!=`); in-memory backend как референс;
  удаление pipeline-scaffold.
- `alpha`: DTO модели — `AxisDefinition` (kind/multi/target/strict/values),
  `ScalarDefinition`, `FacetValue` (discriminated union), `Entity`,
  `Provenance`, `StorageSchema`, `Query`/`Filter`/`Operator`/`QueryResult`,
  `DomainError`/`ErrorCode`.
- `beta`: `IStorageEngine`, `IQueryResolver`, `Capability`,
  чистые функции `validate_axis`/`validate_scalar`/`validate_entity`/
  `validate_query`, `StorageQueryError`, `BetaResolver`.
- `delta`: `MemoryStorage` — эталонный бэкенд (разреженность, динамические
  оси, мультизначность, ссылки, пагинация), снимок состояния в JSON,
  `DeltaResolver`.
- `gamma`: CLI (`axislar`) — `schema add-axis|add-scalar|show`, `put`,
  `show`, `query`; консольный скрипт в `pyproject.toml`.
- `tau/contract`: контрактный набор бэкендов, параметризованный по
  фабрике; каждая строка таблицы DOMAIN §5 — отдельный кейс.

### Changed

- Проект переименован из шаблонного `baselar` в `axislar`; единственная
  зависимость ядра — pydantic 2.
- Template-обвязка снята: `tau/template/` удалён, маркер `template`
  убран; инварианты репозитория перенесены в `tau/repo/`.
- Pipeline-scaffold (`IProcessor`, `IWorkflow`, `IEventBus`, `IEvent`)
  удалён: домен не пайплайн (ADR-0014).
