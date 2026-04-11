"""Chemins standards du répertoire de données Rogier.

Tous les accès disque du module `storage` passent par ces fonctions.
Un `data_dir` est injecté explicitement à chaque appel — aucune lecture
d'environnement dans ce module, pour faciliter les tests et isoler les
dépendances.

Structure cible (§8.1 du SPEC) :

    data/
    ├── admin.json
    ├── docs/
    │   └── {hash}.json
    ├── versions/
    │   └── {version_id}.json
    └── raw/
        └── {hash}.html
"""

from __future__ import annotations

from pathlib import Path


def docs_dir(data_dir: Path) -> Path:
    """Répertoire des Documents (un fichier JSON par document)."""
    return data_dir / "docs"


def versions_dir(data_dir: Path) -> Path:
    """Répertoire des Versions (un fichier JSON par version)."""
    return data_dir / "versions"


def raw_dir(data_dir: Path) -> Path:
    """Répertoire du cache HTML brut."""
    return data_dir / "raw"


def document_path(data_dir: Path, document_hash: str) -> Path:
    """Chemin du fichier JSON pour un Document donné."""
    return docs_dir(data_dir) / f"{document_hash}.json"


def version_path(data_dir: Path, version_id: str) -> Path:
    """Chemin du fichier JSON pour une Version donnée."""
    return versions_dir(data_dir) / f"{version_id}.json"


def raw_html_path(data_dir: Path, document_hash: str) -> Path:
    """Chemin du HTML brut d'un Document dans le cache."""
    return raw_dir(data_dir) / f"{document_hash}.html"


def admin_path(data_dir: Path) -> Path:
    """Chemin du fichier admin.json (hash bcrypt uniquement)."""
    return data_dir / "admin.json"


def ensure_dirs(data_dir: Path) -> None:
    """Créer les sous-répertoires de données s'ils n'existent pas."""
    for sub in (docs_dir(data_dir), versions_dir(data_dir), raw_dir(data_dir)):
        sub.mkdir(parents=True, exist_ok=True)
