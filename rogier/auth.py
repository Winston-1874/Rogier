"""Authentification de Rogier.

Login unique par mot de passe, cookie de session signé via itsdangerous,
vérification bcrypt du hash stocké dans la variable d'environnement.
Le cookie de session contient aussi le token CSRF (synchronizer token).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import bcrypt
from fastapi import Request, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer

from rogier.csrf import generate_csrf_token

if TYPE_CHECKING:
    from rogier.config_app import AppConfig

logger = logging.getLogger(__name__)


def _get_serializer(config: AppConfig) -> URLSafeTimedSerializer:
    """Créer un sérialiseur pour les cookies de session."""
    return URLSafeTimedSerializer(config.secret_key)


def verify_password(plain: str, hashed: str) -> bool:
    """Vérifier un mot de passe contre son hash bcrypt."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_session_cookie(response: Response, config: AppConfig) -> str:
    """Créer un cookie de session signé et l'attacher à la réponse.

    Retourne le token CSRF généré pour cette session.
    """
    csrf_token = generate_csrf_token()
    serializer = _get_serializer(config)
    token = serializer.dumps({"authenticated": True, "csrf_token": csrf_token})
    max_age = config.session_max_age_days * 86400

    response.set_cookie(
        key="rogier_session",
        value=token,
        httponly=True,
        secure=not config.dev_mode,
        samesite="lax",
        max_age=max_age,
    )
    return csrf_token


def clear_session_cookie(response: Response) -> None:
    """Supprimer le cookie de session."""
    response.delete_cookie(key="rogier_session")


def _load_session(request: Request, config: AppConfig) -> dict | None:
    """Charger et vérifier le cookie de session.

    Retourne le payload décodé ou None si absent/invalide.
    """
    cookie = request.cookies.get("rogier_session")
    if not cookie:
        return None

    serializer = _get_serializer(config)
    max_age = config.session_max_age_days * 86400

    try:
        return serializer.loads(cookie, max_age=max_age)
    except BadSignature:
        logger.warning("Cookie de session invalide détecté")
        return None


def get_current_user(request: Request, config: AppConfig) -> bool:
    """Vérifier si l'utilisateur est authentifié via le cookie de session.

    Retourne True si authentifié, False sinon.
    """
    data = _load_session(request, config)
    if data is None:
        return False
    return data.get("authenticated", False)


def get_csrf_token(request: Request, config: AppConfig) -> str | None:
    """Extraire le token CSRF du cookie de session.

    Retourne None si la session est absente ou invalide.
    """
    data = _load_session(request, config)
    if data is None:
        return None
    return data.get("csrf_token")
