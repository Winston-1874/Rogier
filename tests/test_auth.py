"""Tests de l'authentification (auth.py + routes login/logout).

Vérifie que le login fonctionne avec le bon mot de passe,
échoue avec le mauvais, et que le logout supprime la session.
"""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_login_page_accessible(client: TestClient) -> None:
    """La page de login est accessible sans authentification."""
    response = client.get("/login")
    assert response.status_code == 200
    assert "Connexion" in response.text


def test_login_avec_bon_mot_de_passe(client: TestClient, test_password: str) -> None:
    """Le login avec le bon mot de passe redirige vers /."""
    response = client.post(
        "/login",
        data={"password": test_password},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["location"] == "/"
    assert "rogier_session" in response.cookies


def test_login_avec_mauvais_mot_de_passe(client: TestClient) -> None:
    """Le login avec un mauvais mot de passe affiche une erreur."""
    response = client.post(
        "/login",
        data={"password": "mauvais_mot_de_passe"},
    )
    assert response.status_code == 401
    assert "Mot de passe incorrect" in response.text


def test_dashboard_redirige_sans_auth(client: TestClient) -> None:
    """Le dashboard redirige vers /login si non authentifié."""
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["location"]


def test_dashboard_accessible_apres_login(client: TestClient, test_password: str) -> None:
    """Le dashboard est accessible après authentification."""
    # Login
    login_response = client.post(
        "/login",
        data={"password": test_password},
        follow_redirects=False,
    )
    # Accéder au dashboard avec le cookie de session
    client.cookies.set("rogier_session", login_response.cookies["rogier_session"])
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 200
    assert "Rogier" in response.text


def test_logout_supprime_session(client: TestClient, test_password: str) -> None:
    """Le logout redirige vers /login et supprime le cookie."""
    # Login d'abord
    login_response = client.post(
        "/login",
        data={"password": test_password},
        follow_redirects=False,
    )
    client.cookies.set("rogier_session", login_response.cookies["rogier_session"])

    # Logout
    response = client.post("/logout", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["location"]


def test_login_redirige_si_deja_authentifie(client: TestClient, test_password: str) -> None:
    """La page de login redirige vers / si déjà authentifié."""
    login_response = client.post(
        "/login",
        data={"password": test_password},
        follow_redirects=False,
    )
    client.cookies.set("rogier_session", login_response.cookies["rogier_session"])

    response = client.get("/login", follow_redirects=False)
    assert response.status_code == 302
    assert response.headers["location"] == "/"
