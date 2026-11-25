# Changelog

All notable changes to AxisLar are documented in this file.

Format based on [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/),
project adheres to [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

Проект ответвлён от шаблона BaseLar v0.6.1 (см. историю там). Первый
релиз AxisLar — `0.1.0`.

## [Unreleased]

### Added

- Самоопределение проекта: `README.md`, `lambda/DOMAIN.md` (нормативная
  модель), `lambda/PLAN.md` (этапы M0–M5).
- ADR-0009…ADR-0013: многомерная модель; разреженность и семантика
  отсутствующих значений; reference-фасеты вместо relations; модель
  запросов (`none_of` вместо `!=`); in-memory backend как референс.

### Changed

- Template-обвязка снята: `tau/template/` удалён, маркер `template`
  убран из `pyproject.toml`; инварианты репозитория перенесены в
  `tau/repo/` (раскладка тестов, структура модулей).
- `tau/conftest.py`: уровни — `unit` (по умолчанию), `integration`,
  `contract`, `e2e`.
