"""Fixtures communes pour les tests Rogier."""

from __future__ import annotations

import os
from collections.abc import Generator
from pathlib import Path

import bcrypt
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(autouse=True)
def _env_setup(tmp_path: Path) -> Generator[None, None, None]:
    """Configurer les variables d'environnement pour les tests."""
    test_password = "motdepasse_test_12345"
    hashed = bcrypt.hashpw(test_password.encode("utf-8"), bcrypt.gensalt(rounds=4))

    env_vars = {
        "ROGIER_SECRET_KEY": "a" * 64,
        "ROGIER_ADMIN_PASSWORD_HASH": hashed.decode("utf-8"),
        "ROGIER_DATA_DIR": str(tmp_path / "data"),
        "ROGIER_DEV_MODE": "1",
        "ROGIER_LOG_LEVEL": "DEBUG",
    }

    old_env = {}
    for key, value in env_vars.items():
        old_env[key] = os.environ.get(key)
        os.environ[key] = value

    yield

    for key, old_value in old_env.items():
        if old_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = old_value


@pytest.fixture()
def test_password() -> str:
    """Mot de passe de test en clair."""
    return "motdepasse_test_12345"


@pytest.fixture()
def client() -> TestClient:
    """Client HTTP de test pour l'application FastAPI.

    Recharge le module main à chaque test pour prendre en compte
    les variables d'environnement modifiées.
    """
    import importlib

    import rogier.main

    importlib.reload(rogier.main)
    return TestClient(rogier.main.app)
