"""Tests du fetcher Justel (SPEC §6.5).

Le réseau réel n'est jamais touché : on utilise `httpx.MockTransport`
pour injecter des réponses contrôlées.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from rogier.errors import JustelFetchError
from rogier.fetching import cache as fetch_cache
from rogier.fetching.justel_fetcher import (
    JustelFetchResult,
    build_user_agent,
    fetch_justel_url,
    validate_justel_url,
)
from rogier.fetching.rate_limiter import DomainRateLimiter
from rogier.storage import paths

VALID_URL = (
    "https://www.ejustice.just.fgov.be/cgi_loi/change_lg.pl"
    "?language=fr&la=F&cn=2019032309&table_name=loi"
)
SAMPLE_HTML_TEXT = "<html><body>Société anonyme — éàçù</body></html>"
SAMPLE_HTML_BYTES = SAMPLE_HTML_TEXT.encode("windows-1252")


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "rogier_data"
    paths.ensure_dirs(d)
    return d


@pytest.fixture()
def limiter() -> DomainRateLimiter:
    """Rate limiter à délai nul pour ne pas ralentir les tests."""
    return DomainRateLimiter(min_delay_seconds=0.0)


def _mock_client(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.AsyncClient:
    transport = httpx.MockTransport(handler)
    return httpx.AsyncClient(transport=transport, timeout=5.0)


# ---------------------------------------------------------------------------
# validate_justel_url
# ---------------------------------------------------------------------------


def test_validate_accepts_change_lg_url() -> None:
    validate_justel_url(VALID_URL)  # ne lève pas


def test_validate_accepts_eli_loi_url() -> None:
    validate_justel_url("https://www.ejustice.just.fgov.be/eli/loi/2019/03/23/2019011117/justel")


def test_validate_rejects_other_domain() -> None:
    with pytest.raises(JustelFetchError, match="reconnue comme une page Justel"):
        validate_justel_url("https://example.com/cgi_loi/change_lg.pl")


def test_validate_rejects_unknown_path() -> None:
    with pytest.raises(JustelFetchError, match="reconnue comme une page Justel"):
        validate_justel_url("https://www.ejustice.just.fgov.be/contact.html")


def test_validate_rejects_non_http_scheme() -> None:
    with pytest.raises(JustelFetchError):
        validate_justel_url("ftp://www.ejustice.just.fgov.be/cgi_loi/change_lg.pl")


def test_user_agent_format() -> None:
    ua = build_user_agent("https://github.com/me/rogier", "me@example.be")
    assert ua == "Rogier/0.1 (+https://github.com/me/rogier; me@example.be)"


# ---------------------------------------------------------------------------
# fetch_justel_url
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_decodes_windows1252(
    data_dir: Path, limiter: DomainRateLimiter
) -> None:
    """Le contenu reçu en windows-1252 est correctement décodé en Unicode."""
    captured: dict[str, httpx.Request] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["req"] = request
        return httpx.Response(200, content=SAMPLE_HTML_BYTES, headers={"ETag": 'W/"v1"'})

    async with _mock_client(handler) as client:
        result = await fetch_justel_url(
            VALID_URL,
            data_dir=data_dir,
            contact_url="https://github.com/me/rogier",
            contact_email="me@example.be",
            client=client,
            limiter=limiter,
        )

    assert isinstance(result, JustelFetchResult)
    assert "Société" in result.html
    assert "éàçù" in result.html
    assert result.cache_hit is False
    assert result.url == VALID_URL
    assert len(result.content_hash) == 64

    # User-Agent transmis
    assert captured["req"].headers["user-agent"].startswith("Rogier/0.1 (+")


@pytest.mark.asyncio
async def test_fetch_writes_cache_entry(
    data_dir: Path, limiter: DomainRateLimiter
) -> None:
    """Après un fetch, le cache contient l'entrée et un get() la retrouve."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=SAMPLE_HTML_BYTES, headers={"ETag": "abc"})

    async with _mock_client(handler) as client:
        await fetch_justel_url(
            VALID_URL,
            data_dir=data_dir,
            contact_url="https://x",
            contact_email="x@x",
            client=client,
            limiter=limiter,
        )

    cached = fetch_cache.get(data_dir, VALID_URL)
    assert cached is not None
    assert cached.etag == "abc"
    assert "Société" in cached.html


@pytest.mark.asyncio
async def test_cache_hit_does_not_call_network(
    data_dir: Path, limiter: DomainRateLimiter
) -> None:
    """Un second fetch sur la même URL ne déclenche aucune requête HTTP."""
    call_count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, content=SAMPLE_HTML_BYTES)

    async with _mock_client(handler) as client:
        first = await fetch_justel_url(
            VALID_URL,
            data_dir=data_dir,
            contact_url="https://x",
            contact_email="x@x",
            client=client,
            limiter=limiter,
        )
        second = await fetch_justel_url(
            VALID_URL,
            data_dir=data_dir,
            contact_url="https://x",
            contact_email="x@x",
            client=client,
            limiter=limiter,
        )

    assert call_count == 1
    assert first.cache_hit is False
    assert second.cache_hit is True
    assert second.html == first.html


@pytest.mark.asyncio
async def test_force_refresh_bypasses_cache(
    data_dir: Path, limiter: DomainRateLimiter
) -> None:
    """force_refresh=True déclenche une requête même si le cache est chaud."""
    call_count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, content=SAMPLE_HTML_BYTES)

    async with _mock_client(handler) as client:
        await fetch_justel_url(
            VALID_URL,
            data_dir=data_dir,
            contact_url="https://x",
            contact_email="x@x",
            client=client,
            limiter=limiter,
        )
        result = await fetch_justel_url(
            VALID_URL,
            data_dir=data_dir,
            contact_url="https://x",
            contact_email="x@x",
            force_refresh=True,
            client=client,
            limiter=limiter,
        )

    assert call_count == 2
    assert result.cache_hit is False


@pytest.mark.asyncio
async def test_404_raises_french_error(
    data_dir: Path, limiter: DomainRateLimiter
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(404, content=b"Not Found")

    async with _mock_client(handler) as client:
        with pytest.raises(JustelFetchError, match="introuvable"):
            await fetch_justel_url(
                VALID_URL,
                data_dir=data_dir,
                contact_url="https://x",
                contact_email="x@x",
                client=client,
                limiter=limiter,
            )


@pytest.mark.asyncio
async def test_500_raises_french_error(
    data_dir: Path, limiter: DomainRateLimiter
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(503, content=b"oops")

    async with _mock_client(handler) as client:
        with pytest.raises(JustelFetchError, match="erreur"):
            await fetch_justel_url(
                VALID_URL,
                data_dir=data_dir,
                contact_url="https://x",
                contact_email="x@x",
                client=client,
                limiter=limiter,
            )


@pytest.mark.asyncio
async def test_timeout_raises_french_error(
    data_dir: Path, limiter: DomainRateLimiter
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout")

    async with _mock_client(handler) as client:
        with pytest.raises(JustelFetchError, match="n'a pas répondu dans les temps"):
            await fetch_justel_url(
                VALID_URL,
                data_dir=data_dir,
                contact_url="https://x",
                contact_email="x@x",
                client=client,
                limiter=limiter,
            )


@pytest.mark.asyncio
async def test_invalid_url_raises_before_network(
    data_dir: Path, limiter: DomainRateLimiter
) -> None:
    """Une URL hors périmètre est rejetée sans aucune requête HTTP."""
    call_count = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(200, content=b"")

    async with _mock_client(handler) as client:
        with pytest.raises(JustelFetchError, match="reconnue comme une page Justel"):
            await fetch_justel_url(
                "https://example.com/page",
                data_dir=data_dir,
                contact_url="https://x",
                contact_email="x@x",
                client=client,
                limiter=limiter,
            )

    assert call_count == 0


@pytest.mark.asyncio
async def test_rate_limiter_is_called(
    data_dir: Path,
) -> None:
    """Le rate limiter est invoqué avant chaque requête réseau."""
    limiter = DomainRateLimiter(min_delay_seconds=0.0)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=SAMPLE_HTML_BYTES)

    async with _mock_client(handler) as client:
        await fetch_justel_url(
            VALID_URL,
            data_dir=data_dir,
            contact_url="https://x",
            contact_email="x@x",
            client=client,
            limiter=limiter,
        )

    assert "www.ejustice.just.fgov.be" in limiter._last_request


@pytest.mark.asyncio
async def test_rate_limiter_blocks_second_request_in_window(
    data_dir: Path,
) -> None:
    """Deux fetches successifs (sans cache) sont espacés par le rate limiter."""
    import time

    limiter = DomainRateLimiter(min_delay_seconds=0.15)

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=SAMPLE_HTML_BYTES)

    async with _mock_client(handler) as client:
        await fetch_justel_url(
            VALID_URL,
            data_dir=data_dir,
            contact_url="https://x",
            contact_email="x@x",
            client=client,
            limiter=limiter,
        )

        start = time.monotonic()
        await fetch_justel_url(
            VALID_URL,
            data_dir=data_dir,
            contact_url="https://x",
            contact_email="x@x",
            force_refresh=True,
            client=client,
            limiter=limiter,
        )
        elapsed = time.monotonic() - start

    assert elapsed >= 0.12
