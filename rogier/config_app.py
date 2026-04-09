"""Configuration de l'application Rogier.

Lecture et validation des variables d'environnement au démarrage.
L'application refuse de démarrer si une variable obligatoire manque
ou contient une valeur placeholder.
"""

from __future__ import annotations

import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Chaîne sentinelle détectée dans .env.example — interdit en production
_PLACEHOLDER_SECRET = "CHANGE_THIS_BEFORE_RUNNING"


class ConfigError(Exception):
    """Erreur de configuration au démarrage."""


@dataclass(frozen=True)
class AppConfig:
    """Configuration validée de l'application."""

    secret_key: str
    admin_password_hash: str
    data_dir: Path
    max_upload_mb: int
    contact_url: str
    contact_email: str
    session_max_age_days: int
    log_level: str
    dev_mode: bool


def _require_env(name: str, errors: list[str]) -> str:
    """Lire une variable d'environnement obligatoire."""
    value = os.environ.get(name)
    if not value:
        errors.append(f"  - {name} : variable obligatoire absente")
        return ""
    return value


def load_config() -> AppConfig:
    """Charger et valider la configuration depuis les variables d'environnement.

    Lève ConfigError avec un message en français si la configuration est invalide.
    """
    errors: list[str] = []

    secret_key = _require_env("ROGIER_SECRET_KEY", errors)
    admin_hash = _require_env("ROGIER_ADMIN_PASSWORD_HASH", errors)
    data_dir_str = _require_env("ROGIER_DATA_DIR", errors)

    # Vérification des placeholders
    if secret_key and _PLACEHOLDER_SECRET in secret_key:
        errors.append(
            "  - ROGIER_SECRET_KEY : contient encore la valeur placeholder. "
            "Générez une vraie clé avec : openssl rand -hex 32"
        )

    if admin_hash and _PLACEHOLDER_SECRET in admin_hash:
        errors.append(
            "  - ROGIER_ADMIN_PASSWORD_HASH : contient encore la valeur placeholder. "
            "Générez un hash avec : python scripts/create_admin_password_hash.py"
        )

    # Vérification du format bcrypt
    if admin_hash and _PLACEHOLDER_SECRET not in admin_hash and not admin_hash.startswith("$2b$"):
        errors.append(
            "  - ROGIER_ADMIN_PASSWORD_HASH : format invalide. "
            "La valeur doit commencer par '$2b$' (hash bcrypt)."
        )

    if errors:
        msg = "Rogier ne peut pas démarrer. Erreurs de configuration :\n" + "\n".join(errors)
        raise ConfigError(msg)

    data_dir = Path(data_dir_str).resolve()

    # Créer les sous-dossiers de données
    for sub in ("docs", "versions", "raw"):
        (data_dir / sub).mkdir(parents=True, exist_ok=True)

    # Vérifier que le répertoire est accessible en écriture
    if not os.access(data_dir, os.W_OK):
        raise ConfigError(
            f"Rogier ne peut pas démarrer : le répertoire de données "
            f"'{data_dir}' n'est pas accessible en écriture."
        )

    # Variables optionnelles
    max_upload_mb = int(os.environ.get("ROGIER_MAX_UPLOAD_MB", "10"))
    contact_url = os.environ.get("ROGIER_CONTACT_URL", "https://github.com/")
    contact_email = os.environ.get("ROGIER_CONTACT_EMAIL", "noreply@example.com")
    session_max_age_days = int(os.environ.get("ROGIER_SESSION_MAX_AGE_DAYS", "30"))
    log_level = os.environ.get("ROGIER_LOG_LEVEL", "INFO")
    dev_mode = os.environ.get("ROGIER_DEV_MODE", "0") == "1"

    config = AppConfig(
        secret_key=secret_key,
        admin_password_hash=admin_hash,
        data_dir=data_dir,
        max_upload_mb=max_upload_mb,
        contact_url=contact_url,
        contact_email=contact_email,
        session_max_age_days=session_max_age_days,
        log_level=log_level,
        dev_mode=dev_mode,
    )

    logger.info("Rogier démarre avec ROGIER_DATA_DIR=%s", data_dir)
    return config


def exit_on_config_error() -> AppConfig:
    """Charger la config ou quitter avec un message d'erreur en français."""
    try:
        return load_config()
    except ConfigError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)
