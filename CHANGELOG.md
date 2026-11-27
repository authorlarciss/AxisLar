# Changelog

All notable changes to AxisLar are documented in this file.

Format based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

Проект ответвлён от шаблона BaseLar v0.6.1 (см. историю там). Первый
релиз AxisLar — `0.1.0`.

## [Unreleased]

## [0.14.2] - 2026-11-27

### Fixed

- Текст `reference_in_use` склоняется по числу («ссылаются 1 объект», а не
  «1 объекта»): сообщение видно человеку в CLI и UI.

## [0.14.1] - 2026-11-27

### Fixed

- `tombstone_entity`, `cascade_order`, `collect_dangling` и `DanglingLinks` не
  попали в публичный фасад `nu.contracts` в 0.14.0 — для продукта и плагинов
  их не существовало. Добавлены, плюс тест на полноту фасада
  (`tau/psi/test_facade.py`).

## [0.14.0] - 2026-11-27

### Added

- **Политика удаления** (ADR-0025): `tombstone_entity(engine, id)` —
  пользовательское удаление, которое отказывает при живых входящих ссылках
  (`REFERENCE_IN_USE`) и не пишет ничего; пишет через `upsert` с
  `expected_rev`, поэтому гонка с правкой даёт `CONFLICT`.
- `cascade_order(index, id)` — порядок удаления цели вместе со ссылающимися
  (сначала ссылающиеся); `collect_dangling(engine, ids)` — отчёт «какие
  ссылки стали висячими», для синхронизации.
- `ErrorCode.REFERENCE_IN_USE`, `ErrorCode.UNSUPPORTED_CAPABILITY`.
- `lambda/DOMAIN.md` §3.5 — инварианты удаления (D1–D6).

### Changed

- Бэкенд без `TRAVERSE_REFERENCES` удалять отказывается: политику нельзя
  проверить — нельзя и утверждать, что проверили.
- Контракт не менялся (6): порты те же, `upsert` ведёт себя как раньше.

## [0.13.1] - 2026-11-27

### Fixed

- Контрактный набор проверяет ревизии **последними**: у файловых бэкендов
  объекты проверки видны остальным проверкам (удалять нечего), и `none_of`
  начинал возвращать лишнее. Нашёл на `store_sqlite`.

## [0.13.0] - 2026-11-27

### Added

- **Ревизии объектов** (ADR-0024): `Entity.rev`, `upsert(..., expected_rev=...)`,
  ошибка `CONFLICT`. Ревизию ставит бэкенд (1 при создании, +1 при
  обновлении); несовпадение ожидаемой и текущей не пишет ничего.
  `bulk_upsert` ставит ревизии, но не проверяет их: это путь импорта.
- Контрактный набор проверяет ревизии на отдельном инстансе бэкенда:
  создание с `expected_rev=0`, рост, конфликт на устаревшей, отказ без
  создания.

### Changed

- **Контракт 6** (ломающее изменение порта): `IStorageEngine.upsert`
  принимает `expected_rev`. Плагины объявляют `requires_contract >=6,<7`.
- `lambda/DOMAIN.md` §3.4 — нормативные инварианты ревизий.

## [0.12.1] - 2026-11-27

### Changed

- **Воспроизводимые сборки**: `SOURCE_DATE_EPOCH` от времени коммита в
  `make dist`. Два прогона сборки одного коммита дают одинаковый sha256,
  поэтому колесо из CI и локальной сборки совпадает байт в байт.
- **Публикация по тегу**: job `publish` включён (переменная репозитория
  `PYPI_OIDC=true`), перешёл с `--check-url` на проверку
  `/pypi/<проект>/<версия>/json` — повторный запуск пропускает уже
  опубликованные версии вместо падения на несовпадении хеша.

## [0.12.0] - 2026-11-27

### Changed

- **`apply_plan` пишет пачкой** (`bulk_upsert`) вместо последовательных
  `upsert`: первый импорт связанных заметок больше не падает на
  `DanglingReference` из-за порядка действий в плане (ROADMAP §5.1
  продукта). Контракт порта не менялся.
- **`bulk_upsert` стал атомарным**: пачка проверяется целиком, и при
  любой ошибке не пишется ничего. Раньше валидные объекты пачки
  записывались, а ссылки на отвергнутые оставались висячими — модель
  это запрещает. Зафиксировано в docstring порта.

### Added

- ADR-0022 и `lambda/DOMAIN.md` §3.3: пачка `bulk_upsert` атомарна,
  контрактный тест переименован в `test_bulk_upsert_is_atomic`.
- Контрактный набор `run_reference_index_contract(factory)` для порта
  `IReferenceIndex` (ADR-0021): входящие ссылки, фильтр по осям, «пустой
  список = никаких осей», перезапись объекта, пачка со ссылками внутри,
  tombstone и `include_deleted`, детерминированный порядок, отсутствие
  индексации не-reference фасетов. Набор ловит «объявил возможность, а
  порт не реализовал». Экспорт: `nu.contracts`.
- CI: job `publish` для PyPI по тегу через Trusted Publishing. Выключен
  до настройки publisher'а на PyPI, включается переменной репозитория
  `PYPI_OIDC=true`; до этого релиз публикуется вручную токеном.

## [0.11.0] - 2026-11-27

### Added

- **Обратные ссылки** (ADR-0021): DTO `ReferenceLink(axis, entity_id)`,
  порт `IReferenceIndex.references_to(entity_id, axes, include_deleted)`
  и возможность `Capability.TRAVERSE_REFERENCES`. Эталонный
  `MemoryStorage` ведёт обратный индекс «цель → ось → источники» и
  обновляет его в `upsert`/`bulk_upsert`, поэтому обход не пересчитывается
  на чтении. Изменение аддитивное: `IStorageEngine` не тронут, контракт
  остаётся 5, плагины без поддержки порта просто не объявляют
  возможность.
- `lambda/DOMAIN.md` §3.2 — нормативные инварианты R1–R6 обратных ссылок.

## [0.10.1] - 2026-11-26

### Added

- Лицензия **MIT** (`LICENSE`), поле `license = "MIT"` и `license-files`
  в метаданных, `[project.urls]`.
- Репозиторий публикуется в open source: код ядра доступен без
  ограничений, контракт (5) и API не менялись.

## [0.10.0] - 2025-11-25

### Added

- **Клиенты, фичи и варианты** (ADR-0020): `ClientProfile(name, features,
  variants)`, `FeatureVariant(name, clients, fallback)`,
  `FeatureManifest(provider, feature, variants)`.
- `resolve_feature` / `resolve_features` (`beta`): детерминированный выбор
  варианта (провайдеры по имени, варианты — в порядке объявления),
  fallback-цепочки в пределах манифеста с ограничением глубины и
  обнаружением циклов, «не разрешилось» — значение с причиной.
- `fits(profile, variant)`: клиент может сузить выбор своими `variants`,
  провайдер — ограничить вариант списком `clients`.

### Changed

- Контракт остаётся **5**: порт `IStorageEngine`/`IEntitySource` не
  менялся, расширение аддитивно.
- PLAN: M7 отмечен выполненным, ADR-roadmap — 0020 занят.

## [0.9.1] - 2025-11-25

### Fixed

- **Бинарные артефакты в JSON**: `Artifact.data` сериализуется base64
  (url-safe) вместо попытки прочитать байты как UTF-8. Раньше
  `model_dump_json` падал на любом не-UTF-8 артефакте
  (`Error serializing to JSON: invalid utf-8 sequence`), а JSON-хранилище
  продукта не могло сохранить картинку. Контракт не меняется (5).

## [0.9.0] - 2025-11-25

### Added

- **Артефакты** (ADR-0019, контракт **5**): `Artifact(content_hash,
  media_type, data)` и `ArtifactRef(content_hash, media_type, size,
  derived_by)`, поле `Entity.artifacts` (роль → ссылка). Адрес — sha256
  содержимого, дедупликация свойство модели: две копии одного файла
  ссылаются на одни байты.
- Порт `IStorageEngine`: `put_artifact`, `get_artifact`, `list_artifacts`,
  `delete_artifact`; `Capability.ARTIFACTS`. Бэкенд без возможности
  обязан отказать (`UnsupportedArtifact`), а не отдать пустоту.
- Ошибки: `UnsupportedArtifact`, `DanglingArtifact`, `ArtifactMismatch`,
  `ArtifactInUse`. Ссылка на отсутствующий артефакт проверяется только
  при объявленной возможности (как `DanglingReference`).
- `beta`: `validate_artifact`, `validate_entity(known_artifacts=...)`.
- `iota`: контрактный набор проверяет дедупликацию, метаданные, конфликт
  `media_type`, ссылку, занятость и удаление, а также корректный отказ
  бэкенда без артефактов.
- `Core`: делегаты `put_artifact`/`get_artifact`/`list_artifacts`/
  `delete_artifact`; `contracts` экспортирует `Artifact`, `ArtifactRef`,
  `make_artifact`, `content_hash_of`, `validate_artifact`.
- DOMAIN §3.1: инварианты A6–A10, обновлён список ошибок §7.

### Changed

- **Контракт 5**: плагины и продукт переходят на диапазон `>=5,<6`.
- PLAN: таблица ADR roadmap приведена к фактическим файлам (нумерация —
  своя в каждом проекте), M8 отмечен выполненным.

## [0.8.0] - 2025-11-25

### Added

- **Переиспользование производных фактов по `content_hash`** (ADR-0017):
  `inherit_derived(target, donors)` переносит фасеты с владельцем
  `analysis` (вместе с `derived_by`) на объект с тем же содержимым.
  Отдельного кэша нет — им служит хранилище.
- Встроено в `plan_sync`: `create`, `move` и `update` со сменой содержимого
  подхватывают известные производные факты; копия проекта не требует
  повторного анализа.
- Неоднозначность разрешается детерминированно: свежесть `Provenance.at`,
  при равенстве времени и разных значениях ось пропускается.

## [0.7.0] - 2025-11-25

### Added

- **Владелец фасета** `FacetOwner` (`source`/`user`/`analysis`) и
  `Entity.owners` (ADR-0018).
- `merge_entity(scanned, existing)`: при обновлении фасеты источника
  обновляются, `user`/`analysis` сохраняются, оси, которые источник больше
  не отдаёт, освобождаются.
- Контрактный набор источников требует разметки владельцев (`source`).
- DOMAIN: поле `owners` и правила слияния.

### Changed

- **`CONTRACT_VERSION = "4"`**: адаптеры-источники обязаны размечать
  фасеты; источники под contract 3 отклоняются реестром.
- Сравнение «объект изменился» учитывает только факты источника
  (`content_hash`, скаляры, `kind`, `source`-фасеты) — ручная правка не
  вызывает перезапись.

## [0.6.1] - 2025-11-25

### Added

- Политика идентичности `entity_id_for(source_id, key)` (`nu.iota`):
  детерминированный `UUIDv5` в пространстве имён AxisLar; экспорт через
  фасад `nu.contracts`. Адаптеры обязаны пользоваться ею, иначе
  `plan_sync` не сопоставит объекты.
- `run_source_sync_contract(factory, schema)`: стабильность повторного
  скана (объекты целиком, не только `id`), соответствие `id` политике,
  наличие `content_hash`/`hash_algo` — без хэша переименования не
  отслеживаются.

## [0.6.0] - 2025-11-25

### Added

- `IStorageEngine.list_entities(include_deleted: bool = False)` — перечень
  объектов в порядке `id`; tombstone видны только с `include_deleted=True`.
- Контрактный набор проверяет tombstone-семантику: `get`, `count`,
  `query`, `list_entities` не видят удалённых, `include_deleted=True`
  видит, resurrect возвращает объект.

### Changed

- **`CONTRACT_VERSION = "3"`**: добавлен абстрактный метод порта —
  бэкенды-плагины обязаны его реализовать. Старые плагины (`>=2,<3`) будут
  отклонены реестром с явной причиной.

## [0.5.0] - 2025-11-25

### Added

- **Синхронизация источника** (ADR-0016): `Origin` в `Entity` (источник,
  ключ, `content_hash`/`hash_algo`), `deleted_at` — tombstone;
  `plan_sync(scanned, existing, policy)` — чистая функция с действиями
  `create/update/move/tombstone/resurrect` и списком конфликтов;
  `apply_plan(engine, plan)` — применение.
- Правило переименования: `id` сохраняется, меняется `origin.key`
  (move определяется по `content_hash`, неоднозначность — конфликт).
- Неполный скан (`complete=False`) не порождает tombstone.
- ADR-0017: content-addressed кэш производных фактов (проектирование
  под будущую реализацию после провенанса).
- DOMAIN §9: нормативная таблица поведения синхронизации.

## [0.4.0] - 2025-11-25

### Added

- **Порт источника** `IEntitySource` (`delta`): адаптер отдаёт объекты
  потоком (`scan`), сам отвечает за нормализацию и стабильные `id`;
  `describe()` — человекочитаемое описание источника.
- **Контрактный набор источников** `run_source_contract(factory, schema)`:
  валидность объектов против схемы, непустые и уникальные `id`,
  детерминированность сканирования (идемпотентный импорт). Экспорт — через
  фасад `nu.contracts`.

## [0.3.0] - 2025-11-25

### Added

- **Контрактный набор для бэкендов** (`nu.iota`): `run_storage_contract(factory)`
  прогоняет семантику модели против любой реализации `IStorageEngine` —
  таблицу отсутствующих значений, мультизначность, разреженность, ссылки,
  кардинальность, пагинацию, отказ на `any`/`not`. Экспортируется через
  фасад `nu.contracts`; автор плагина оборачивает вызов в свой тест.
- Модуль `iota` в ядре и `psi.contracts.iota`; тесты набора, включая
  проверку, что набор ловит нарушения (порядок выдачи, пустые
  `capabilities`).

## [0.2.5] - 2025-11-25

### Added

- `py.typed` (PEP 561): типы ядра видны mypy strict у потребителей —
  продукт и плагины проверяются без `ignore_missing_imports`.

## [0.2.4] - 2025-11-25

### Fixed

- CI: прикрепление к GitHub Release переведено в best-effort
  (`continue-on-error`). GitHub Releases API на репозитории отдаёт HTTP 500
  и на ручное создание релиза, поэтому источник истины — workflow-artifacts
  (`gh run download <run-id> -n dist`), а релиз — необязательное удобство.
- Release notes берутся из `CHANGELOG.md`, без `--generate-notes`.

## [0.2.3] - 2025-11-25

### Fixed

- CI: прикрепление артефактов переведено на `gh release create/upload`
  вместо `softprops/action-gh-release` — тот ретраил HTTP 500 от GitHub
  API и падал без диагностики. Шаг идемпотентен, логирует список
  прикреплённых файлов.

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
