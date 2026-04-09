"""Tests de la configuration de l'application (config_app.py).

Vérifie que l'application refuse de démarrer si les variables
d'environnement obligatoires sont absentes ou invalides.
"""

from __future__ import annotations

import os

import pytest

from rogier.config_app import ConfigError, load_config


def test_demarre_avec_config_valide() -> None:
    """La config se charge correctement avec toutes les variables présentes."""
    config = load_config()
    assert config.data_dir.exists()
    assert (config.data_dir / "docs").exists()
    assert (config.data_dir / "versions").exists()
    assert (config.data_dir / "raw").exists()


def test_echoue_sans_secret_key() -> None:
    """Le démarrage échoue si ROGIER_SECRET_KEY est absente."""
    os.environ.pop("ROGIER_SECRET_KEY", None)
    with pytest.raises(ConfigError, match="ROGIER_SECRET_KEY"):
        load_config()


def test_echoue_sans_admin_hash() -> None:
    """Le démarrage échoue si ROGIER_ADMIN_PASSWORD_HASH est absente."""
    os.environ.pop("ROGIER_ADMIN_PASSWORD_HASH", None)
    with pytest.raises(ConfigError, match="ROGIER_ADMIN_PASSWORD_HASH"):
        load_config()


def test_echoue_sans_data_dir() -> None:
    """Le démarrage échoue si ROGIER_DATA_DIR est absente."""
    os.environ.pop("ROGIER_DATA_DIR", None)
    with pytest.raises(ConfigError, match="ROGIER_DATA_DIR"):
        load_config()


def test_echoue_avec_placeholder_secret_key() -> None:
    """Le démarrage échoue si ROGIER_SECRET_KEY contient le placeholder."""
    os.environ["ROGIER_SECRET_KEY"] = "CHANGE_THIS_BEFORE_RUNNING_openssl_rand_hex_32"
    with pytest.raises(ConfigError, match="placeholder"):
        load_config()


def test_echoue_avec_placeholder_admin_hash() -> None:
    """Le démarrage échoue si ROGIER_ADMIN_PASSWORD_HASH contient le placeholder."""
    os.environ["ROGIER_ADMIN_PASSWORD_HASH"] = "CHANGE_THIS_BEFORE_RUNNING"
    with pytest.raises(ConfigError, match="placeholder"):
        load_config()


def test_echoue_avec_hash_format_invalide() -> None:
    """Le démarrage échoue si le hash n'est pas au format bcrypt."""
    os.environ["ROGIER_ADMIN_PASSWORD_HASH"] = "pas_un_hash_bcrypt"
    with pytest.raises(ConfigError, match="\\$2b\\$"):
        load_config()


def test_variables_optionnelles_defaut() -> None:
    """Les variables optionnelles ont des valeurs par défaut correctes."""
    config = load_config()
    assert config.max_upload_mb == 10
    assert config.session_max_age_days == 30
    assert config.log_level == "DEBUG"  # Fixé dans conftest
    assert config.dev_mode is True  # Fixé dans conftest
