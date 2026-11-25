"""Исключения границы исполнения запросов.

`DomainError` остаётся значением (DOMAIN §7): клиент получает их через
`IQueryResolver.check`. Это исключение — для случая, когда движок вызван
с невалидированным запросом: молча вернуть пустую выдачу нельзя, это
скрыло бы ошибку вызывающего.
"""

from __future__ import annotations

from collections.abc import Sequence

from nu.psi.contracts.alpha import DomainError


class StorageQueryError(Exception):
    """Движок получил запрос, не прошедший валидацию."""

    def __init__(self, errors: Sequence[DomainError]) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(str(error) for error in self.errors))


__all__ = ["StorageQueryError"]
