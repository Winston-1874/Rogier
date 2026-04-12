"""Tests CSRF et protection des routes authentifiées.

Vérifie que les routes POST exigent un token CSRF valide,
que les routes protégées redirigent vers /login, et que le
gestionnaire d'erreurs global fonctionne.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


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


# --- CSRF ---


def test_csrf_absent_retourne_403(client: TestClient, test_password: str) -> None:
    """POST sans token CSRF retourne 403."""
    _login(client, test_password)
    response = client.post("/logout", data={}, follow_redirects=False)
    assert response.status_code == 403


def test_csrf_invalide_retourne_403(client: TestClient, test_password: str) -> None:
    """POST avec un token CSRF bidon retourne 403."""
    _login(client, test_password)
    response = client.post(
        "/logout",
        data={"csrf_token": "token_bidon"},
        follow_redirects=False,
    )
    assert response.status_code == 403


def test_csrf_valide_passe(client: TestClient, test_password: str) -> None:
    """POST avec le bon token CSRF réussit."""
    csrf = _login(client, test_password)
    response = client.post(
        "/logout",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert response.status_code == 302


# --- Redirect si non authentifié ---


def test_dashboard_redirige_sans_auth(client: TestClient) -> None:
    """GET / redirige vers /login sans session."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["location"]


def test_upload_redirige_sans_auth(client: TestClient) -> None:
    """GET /upload redirige vers /login sans session."""
    response = client.get("/upload", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["location"]


# --- Accès authentifié ---


def test_upload_accessible_apres_login(client: TestClient, test_password: str) -> None:
    """GET /upload est accessible après login."""
    _login(client, test_password)
    response = client.get("/upload")
    assert response.status_code == 200
    assert "Importer un document" in response.text


def test_dashboard_affiche_message_vide(client: TestClient, test_password: str) -> None:
    """Le dashboard sans documents affiche un message d'accueil."""
    _login(client, test_password)
    response = client.get("/")
    assert response.status_code == 200
    assert "Aucun document" in response.text
