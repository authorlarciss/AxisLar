"""Выбор варианта фичи для клиента (ADR-0020).

Функции чистые: ни состояния, ни побочных эффектов, ни исключений —
неразрешённая фича возвращается значением с причиной (как доменные
ошибки, DOMAIN §7). Порядок обхода детерминирован: провайдеры по имени,
варианты — в порядке объявления в манифесте.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from nu.psi.contracts.alpha import ClientProfile, FeatureManifest, FeatureVariant

#: Предел длины fallback-цепочки: защита от «умных» манифестов.
MAX_FALLBACK_DEPTH = 8


@dataclass(frozen=True, slots=True)
class FeatureResolution:
    """Итог выбора: вариант, провайдер и причина отказа."""

    feature: str
    variant: str | None = None
    provider: str | None = None
    fallback_used: bool = False
    reason: str | None = None

    @property
    def resolved(self) -> bool:
        """Есть ли вариант, который можно отдать клиенту."""
        return self.variant is not None

    def describe(self) -> str:
        if self.variant is None:
            return f"{self.feature}: не разрешена ({self.reason})"
        suffix = " (через fallback)" if self.fallback_used else ""
        return f"{self.feature}: {self.variant} от {self.provider}{suffix}"


def resolve_feature(
    feature: str,
    profile: ClientProfile,
    manifests: Iterable[FeatureManifest],
) -> FeatureResolution:
    """Подобрать вариант фичи для клиента.

    Шаги: берём манифесты этой фичи (по имени провайдера), идём по вариантам
    в порядке объявления, проверяем совместимость с клиентом; если вариант
    не подошёл — идём по его `fallback` внутри того же манифеста. Цикл
    fallback'ов обрывается и попадает в причину, а не в бесконечный обход.
    """
    if feature not in profile.features:
        return FeatureResolution(feature=feature, reason="client does not request this feature")

    providers = sorted(
        (manifest for manifest in manifests if manifest.feature == feature),
        key=lambda manifest: manifest.provider,
    )
    if not providers:
        return FeatureResolution(feature=feature, reason="no provider declares this feature")

    cycles: list[str] = []
    for manifest in providers:
        index = {variant.name: variant for variant in manifest.variants}
        for variant in manifest.variants:
            if fits(profile, variant):
                return FeatureResolution(
                    feature=feature,
                    variant=variant.name,
                    provider=manifest.provider,
                )
            resolved, cycle = _follow_fallback(profile, variant, index)
            if resolved is not None:
                return FeatureResolution(
                    feature=feature,
                    variant=resolved,
                    provider=manifest.provider,
                    fallback_used=True,
                )
            if cycle:
                cycles.append(f"{manifest.provider}:{variant.name}")

    reason = "no compatible variant"
    if cycles:
        reason = f"{reason}; fallback cycle at {', '.join(sorted(cycles))}"
    return FeatureResolution(feature=feature, reason=reason)


def resolve_features(
    profile: ClientProfile,
    manifests: Iterable[FeatureManifest],
) -> tuple[FeatureResolution, ...]:
    """Разрешить все фичи клиента (порядок — по имени фичи)."""
    catalog = tuple(manifests)
    return tuple(resolve_feature(feature, profile, catalog) for feature in sorted(profile.features))


def fits(profile: ClientProfile, variant: FeatureVariant) -> bool:
    """Годится ли вариант этому клиенту.

    `variant.clients` пуст — вариант для любых клиентов. Если клиент
    объявил свои `variants`, вариант обязан быть в этом списке: клиент
    говорит, что умеет показать, и провайдер не навязывает ему чужое.
    """
    if variant.clients and profile.name not in variant.clients:
        return False
    return not profile.variants or variant.name in profile.variants


def _follow_fallback(
    profile: ClientProfile,
    variant: FeatureVariant,
    index: dict[str, FeatureVariant],
) -> tuple[str | None, bool]:
    """Пройти цепочку fallback'ов; вернуть `(вариант, был_ли_цикл)`."""
    seen = {variant.name}
    current = variant
    for _ in range(MAX_FALLBACK_DEPTH):
        if current.fallback is None:
            return None, False
        if current.fallback in seen:
            return None, True
        seen.add(current.fallback)
        target = index.get(current.fallback)
        if target is None:
            return None, False
        if fits(profile, target):
            return target.name, False
        current = target
    return None, True


__all__ = [
    "MAX_FALLBACK_DEPTH",
    "FeatureResolution",
    "fits",
    "resolve_feature",
    "resolve_features",
]
