"""Authentification de Rogier.

Login unique par mot de passe, cookie de session signé via itsdangerous,
vérification bcrypt du hash stocké dans la variable d'environnement.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import bcrypt
from fastapi import Request, Response
from itsdangerous import BadSignature, URLSafeTimedSerializer

if TYPE_CHECKING:
    from rogier.config_app import AppConfig

logger = logging.getLogger(__name__)


def _get_serializer(config: AppConfig) -> URLSafeTimedSerializer:
    """Créer un sérialiseur pour les cookies de session."""
    return URLSafeTimedSerializer(config.secret_key)


def verify_password(plain: str, hashed: str) -> bool:
    """Vérifier un mot de passe contre son hash bcrypt."""
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_session_cookie(response: Response, config: AppConfig) -> None:
    """Créer un cookie de session signé et l'attacher à la réponse."""
    serializer = _get_serializer(config)
    token = serializer.dumps({"authenticated": True})
    max_age = config.session_max_age_days * 86400

    response.set_cookie(
        key="rogier_session",
        value=token,
        httponly=True,
        secure=not config.dev_mode,
        samesite="lax",
        max_age=max_age,
    )


def clear_session_cookie(response: Response) -> None:
    """Supprimer le cookie de session."""
    response.delete_cookie(key="rogier_session")


def get_current_user(request: Request, config: AppConfig) -> bool:
    """Vérifier si l'utilisateur est authentifié via le cookie de session.

    Retourne True si authentifié, False sinon.
    """
    cookie = request.cookies.get("rogier_session")
    if not cookie:
        return False

    serializer = _get_serializer(config)
    max_age = config.session_max_age_days * 86400

    try:
        data = serializer.loads(cookie, max_age=max_age)
        return data.get("authenticated", False)
    except BadSignature:
        logger.warning("Cookie de session invalide détecté")
        return False
