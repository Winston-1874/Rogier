"""Tests d'intégration HTTP pour les routes export."""

from __future__ import annotations

from pathlib import Path

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
        start = dash.text.index('content="', dash.text.index("csrf-token")) + 9
        end = dash.text.index('"', start)
        csrf_token = dash.text[start:end]
    return csrf_token


def _upload_csa(client: TestClient, csrf: str) -> str:
    """Upload la fixture CSA sample et retourne le hash du document."""
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
    # /document/{hash}/tree → extraire le hash
    parts = location.split("/")
    doc_hash = parts[2]
    return doc_hash


@pytest.mark.slow
def test_export_page_loads(client: TestClient, test_password: str) -> None:
    """GET /document/{hash}/export renvoie 200 avec le formulaire."""
    csrf = _login(client, test_password)
    doc_hash = _upload_csa(client, csrf)

    response = client.get(f"/document/{doc_hash}/export")
    assert response.status_code == 200
    assert "Stratégie de chunking" in response.text
    assert "Exporter en Markdown" in response.text
    # L'aperçu contient le nombre de chunks
    assert "336" in response.text


@pytest.mark.slow
def test_export_download_md(client: TestClient, test_password: str) -> None:
    """POST /document/{hash}/export télécharge un fichier .md."""
    csrf = _login(client, test_password)
    doc_hash = _upload_csa(client, csrf)

    response = client.post(
        f"/document/{doc_hash}/export",
        data={
            "csrf_token": csrf,
            "strategy": "per_article",
            "hybrid_threshold": "2000",
            "max_chunk_size": "5000",
            "include_breadcrumb": "1",
            "include_node_titles": "1",
        },
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "attachment" in response.headers.get("content-disposition", "")
    assert ".md" in response.headers.get("content-disposition", "")
    # Le contenu est du Markdown avec 336 chunks
    assert response.text.startswith("# ")
    assert response.text.count("**[") == 336


@pytest.mark.slow
def test_export_manifest_available(client: TestClient, test_password: str) -> None:
    """GET /document/{hash}/export/manifest renvoie le manifest après un export."""
    csrf = _login(client, test_password)
    doc_hash = _upload_csa(client, csrf)

    # Avant export → 404
    response = client.get(f"/document/{doc_hash}/export/manifest")
    assert response.status_code == 404

    # Faire un export
    client.post(
        f"/document/{doc_hash}/export",
        data={
            "csrf_token": csrf,
            "strategy": "per_article",
            "hybrid_threshold": "2000",
            "max_chunk_size": "5000",
            "include_breadcrumb": "1",
            "include_node_titles": "1",
        },
    )

    # Après export → 200 avec JSON valide
    response = client.get(f"/document/{doc_hash}/export/manifest")
    assert response.status_code == 200
    manifest = response.json()
    assert manifest["stats"]["total_chunks"] == 336
    assert manifest["strategy"] == "per_article"
    assert manifest["document_hash"] == doc_hash
    # B4 : le manifest contient la validation réelle, pas "pending"
    assert manifest["validation"]["overall"] in ("pass", "fail")
    assert isinstance(manifest["validation"]["structural"], list)
    assert len(manifest["validation"]["structural"]) == 8


@pytest.mark.slow
def test_export_page_shows_validation_report(
    client: TestClient,
    test_password: str,
) -> None:
    """T1 : la page export affiche le rapport de validation structurel."""
    csrf = _login(client, test_password)
    doc_hash = _upload_csa(client, csrf)

    response = client.get(f"/document/{doc_hash}/export")
    assert response.status_code == 200
    assert "Rapport de validation" in response.text
    assert "S001" in response.text
    # Invariants structurels du CSA sample → tous pass (coche verte)
    assert "&#10003;" in response.text


@pytest.mark.slow
def test_save_validation_config_persists(
    client: TestClient,
    test_password: str,
) -> None:
    """T3 : POST /export/validation persiste la ValidationConfig."""
    csrf = _login(client, test_password)
    doc_hash = _upload_csa(client, csrf)

    # Sauvegarder des invariants sémantiques
    response = client.post(
        f"/document/{doc_hash}/export/validation",
        data={
            "csrf_token": csrf,
            "must_contain": "61 500\nCode des sociétés",
            "must_not_contain": "Table des matières",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    # Recharger la page et vérifier que les valeurs sont pré-remplies
    page = client.get(f"/document/{doc_hash}/export")
    assert "61 500" in page.text
    assert "Table des matières" in page.text
    # Les invariants sémantiques apparaissent dans le rapport
    assert "must_contain" in page.text
