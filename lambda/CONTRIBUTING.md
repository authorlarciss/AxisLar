# Правила разработки AxisLar (ядро)

Коротко: модуль — не слой, связи — только через `psi.contracts`, наружу —
только `nu/contracts.py`, деплой — только через `make dist`.

## Ветки и коммиты

Модель ветвления — `lambda/VERSIONING.md` (Hellenic Git Flow). Имена
коммитов — Conventional Commits: `feat`, `fix`, `chore`, `docs`, `test`,
`refactor`.

Перед коммитом:

    make check     # формат, линт, контракты, типы, тесты

## Модуль — не слой (ADR-0009)

- Модуль владеет понятием целиком: порт и его эталонная реализация живут
  в одном модуле. Пример: `delta` объявляет `IStorageEngine` и содержит
  `MemoryStorage` в `_internal/`.
- Модуль **не** задаёт шаблон, который обязан реализовать другой модуль
  этого же проекта.
- Порт оправдан только для **внешней поставки** (плагин, продукт, клиент
  в другом дистрибутиве). Такой порт документируется и версионируется
  через `CONTRACT_VERSION` (`nu.mu.public`).
- Доменные правила — чистые функции, а не ABC «на будущее»:
  `validate_axis/scalar/entity/query` возвращают `list[DomainError]`.

## Связи между модулями

Между модулями — только `psi.contracts`:

    from nu.psi.contracts.alpha import Entity
    from nu.psi.contracts.beta import validate_query

Внутри своего модуля — прямые импорты из `public/`. Внешним потребителям
(плагины, продукт) доступен только фасад:

    from nu.contracts import Core, Entity, IStorageEngine, build_core

После деплой-переименования это `axislar_core.contracts`.

## public / _internal / resolver

- `public/` — API модуля; `_internal/` — реализация, недоступная никому.
- Единственный путь к `_internal/` — `public/resolver.py` с lazy import:

        class DeltaResolver:
            def make_memory_storage(self, schema: StorageSchema | None = None) -> IStorageEngine:
                from nu.delta._internal.memory import MemoryStorage
                return MemoryStorage(schema=schema)

- **На каждую фабрику — тест**, который проверяет `isinstance(result,
  IInterface)` и тем самым покрывает строку lazy import.
- `__init__.py` — только docstring, без реэкспортов.
- Реэкспорт — строго `from X import Y as Y`.

## Async и ошибки

- Все интерфейсы — `async def`; синхронная реализация просто без `await`.
- Ошибки домена — значения: `DomainError` со `code` из `ErrorCode`.
  Ничего не бросаем и не логируем в проверках.
- Исключение — граница исполнения: `StorageQueryError`, когда движок
  получил запрос, не прошедший валидацию (молча вернуть пустую выдачу
  нельзя).

## Тесты

Раскладка — по модулям (ADR-0008 в BaseLar, `tau/repo/test_layout.py`):

    tau/<module>/test_<что>.py

Общие каталоги (без модуля-владельца): `tau/contract/` — контрактный
набор бэкендов, `tau/eta/` — тесты инструментов, `tau/repo/` —
инварианты репозитория. Уровни — маркеры: `unit` (по умолчанию),
`integration`, `contract`, `e2e`.

Контрактный набор (`tau/contract/`) — единственное место, где живёт
семантика модели (таблица `lambda/DOMAIN.md` §5). Новый бэкенд
подключается строкой в `BACKENDS` и обязан пройти набор целиком, без
правок в тестах.

## Логирование

`get_logger(__name__)` из `sigma`, контекст (`request_id`, `user_id`) —
через `ContextVar`. Настройка — в точке входа (`nu/main.py`), не в ядре.

## Деплой

Пакет в разработке — всегда `nu`. Дистрибутив собирается с уникальным
именем (ADR-0010 BaseLar):

    make dist                        # DIST_PACKAGE=axislar_core
    make dist DIST_PACKAGE=other_nu  # другой форк

`eta/rename_package.py` копирует дерево в `.deploy/`, переименовывает
пакет и переписывает импорты/конфиги. Артефакты — в `dist/`.

**Установка из git не поддерживается**: в репозитории пакет называется
`nu`, а в артефакте — `axislar_core`. Ставить нужно из wheel/sdist
релиза (см. `lambda/VERSIONING.md`, раздел «Релиз и деплой»).

## Окружение

- Python 3.13 (`uv python install 3.13`), зависимости — `uv sync --extra dev`.
- `make help` — список таргетов.
- mypy strict, ruff format (не black), import-linter, pytest.
