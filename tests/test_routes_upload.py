"""Tests des routes d'upload (fichier local et URL Justel).

Vérifie le formulaire, la validation, le parsing, la déduplication,
et les erreurs.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _login(client: TestClient, password: str) -> str:
    """Helper : login et retour du csrf_token."""
    response = client.post(
        "/login",
        data={"password": password},
        follow_redirects=False,
    )
    client.cookies.set("rogier_session", response.cookies["rogier_session"])

    dash = client.get("/")
    csrf_token = ""
    if 'name="csrf-token"' in dash.text:
        start = dash.text.index('content="', dash.text.index('csrf-token')) + 9
        end = dash.text.index('"', start)
        csrf_token = dash.text[start:end]
    return csrf_token


# --- Upload fichier ---


@pytest.mark.slow
def test_upload_fichier_valide(client: TestClient, test_password: str) -> None:
    """Upload d'un fichier HTML Justel valide crée un document."""
    csrf = _login(client, test_password)
    html_path = FIXTURES_DIR / "csa_sample.html"
    html_bytes = html_path.read_bytes()

    response = client.post(
        "/upload",
        data={"csrf_token": csrf, "upload_mode": "file", "justel_url": ""},
        files={"html_file": ("csa_sample.html", html_bytes, "text/html")},
        follow_redirects=False,
    )
    assert response.status_code == 302
    location = response.headers["location"]
    assert "/document/" in location
    assert "/tree" in location


def test_upload_fichier_vide(client: TestClient, test_password: str) -> None:
    """Upload sans fichier affiche une erreur."""
    csrf = _login(client, test_password)

    response = client.post(
        "/upload",
        data={"csrf_token": csrf, "upload_mode": "file", "justel_url": ""},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "selectionner un fichier" in response.text


def test_upload_fichier_trop_gros(client: TestClient, test_password: str) -> None:
    """Upload d'un fichier trop gros affiche une erreur."""
    csrf = _login(client, test_password)
    # Générer un fichier HTML factice contenant les marqueurs mais trop gros
    content = (
        '<html><body><a href="change_lg.pl">link</a>'
        '<span class="list-title-2">t</span>'
        + "x" * (11 * 1024 * 1024)
        + "</body></html>"
    )

    response = client.post(
        "/upload",
        data={"csrf_token": csrf, "upload_mode": "file", "justel_url": ""},
        files={"html_file": ("big.html", content.encode(), "text/html")},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "taille maximale" in response.text


def test_upload_fichier_non_justel(client: TestClient, test_password: str) -> None:
    """Upload d'un fichier HTML non-Justel affiche une erreur."""
    csrf = _login(client, test_password)
    content = b"<html><body><p>Pas du Justel</p></body></html>"

    response = client.post(
        "/upload",
        data={"csrf_token": csrf, "upload_mode": "file", "justel_url": ""},
        files={"html_file": ("fake.html", content, "text/html")},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "Justel valide" in response.text


# --- Upload URL ---


def test_upload_url_vide(client: TestClient, test_password: str) -> None:
    """Upload URL sans saisie affiche une erreur."""
    csrf = _login(client, test_password)

    response = client.post(
        "/upload",
        data={"csrf_token": csrf, "upload_mode": "url", "justel_url": ""},
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "saisir une URL" in response.text


def test_upload_url_invalide(client: TestClient, test_password: str) -> None:
    """Upload avec une URL non-Justel affiche une erreur."""
    csrf = _login(client, test_password)

    response = client.post(
        "/upload",
        data={
            "csrf_token": csrf,
            "upload_mode": "url",
            "justel_url": "https://example.com/not-justel",
        },
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "Justel valide" in response.text


@pytest.mark.slow
def test_upload_url_valide_mock(client: TestClient, test_password: str) -> None:
    """Upload via URL Justel (mockée) crée un document."""
    csrf = _login(client, test_password)
    html_path = FIXTURES_DIR / "csa_sample.html"
    html_content = html_path.read_text(encoding="utf-8", errors="replace")

    from rogier.fetching.justel_fetcher import JustelFetchResult

    mock_result = JustelFetchResult(
        url="https://www.ejustice.just.fgov.be/cgi_loi/change_lg.pl?language=fr&la=F&cn=2019032309&table_name=loi",
        html=html_content,
        cache_hit=False,
        fetched_at="2026-04-12T10:00:00+00:00",
        content_hash="abcd1234",
    )

    with patch(
        "rogier.routes.upload_routes.fetch_justel_url",
        new_callable=AsyncMock,
        return_value=mock_result,
    ):
        response = client.post(
            "/upload",
            data={
                "csrf_token": csrf,
                "upload_mode": "url",
                "justel_url": "https://www.ejustice.just.fgov.be/cgi_loi/change_lg.pl?language=fr&la=F&cn=2019032309&table_name=loi",
            },
            follow_redirects=False,
        )
    assert response.status_code == 302
    location = response.headers["location"]
    assert "/document/" in location
    assert "/tree" in location


# --- Déduplication ---


@pytest.mark.slow
def test_upload_deduplication(client: TestClient, test_password: str) -> None:
    """Upload du même contenu deux fois redirige vers le document existant."""
    csrf = _login(client, test_password)
    html_path = FIXTURES_DIR / "csa_sample.html"
    html_bytes = html_path.read_bytes()

    # Premier upload
    resp1 = client.post(
        "/upload",
        data={"csrf_token": csrf, "upload_mode": "file", "justel_url": ""},
        files={"html_file": ("csa.html", html_bytes, "text/html")},
        follow_redirects=False,
    )
    assert resp1.status_code == 302

    # Deuxième upload du même contenu
    resp2 = client.post(
        "/upload",
        data={"csrf_token": csrf, "upload_mode": "file", "justel_url": ""},
        files={"html_file": ("csa.html", html_bytes, "text/html")},
        follow_redirects=False,
    )
    assert resp2.status_code == 302
    # Même URL (même hash, mais sans ?warnings pour le second)
    assert "/document/" in resp2.headers["location"]


# --- Dashboard après upload ---


@pytest.mark.slow
def test_dashboard_apres_upload(client: TestClient, test_password: str) -> None:
    """Le dashboard affiche le document après upload."""
    csrf = _login(client, test_password)
    html_path = FIXTURES_DIR / "csa_sample.html"
    html_bytes = html_path.read_bytes()

    client.post(
        "/upload",
        data={"csrf_token": csrf, "upload_mode": "file", "justel_url": ""},
        files={"html_file": ("csa.html", html_bytes, "text/html")},
        follow_redirects=False,
    )

    response = client.get("/")
    assert response.status_code == 200
    assert "Aucun document" not in response.text
    # Le tableau doit contenir au moins une ligne
    assert "<tbody>" in response.text
