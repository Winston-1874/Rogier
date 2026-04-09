"""Point d'entrée de l'application Rogier.

Crée l'application FastAPI, monte les fichiers statiques et les templates,
et configure les routes d'authentification et le dashboard.
"""

from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from rogier.auth import (
    clear_session_cookie,
    create_session_cookie,
    get_current_user,
    verify_password,
)
from rogier.config_app import AppConfig, exit_on_config_error
from rogier.logging_setup import setup_logging

logger = logging.getLogger(__name__)

# Charger .env en développement
load_dotenv()

# Chargement de la configuration (quitte si invalide)
config: AppConfig = exit_on_config_error()

# Configuration du logging
setup_logging(config.log_level)

# Application FastAPI
app = FastAPI(title="Rogier", version="0.1.0", docs_url=None, redoc_url=None)

# Montage des fichiers statiques et templates
_base_dir = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=_base_dir / "static"), name="static")
templates = Jinja2Templates(directory=_base_dir / "templates")


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request) -> HTMLResponse:
    """Afficher le formulaire de connexion."""
    if get_current_user(request, config):
        return RedirectResponse(url="/", status_code=302)
    return templates.TemplateResponse(
        request,
        "login.html",
        {"error": None, "csrf_token": None, "authenticated": False},
    )


@app.post("/login", response_class=HTMLResponse)
async def login_submit(request: Request, password: str = Form(...)) -> HTMLResponse:
    """Traiter la soumission du formulaire de connexion."""
    if verify_password(password, config.admin_password_hash):
        response = RedirectResponse(url="/", status_code=302)
        create_session_cookie(response, config)
        logger.info("Connexion réussie")
        return response

    logger.warning("Tentative de connexion échouée")
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


@app.post("/logout")
async def logout() -> RedirectResponse:
    """Déconnecter l'utilisateur."""
    response = RedirectResponse(url="/login", status_code=302)
    clear_session_cookie(response)
    logger.info("Déconnexion")
    return response


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request) -> HTMLResponse:
    """Page d'accueil — redirige vers /login si non authentifié."""
    if not get_current_user(request, config):
        return RedirectResponse(url="/login", status_code=302)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {"csrf_token": None, "authenticated": True},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "rogier.main:app",
        host="127.0.0.1",
        port=8000,
        reload=config.dev_mode,
    )
