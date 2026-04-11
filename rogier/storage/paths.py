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
    ├── raw/
    │   └── {hash}.html             # raw HTML d'un Document (clé = sha256 du contenu)
    └── fetch_cache/
        ├── {sha256_url}.html       # cache du fetcher Justel (clé = sha256 de l'URL)
        └── {sha256_url}.json       # sidecar : ETag, fetched_at, content_hash

Le séparation `raw/` vs `fetch_cache/` est délibérée : le premier est la
propriété de `storage.documents` (durée de vie liée au Document), le second
celle de `fetching.cache` (TTL 24h, indépendant des Documents).
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
    """Répertoire du HTML brut associé à un Document (clé = sha256 du contenu)."""
    return data_dir / "raw"


def fetch_cache_dir(data_dir: Path) -> Path:
    """Répertoire du cache du fetcher Justel (clé = sha256 de l'URL).

    Distinct de `raw/` : ces fichiers expirent après 24h et ne sont pas liés
    à un Document. Cf. §6.2.4 du SPEC.
    """
    return data_dir / "fetch_cache"


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
    for sub in (
        docs_dir(data_dir),
        versions_dir(data_dir),
        raw_dir(data_dir),
        fetch_cache_dir(data_dir),
    ):
        sub.mkdir(parents=True, exist_ok=True)
