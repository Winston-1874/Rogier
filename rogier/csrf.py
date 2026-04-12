"""Protection CSRF de Rogier — synchronizer token.

Le token est généré à la connexion, stocké dans le cookie de session,
injecté dans chaque formulaire (champ hidden) et dans ``<meta name="csrf-token">``.
Le serveur vérifie le token sur chaque POST authentifié.
"""

from __future__ import annotations

import secrets

from fastapi import HTTPException


def generate_csrf_token() -> str:
    """Générer un token CSRF aléatoire (32 octets hex)."""
    return secrets.token_hex(32)


def check_csrf_token(submitted: str | None, session_token: str) -> None:
    """Comparer le token soumis (form ou header) au token de session.

    Lève HTTP 403 si le token est absent ou ne correspond pas.
    """
    if not submitted or not secrets.compare_digest(submitted, session_token):
        raise HTTPException(
            status_code=403,
            detail="Requête invalide. Merci de recharger la page.",
        )
