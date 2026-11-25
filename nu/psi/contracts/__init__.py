"""Публичные контракты модулей ядра.

Модули импортируют контракты конкретных модулей через подмодули:
`nu.psi.contracts.alpha`, `nu.psi.contracts.beta` и т.д.

Агрегат `Contracts` — удобная точка доступа для инструментов и тестов.
"""

from . import alpha, beta, delta, mu, sigma


class Contracts:
    """Namespace со ссылками на модули-контракты."""

    alpha = alpha
    beta = beta
    delta = delta
    sigma = sigma
    mu = mu


__all__ = ["Contracts", "alpha", "beta", "delta", "sigma", "mu"]
