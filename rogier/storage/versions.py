"""CRUD des Versions et helpers d'historique.

Une Version capture une configuration complète d'un Document à un
instant donné. Elle est stockée séparément dans
`data/versions/{version_id}.json` et référencée par le Document
via `Document.versions` (liste de VersionRef) et `current_version_id`.

Ce module fournit également les helpers d'auto-génération des labels
listés au §8.3 du SPEC.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

from rogier.errors import StorageError
from rogier.parsing.tree import Document, DocumentConfig, Version, VersionRef
from rogier.storage import paths
from rogier.storage.documents import save_document
from rogier.storage.locks import read_json, write_json

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Labels auto-générés (§8.3 du SPEC)
# ---------------------------------------------------------------------------


def label_import_initial() -> str:
    return "Import initial"


def label_manual_edit_article(article_number: str) -> str:
    return f"Édition manuelle Art. {article_number}"


def label_container_rename(kind_label: str, number: str) -> str:
    return f"Renommage {kind_label} {number}"


def label_chunking_changed() -> str:
    return "Stratégie de chunking modifiée"


def label_validation_changed() -> str:
    return "Invariants sémantiques modifiés"


def label_restore(source_created_at: str) -> str:
    """Label pour un rollback. `source_created_at` est une date ISO."""
    try:
        parsed = datetime.fromisoformat(source_created_at.replace("Z", "+00:00"))
        human = parsed.strftime("%d/%m/%Y")
    except ValueError:
        human = source_created_at
    return f"Restauration de la version du {human}"


# ---------------------------------------------------------------------------
# CRUD bas niveau
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _new_version_id() -> str:
    return f"v-{uuid.uuid4().hex[:12]}"


def save_version(data_dir: Path, version: Version) -> None:
    """Enregistrer une Version sur disque."""
    path = paths.version_path(data_dir, version.id)
    write_json(path, version.to_dict())
    logger.debug("Version %s sauvegardée", version.id)


def load_version(data_dir: Path, version_id: str) -> Version:
    """Charger une Version depuis le disque."""
    path = paths.version_path(data_dir, version_id)
    if not path.exists():
        raise StorageError(f"Version introuvable : {version_id}.")
    try:
        data = read_json(path)
    except ValueError as e:
        raise StorageError(f"La version {version_id} est corrompue : {e}") from e
    return Version.from_dict(data)


def delete_version(data_dir: Path, version_id: str) -> None:
    """Supprimer un fichier de Version."""
    path = paths.version_path(data_dir, version_id)
    if path.exists():
        path.unlink()


# ---------------------------------------------------------------------------
# Helpers d'historique
# ---------------------------------------------------------------------------


def create_initial_version(data_dir: Path, document: Document) -> Version:
    """Créer la Version initiale d'un Document fraîchement importé.

    Cette fonction :
    1. Crée une Version avec une config vide par défaut et le label « Import initial »
    2. L'enregistre dans `data/versions/`
    3. Met à jour `Document.current_version_id` et `Document.versions`
    4. Enregistre le Document mis à jour

    À appeler juste après l'import d'un document (Phase 4+).
    """
    version = Version(
        id=_new_version_id(),
        document_hash=document.hash,
        created_at=_now_iso(),
        label=label_import_initial(),
        note="",
        config=DocumentConfig(),
        parent_id=None,
    )
    save_version(data_dir, version)

    document.current_version_id = version.id
    document.versions = [
        VersionRef(id=version.id, created_at=version.created_at, label=version.label)
    ]
    save_document(data_dir, document)
    return version


def create_new_version(
    data_dir: Path,
    document: Document,
    config: DocumentConfig,
    label: str,
    note: str = "",
) -> Version:
    """Créer une nouvelle Version à partir d'une config modifiée.

    Le `parent_id` est automatiquement pointé vers la Version
    précédemment active. `Document.current_version_id` est mis à jour
    et le Document est ré-enregistré.

    À utiliser pour toute modification de configuration (édition d'un
    nœud, changement de chunking, modification d'invariants).
    """
    version = Version(
        id=_new_version_id(),
        document_hash=document.hash,
        created_at=_now_iso(),
        label=label,
        note=note,
        config=config,
        parent_id=document.current_version_id or None,
    )
    save_version(data_dir, version)

    document.current_version_id = version.id
    document.versions.append(
        VersionRef(id=version.id, created_at=version.created_at, label=version.label)
    )
    save_document(data_dir, document)
    return version


def restore_version(
    data_dir: Path,
    document: Document,
    source_version_id: str,
) -> Version:
    """Créer une nouvelle Version à partir d'une Version antérieure.

    Le rollback ne supprime **jamais** l'historique : il crée une
    nouvelle Version dont la config est celle de la source, avec un
    label « Restauration... » et pour parent la version active au
    moment du rollback.
    """
    source = load_version(data_dir, source_version_id)
    return create_new_version(
        data_dir,
        document,
        config=source.config,
        label=label_restore(source.created_at),
        note="",
    )
