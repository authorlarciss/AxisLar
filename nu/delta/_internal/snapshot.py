"""Снимок in-memory хранилища в JSON-файл.

Это **не** бэкенд: снимок перезаписывает файл целиком, запросы по нему не
выполняются. Настоящий `JsonStorage` (с фильтрацией по файлу) — отдельный
бэкенд и отдельный этап (PLAN M6).

Нужен, чтобы CLI был осмысленным между вызовами процесса.
"""

from __future__ import annotations

import json
from pathlib import Path

from nu.delta._internal.memory import MemoryStorage
from nu.delta.public.errors import SnapshotError
from nu.psi.contracts.alpha import Entity, StorageSchema

#: Версия формата снимка. Меняется при несовместимом изменении файла.
SNAPSHOT_VERSION = 1


def save(storage: MemoryStorage, path: Path) -> None:
    """Записать схему и объекты в файл (атомарно, через временный файл)."""
    payload = {
        "version": SNAPSHOT_VERSION,
        "schema": json.loads(storage.schema.model_dump_json()),
        "entities": [json.loads(entity.model_dump_json()) for entity in storage.iter_entities()],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def load(path: Path) -> MemoryStorage:
    """Прочитать снимок; отсутствующий файл — пустое хранилище."""
    if not path.is_file():
        return MemoryStorage()

    raw = json.loads(path.read_text(encoding="utf-8"))
    version = raw.get("version") if isinstance(raw, dict) else None
    if version != SNAPSHOT_VERSION:
        raise SnapshotError(
            f"unsupported snapshot version: {version!r} (expected {SNAPSHOT_VERSION})"
        )

    try:
        schema = StorageSchema.model_validate(raw["schema"])
        entities = [Entity.model_validate(item) for item in raw["entities"]]
    except (KeyError, TypeError, ValueError) as error:
        raise SnapshotError(f"broken snapshot: {error}") from error

    storage = MemoryStorage(schema=schema)
    for entity in entities:
        errors = storage.upsert_sync(entity)
        if errors:
            raise SnapshotError(f"broken snapshot: {errors[0]}")
    return storage


__all__ = ["SNAPSHOT_VERSION", "SnapshotError", "load", "save"]
