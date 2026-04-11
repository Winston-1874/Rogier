"""Tests du rate limiter par domaine (SPEC §6.2.1, §6.5)."""

from __future__ import annotations

import asyncio
import time

import pytest

from rogier.fetching.rate_limiter import (
    MIN_DELAY_SECONDS,
    DomainRateLimiter,
    domain_of,
)


def test_min_delay_is_5_seconds() -> None:
    """Le délai par défaut respecte la contrainte du SPEC §6.2.1."""
    assert MIN_DELAY_SECONDS == 5.0


def test_domain_of_extracts_netloc() -> None:
    assert domain_of("https://www.ejustice.just.fgov.be/cgi_loi/...") == "www.ejustice.just.fgov.be"
    assert domain_of("http://Example.COM/path") == "example.com"


@pytest.mark.asyncio
async def test_first_request_does_not_wait() -> None:
    """La toute première requête vers un domaine ne déclenche aucune attente."""
    limiter = DomainRateLimiter(min_delay_seconds=0.1)
    waited = await limiter.wait_for("a.example")
    assert waited == 0.0


@pytest.mark.asyncio
async def test_second_request_in_window_waits() -> None:
    """Une seconde requête dans la fenêtre est effectivement bloquée."""
    limiter = DomainRateLimiter(min_delay_seconds=0.2)
    await limiter.wait_for("a.example")

    start = time.monotonic()
    waited = await limiter.wait_for("a.example")
    elapsed = time.monotonic() - start

    assert waited > 0.0
    # Au moins ~80% du délai pour absorber le jitter de la boucle.
    assert elapsed >= 0.16


@pytest.mark.asyncio
async def test_different_domains_are_independent() -> None:
    """Deux requêtes vers des domaines différents ne se bloquent pas mutuellement."""
    limiter = DomainRateLimiter(min_delay_seconds=0.5)
    await limiter.wait_for("a.example")

    start = time.monotonic()
    waited = await limiter.wait_for("b.example")
    elapsed = time.monotonic() - start

    assert waited == 0.0
    assert elapsed < 0.05


@pytest.mark.asyncio
async def test_request_after_delay_does_not_wait() -> None:
    """Si on attend assez, la requête suivante passe immédiatement."""
    limiter = DomainRateLimiter(min_delay_seconds=0.1)
    await limiter.wait_for("a.example")
    await asyncio.sleep(0.12)

    waited = await limiter.wait_for("a.example")
    assert waited == 0.0


@pytest.mark.asyncio
async def test_concurrent_requests_are_serialized() -> None:
    """Trois requêtes concurrentes sur le même domaine s'enchaînent à intervalles réguliers."""
    limiter = DomainRateLimiter(min_delay_seconds=0.1)

    start = time.monotonic()
    await asyncio.gather(
        limiter.wait_for("a.example"),
        limiter.wait_for("a.example"),
        limiter.wait_for("a.example"),
    )
    elapsed = time.monotonic() - start

    # 1ʳᵉ immédiate, 2ᵉ après ~0.1s, 3ᵉ après ~0.2s
    assert elapsed >= 0.18


def test_reset_clears_state() -> None:
    """reset() vide l'historique."""
    limiter = DomainRateLimiter()
    limiter._last_request["x"] = 12345.0
    limiter.reset()
    assert limiter._last_request == {}
