"""Exceptions métier de Rogier.

Toutes les exceptions applicatives héritent de RogierError.
Les messages sont en français, destinés à l'utilisateur final.
"""

from __future__ import annotations

import logging
import secrets

logger = logging.getLogger(__name__)


class RogierError(Exception):
    """Erreur applicative Rogier avec message utilisateur en français."""

    def __init__(self, message: str) -> None:
        self.message = message
        self.correlation_id = secrets.token_hex(4)
        logger.error("Erreur [%s] : %s", self.correlation_id, message)
        super().__init__(message)


class JustelFetchError(RogierError):
    """Erreur lors du fetch d'une page Justel."""


class JustelParseError(RogierError):
    """Erreur lors du parsing d'un HTML Justel."""


class StorageError(RogierError):
    """Erreur de stockage (lecture/écriture de fichiers JSON)."""


class AuthError(RogierError):
    """Erreur d'authentification."""
