"""Ошибки модуля delta: исполнение запросов и состояния."""

from __future__ import annotations

from collections.abc import Sequence

from nu.psi.contracts.alpha import DomainError


class StorageQueryError(Exception):
    """Движок получил запрос, не прошедший валидацию.

    `DomainError` остаётся значением (DOMAIN §7): клиент получает их через
    `validate_query`. Исключение нужно, чтобы невалидированный запрос не
    вернул молча пустую выдачу.
    """

    def __init__(self, errors: Sequence[DomainError]) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(str(error) for error in self.errors))


__all__ = ["StorageQueryError"]
