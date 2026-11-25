.PHONY: help install install-pip lock lint lint-imports contracts contracts-check strip-template typecheck format format-check check ci test test-unit test-integration test-contract test-e2e test-module run clean

PYTHON := python3
VENV := .venv
PRECOMMIT := $(VENV)/bin/pre-commit
PYTEST := $(VENV)/bin/pytest
RUFF := $(VENV)/bin/ruff
LINT_IMPORTS := $(VENV)/bin/lint-imports
MYPY := $(VENV)/bin/mypy
PY := $(VENV)/bin/python

help:
	@echo "Доступные команды:"
	@echo "  make install       — установить зависимости через uv sync (рекомендуется)"
	@echo "  make install-pip   — установить зависимости через venv+pip (fallback)"
	@echo "  make lock          — обновить uv.lock после изменения зависимостей"
	@echo "  make lint          — ruff check"
	@echo "  make lint-imports  — import-linter"
	@echo "  make contracts     — пересчитать белые списки import-linter из дерева nu/"
	@echo "  make contracts-check — проверить, что белые списки не устарели"
	@echo "  make typecheck     — mypy (strict, nu + tau + eta)"
	@echo "  make format        — ruff format + ruff check --fix"
	@echo "  make format-check  — ruff format --check (без изменений)"
	@echo "  make check         — format-check + lint + lint-imports + contracts-check + typecheck + test"
	@echo "  make ci            — алиас make check"
	@echo "  make test          — pytest"
	@echo "  make test-unit     — только маркер unit"
	@echo "  make test-integration — только маркер integration"
	@echo "  make test-contract — только маркер contract"
	@echo "  make test-e2e      — только маркер e2e"
	@echo "  make test-module M=beta — тесты одного модуля с его покрытием"
	@echo "  make strip-template — снести template-обвязку при форке"
	@echo "  make run           — запуск nu.main"
	@echo "  make clean         — удалить кэши и venv"

install:
	@command -v uv >/dev/null 2>&1 || (echo "uv not found. Install it or use 'make install-pip'."; exit 1)
	uv sync --extra dev
	$(PRECOMMIT) install

install-pip:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -e ".[dev]"
	$(PRECOMMIT) install

lock:
	@command -v uv >/dev/null 2>&1 || (echo "uv not found."; exit 1)
	uv lock

lint:
	$(RUFF) check nu tau eta

lint-imports:
	$(LINT_IMPORTS)

contracts:
	$(PY) -m eta.sync_contracts

contracts-check:
	$(PY) -m eta.sync_contracts --check

typecheck:
	$(MYPY) nu tau eta

format:
	$(RUFF) format nu tau eta
	$(RUFF) check --fix nu tau eta

format-check:
	$(RUFF) format --check nu tau eta

check: format-check lint lint-imports contracts-check typecheck test

ci: check

test:
	$(PYTEST)

test-unit:
	$(PYTEST) -m unit

test-integration:
	$(PYTEST) -m integration

test-contract:
	$(PYTEST) -m contract

test-e2e:
	$(PYTEST) -m e2e

test-module:
	$(PYTEST) tau/$(M) --cov=nu.$(M)

strip-template:
	$(PY) -m eta.strip_template

run:
	$(VENV)/bin/axislar schema show

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	rm -rf $(VENV)
	rm -rf .import_linter_cache
	rm -rf .coverage htmlcov .mypy_cache
