"""Configuration du logging pour Rogier.

Utilise le module standard logging avec un format lisible.
Le niveau est configurable via la variable ROGIER_LOG_LEVEL.
"""

from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configurer le logging de l'application.

    Args:
        level: niveau de log (DEBUG, INFO, WARNING, ERROR).
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger("rogier")
    root.setLevel(numeric_level)
    root.addHandler(handler)

    # Éviter la propagation vers le logger racine (doublons uvicorn)
    root.propagate = False
