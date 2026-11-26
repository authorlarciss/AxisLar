"""Артефакты: тяжёлые производные данные, адресуемые содержимым.

Артефакт — байты (превью, эмбеддинг, транскрипт), которые не являются
фасетом: фасет отвечает на «какое значение по оси», артефакт — «где лежат
данные». Адресация по хэшу содержимого делает дедупликацию свойством
модели, а не оптимизацией хранилища (ADR-0019, ADR-0017).

Ссылка на артефакт (`ArtifactRef`) живёт в объекте под ролью
(`preview`, `embedding`, ...), сам артефакт — отдельно, в хранилище.
Поэтому две копии одного файла ссылаются на одни байты.
"""

from __future__ import annotations

import hashlib

from pydantic import BaseModel, ConfigDict, Field, model_validator

#: Алгоритм адресации артефактов. Меняется только вместе с контрактом.
HASH_ALGO = "sha256"


def content_hash_of(data: bytes) -> str:
    """Хэш байтов — адрес артефакта в хранилище."""
    return hashlib.sha256(data).hexdigest()


class Artifact(BaseModel):
    """Байты плюс минимальные метаданные. Инвариант: хэш соответствует данным.

    `content_hash` не вычисляется на чтении: он проверяется на создании,
    иначе хранилище могло бы отдать «артефакт» с чужим адресом.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    content_hash: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    data: bytes

    @property
    def size(self) -> int:
        """Размер в байтах (выводится из данных, а не хранится рядом)."""
        return len(self.data)

    @model_validator(mode="after")
    def _check_hash(self) -> Artifact:
        if self.content_hash != content_hash_of(self.data):
            raise ValueError("artifact content_hash must be sha256 of its data")
        return self


def make_artifact(data: bytes, media_type: str) -> Artifact:
    """Собрать артефакт: адрес считается из данных."""
    return Artifact(content_hash=content_hash_of(data), media_type=media_type, data=data)


__all__ = ["HASH_ALGO", "Artifact", "content_hash_of", "make_artifact"]
