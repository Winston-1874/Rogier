"""Routes d'authentification : login, logout."""

from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from rogier.auth import (
    clear_session_cookie,
    create_session_cookie,
    get_current_user,
    verify_password,
)
from rogier.csrf import check_csrf_token
from rogier.dependencies import AuthDep, ConfigDep, TemplatesDep

logger = logging.getLogger(__name__)

router = APIRouter()

# --- Rate limiting login (en mémoire, par IP) ---
# Après MAX_ATTEMPTS échecs dans WINDOW_SECONDS, on bloque les tentatives.
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 300  # 5 minutes
_failed_attempts: dict[str, list[float]] = {}


def _is_rate_limited(ip: str) -> bool:
    """Vérifier si une IP a dépassé le seuil de tentatives échouées."""
    now = time.monotonic()
    attempts = _failed_attempts.get(ip, [])
    # Nettoyer les tentatives hors fenêtre
    attempts = [t for t in attempts if now - t < _WINDOW_SECONDS]
    _failed_attempts[ip] = attempts
    return len(attempts) >= _MAX_ATTEMPTS


def _record_failure(ip: str) -> None:
    """Enregistrer une tentative échouée."""
    now = time.monotonic()
    attempts = _failed_attempts.get(ip, [])
    attempts.append(now)
    _failed_attempts[ip] = attempts


def _clear_failures(ip: str) -> None:
    """Effacer les échecs après un login réussi."""
    _failed_attempts.pop(ip, None)


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    config: ConfigDep,
    templates: TemplatesDep,
) -> HTMLResponse:
    """Afficher le formulaire de connexion."""
    if get_current_user(request, config):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": None, "csrf_token": None, "authenticated": False},
    )


@router.post("/login", response_class=HTMLResponse)
async def login_submit(
    request: Request,
    config: ConfigDep,
    templates: TemplatesDep,
    password: str = Form(...),
) -> HTMLResponse:
    """Traiter la soumission du formulaire de connexion."""
    client_ip = request.client.host if request.client else "unknown"

    if _is_rate_limited(client_ip):
        logger.warning("Login bloque par rate limit pour %s", client_ip)
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "error": "Trop de tentatives. Reessayez dans quelques minutes.",
                "csrf_token": None,
                "authenticated": False,
            },
            status_code=429,
        )

    if verify_password(password, config.admin_password_hash):
        _clear_failures(client_ip)
        response = RedirectResponse(url="/", status_code=302)
        create_session_cookie(response, config)
        logger.info("Connexion réussie")
        return response

    _record_failure(client_ip)
    logger.warning("Tentative de connexion échouée depuis %s", client_ip)
    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "error": "Mot de passe incorrect.",
            "csrf_token": None,
            "authenticated": False,
        },
        status_code=401,
    )


@router.post("/logout")
async def logout(
    request: Request,
    config: ConfigDep,
    csrf_token: AuthDep,
    form_csrf: str = Form(None, alias="csrf_token"),
) -> RedirectResponse:
    """Déconnecter l'utilisateur."""
    check_csrf_token(form_csrf, csrf_token)
    response = RedirectResponse(url="/login", status_code=302)
    clear_session_cookie(response)
    logger.info("Déconnexion")
    return response
