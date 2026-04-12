"""Point d'entrée de l'application Rogier.

Crée l'application FastAPI, monte les fichiers statiques et les templates,
et enregistre les routers.
"""

from __future__ import annotations

import logging
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from rogier.config_app import AppConfig, exit_on_config_error
from rogier.dependencies import AuthenticationRequiredError
from rogier.errors import RogierError
from rogier.logging_setup import setup_logging
from rogier.routes.auth_routes import router as auth_router
from rogier.routes.dashboard_routes import router as dashboard_router
from rogier.routes.document_routes import router as document_router
from rogier.routes.upload_routes import router as upload_router
from rogier.routes.version_routes import router as version_router

logger = logging.getLogger(__name__)

# Charger .env en développement
load_dotenv()

# Chargement de la configuration (quitte si invalide)
config: AppConfig = exit_on_config_error()

# Configuration du logging
setup_logging(config.log_level)

# Application FastAPI
app = FastAPI(title="Rogier", version="0.1.0", docs_url=None, redoc_url=None)

# État partagé accessible via les dépendances
app.state.config = config

_base_dir = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=_base_dir / "static"), name="static")
app.state.templates = Jinja2Templates(directory=_base_dir / "templates")


# --- Gestionnaires d'erreurs ---


@app.exception_handler(AuthenticationRequiredError)
async def auth_required_handler(
    request: Request,
    exc: AuthenticationRequiredError,
) -> HTMLResponse:
    """Rediriger vers /login si non authentifié."""
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url="/login", status_code=302)


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> HTMLResponse:
    """Afficher les erreurs HTTP (403, 404, etc.) via le template erreur."""
    templates = app.state.templates
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "error_message": str(exc.detail),
            "correlation_id": None,
            "authenticated": True,
            "csrf_token": None,
        },
        status_code=exc.status_code,
    )


@app.exception_handler(RogierError)
async def rogier_error_handler(
    request: Request,
    exc: RogierError,
) -> HTMLResponse:
    """Afficher la page d'erreur pour les erreurs métier."""
    templates = app.state.templates
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "error_message": exc.message,
            "correlation_id": exc.correlation_id,
            "authenticated": True,
            "csrf_token": None,
        },
        status_code=400,
    )


@app.exception_handler(500)
async def internal_error_handler(
    request: Request,
    exc: Exception,
) -> HTMLResponse:
    """Afficher une page d'erreur générique pour les erreurs 500."""
    import secrets as _secrets

    correlation_id = _secrets.token_hex(4)
    logger.exception("Erreur interne [%s]", correlation_id)
    templates = app.state.templates
    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "error_message": "Une erreur inattendue est survenue. Veuillez reessayer.",
            "correlation_id": correlation_id,
            "authenticated": True,
            "csrf_token": None,
        },
        status_code=500,
    )


# --- Enregistrement des routers ---

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(document_router)
app.include_router(upload_router)
app.include_router(version_router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "rogier.main:app",
        host="127.0.0.1",
        port=8000,
        reload=config.dev_mode,
    )
