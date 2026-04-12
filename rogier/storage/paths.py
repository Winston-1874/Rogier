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

import re
from pathlib import Path

_RE_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_RE_VERSION_ID = re.compile(r"^v-[0-9a-f]{12,}$")


def _validate_sha256(value: str, label: str) -> None:
    """Valider qu'une chaîne est un hash SHA-256 hexadécimal."""
    if not _RE_SHA256.fullmatch(value):
        raise ValueError(f"{label} invalide (attendu : 64 caractères hex) : {value!r}")


def _validate_version_id(value: str) -> None:
    """Valider qu'un version_id est au format v-<hex> (≥12 chars hex)."""
    if not _RE_VERSION_ID.fullmatch(value):
        raise ValueError(f"version_id invalide (attendu : v-<≥12 chars hex>) : {value!r}")


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
    _validate_sha256(document_hash, "document_hash")
    return docs_dir(data_dir) / f"{document_hash}.json"


def version_path(data_dir: Path, version_id: str) -> Path:
    """Chemin du fichier JSON pour une Version donnée."""
    _validate_version_id(version_id)
    return versions_dir(data_dir) / f"{version_id}.json"


def raw_html_path(data_dir: Path, document_hash: str) -> Path:
    """Chemin du HTML brut d'un Document dans le cache."""
    _validate_sha256(document_hash, "document_hash")
    return raw_dir(data_dir) / f"{document_hash}.html"


def admin_path(data_dir: Path) -> Path:
    """Chemin du fichier admin.json (hash bcrypt uniquement)."""
    return data_dir / "admin.json"


def ui_dir(data_dir: Path) -> Path:
    """Répertoire des préférences UI par document."""
    return data_dir / "ui"


def dismissed_warnings_path(data_dir: Path, document_hash: str) -> Path:
    """Chemin du fichier de warnings ignorés pour un Document."""
    _validate_sha256(document_hash, "document_hash")
    return ui_dir(data_dir) / f"{document_hash}_dismissed.json"


def exports_dir(data_dir: Path, document_hash: str) -> Path:
    """Répertoire des exports d'un Document (manifest JSON, etc.)."""
    _validate_sha256(document_hash, "document_hash")
    return data_dir / "exports" / document_hash


def ensure_dirs(data_dir: Path) -> None:
    """Créer les sous-répertoires de données s'ils n'existent pas."""
    for sub in (
        docs_dir(data_dir),
        versions_dir(data_dir),
        raw_dir(data_dir),
        fetch_cache_dir(data_dir),
        ui_dir(data_dir),
        data_dir / "exports",
    ):
        sub.mkdir(parents=True, exist_ok=True)
