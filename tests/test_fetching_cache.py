"""Tests du cache local du fetcher Justel (SPEC §6.2.4)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from rogier.fetching import cache as fetch_cache
from rogier.fetching.cache import CACHE_TTL, CachedEntry, get, put, url_key
from rogier.storage import paths


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "rogier_data"
    paths.ensure_dirs(d)
    return d


URL = "https://www.ejustice.just.fgov.be/cgi_loi/change_lg.pl?language=fr&la=F&cn=2019032309&table_name=loi"
HTML = "<html><body>contenu Justel avec accents : éàçùù</body></html>"


def test_url_key_is_stable_and_64_hex() -> None:
    k = url_key(URL)
    assert len(k) == 64
    assert all(c in "0123456789abcdef" for c in k)
    assert url_key(URL) == k  # déterministe


def test_url_key_differs_for_different_urls() -> None:
    assert url_key("https://a") != url_key("https://b")


def test_get_missing_returns_none(data_dir: Path) -> None:
    assert get(data_dir, URL) is None


def test_put_then_get_roundtrip(data_dir: Path) -> None:
    entry = put(data_dir, URL, HTML, etag='W/"abc"')
    assert isinstance(entry, CachedEntry)
    assert entry.url == URL
    assert entry.html == HTML
    assert entry.etag == 'W/"abc"'
    assert len(entry.content_hash) == 64

    loaded = get(data_dir, URL)
    assert loaded is not None
    assert loaded.html == HTML
    assert loaded.etag == 'W/"abc"'
    assert loaded.content_hash == entry.content_hash
    assert loaded.url == URL


def test_put_writes_html_and_sidecar_files(data_dir: Path) -> None:
    put(data_dir, URL, HTML)
    cache_dir = paths.fetch_cache_dir(data_dir)
    # On ignore les lockfiles `.{name}.lock` laissés par locks.locked_write.
    real_files = sorted(p.name for p in cache_dir.iterdir() if not p.name.startswith("."))
    assert len(real_files) == 2
    assert any(f.endswith(".html") for f in real_files)
    assert any(f.endswith(".json") for f in real_files)
    # Le HTML est stocké en UTF-8 (les caractères accentués sont relus correctement)
    html_files = [p for p in cache_dir.iterdir() if p.suffix == ".html"]
    assert "éàçùù" in html_files[0].read_text(encoding="utf-8")


def test_get_returns_none_when_expired(data_dir: Path) -> None:
    """Au-delà de CACHE_TTL, l'entrée est considérée expirée."""
    put(data_dir, URL, HTML)

    future = datetime.now(UTC) + CACHE_TTL + timedelta(minutes=1)
    assert get(data_dir, URL, now=future) is None


def test_get_returns_entry_just_before_expiry(data_dir: Path) -> None:
    """Une entrée juste avant la limite reste valide."""
    put(data_dir, URL, HTML)

    almost = datetime.now(UTC) + CACHE_TTL - timedelta(minutes=5)
    assert get(data_dir, URL, now=almost) is not None


def test_get_returns_none_if_sidecar_missing(data_dir: Path) -> None:
    """Si seul le HTML existe (interruption entre put HTML / put sidecar), entrée invalide."""
    put(data_dir, URL, HTML)
    cache_dir = paths.fetch_cache_dir(data_dir)
    for p in cache_dir.iterdir():
        if p.suffix == ".json":
            p.unlink()
    assert get(data_dir, URL) is None


def test_get_returns_none_if_sidecar_corrupt(data_dir: Path) -> None:
    """Sidecar corrompu → entrée ignorée, pas de crash."""
    put(data_dir, URL, HTML)
    cache_dir = paths.fetch_cache_dir(data_dir)
    sidecar = next(p for p in cache_dir.iterdir() if p.suffix == ".json")
    sidecar.write_text("{ pas du json", encoding="utf-8")
    assert get(data_dir, URL) is None


def test_put_overwrites_existing_entry(data_dir: Path) -> None:
    put(data_dir, URL, "<html>v1</html>")
    put(data_dir, URL, "<html>v2</html>", etag="new")

    loaded = get(data_dir, URL)
    assert loaded is not None
    assert loaded.html == "<html>v2</html>"
    assert loaded.etag == "new"


def test_clear_removes_all_entries(data_dir: Path) -> None:
    put(data_dir, "https://www.ejustice.just.fgov.be/a", HTML)
    put(data_dir, "https://www.ejustice.just.fgov.be/b", HTML)
    removed = fetch_cache.clear(data_dir)
    assert removed == 2
    assert get(data_dir, "https://www.ejustice.just.fgov.be/a") is None
