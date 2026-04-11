"""Infrastructure de migration du schéma des Documents stockés.

Chaque fichier JSON de Document porte un champ `schema_version`. À la
lecture, si cette version est inférieure à `CURRENT_SCHEMA_VERSION`,
la fonction `migrate()` applique les migrations en chaîne jusqu'à la
version courante.

En v0.1, `CURRENT_SCHEMA_VERSION = 1` et aucune migration n'est
nécessaire. Mais l'infrastructure est en place dès maintenant pour que
v0.2 puisse migrer proprement depuis v0.1 sans casser les données
existantes.

Convention d'écriture d'une future migration :

    def migrate_v1_to_v2(data: dict) -> dict:
        # Transformer `data` d'un schema v1 vers un schema v2.
        # Retourne un nouveau dict (ne pas muter `data` en place).
        ...

    MIGRATIONS[1] = migrate_v1_to_v2
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from rogier.errors import StorageError

CURRENT_SCHEMA_VERSION = 1

# Dictionnaire des migrations : la clé `n` donne la fonction qui migre
# les données du schéma v`n` vers le schéma v`n+1`.
MIGRATIONS: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {}


def migrate(data: dict[str, Any], from_version: int) -> dict[str, Any]:
    """Migrer un dict Document depuis `from_version` vers CURRENT_SCHEMA_VERSION.

    Lève StorageError si :
    - Une migration intermédiaire n'existe pas
    - `from_version` est supérieur à CURRENT_SCHEMA_VERSION
      (fichier créé par une version plus récente de Rogier)
    """
    if from_version > CURRENT_SCHEMA_VERSION:
        raise StorageError(
            f"Ce document a été créé par une version plus récente de Rogier "
            f"(schema v{from_version}). Version actuelle : v{CURRENT_SCHEMA_VERSION}. "
            f"Mettez Rogier à jour pour l'ouvrir."
        )

    current = from_version
    while current < CURRENT_SCHEMA_VERSION:
        migrator = MIGRATIONS.get(current)
        if migrator is None:
            raise StorageError(
                f"Migration de v{current} vers v{current + 1} non disponible. "
                f"Ce document ne peut pas être ouvert."
            )
        data = migrator(data)
        current += 1

    data["schema_version"] = CURRENT_SCHEMA_VERSION
    return data


def needs_migration(data: dict[str, Any]) -> bool:
    """Indique si un dict Document nécessite une migration."""
    return int(data.get("schema_version", 1)) < CURRENT_SCHEMA_VERSION
