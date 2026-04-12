"""Dépendances FastAPI partagées entre les routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.templating import Jinja2Templates

from rogier.auth import get_csrf_token, get_current_user
from rogier.config_app import AppConfig


def get_config(request: Request) -> AppConfig:
    """Récupérer la configuration depuis l'état de l'application."""
    return request.app.state.config


def get_templates(request: Request) -> Jinja2Templates:
    """Récupérer le moteur de templates depuis l'état de l'application."""
    return request.app.state.templates


ConfigDep = Annotated[AppConfig, Depends(get_config)]
TemplatesDep = Annotated[Jinja2Templates, Depends(get_templates)]


class AuthenticationRequiredError(Exception):
    """Levée quand un utilisateur non authentifié accède à une route protégée."""


def require_auth(request: Request, config: ConfigDep) -> str:
    """Vérifier l'authentification et retourner le token CSRF.

    Lève AuthenticationRequired si l'utilisateur n'est pas authentifié.
    Le token CSRF est retourné pour injection dans les templates.
    """
    if not get_current_user(request, config):
        raise AuthenticationRequiredError
    csrf_token = get_csrf_token(request, config)
    # Fallback pour les sessions créées avant l'ajout du CSRF
    return csrf_token or ""


AuthDep = Annotated[str, Depends(require_auth)]
