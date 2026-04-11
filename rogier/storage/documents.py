"""CRUD des Documents stockés en JSON.

Un Document est sérialisé dans `data/docs/{hash}.json`. Son HTML brut
est mis en cache dans `data/raw/{hash}.html` (écrit ailleurs, par le
fetcher). Ses Versions sont des fichiers séparés, gérés par
`storage.versions`.

Ce module est la seule porte d'entrée pour lire/écrire les Documents.
Aucun autre module ne doit toucher directement aux fichiers.
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path

from rogier.errors import StorageError
from rogier.parsing.tree import Document
from rogier.storage import paths
from rogier.storage.locks import read_json, write_json
from rogier.storage.migrations import CURRENT_SCHEMA_VERSION, migrate, needs_migration

logger = logging.getLogger(__name__)


def compute_hash(raw_html: bytes) -> str:
    """Calculer le SHA-256 d'un HTML brut (bytes).

    Le hash est calculé sur les bytes, avant tout décodage, pour être
    indépendant de l'encoding. C'est la clé primaire d'un Document.
    """
    return hashlib.sha256(raw_html).hexdigest()


def save_document(data_dir: Path, document: Document) -> None:
    """Enregistrer un Document sur disque.

    Écrase silencieusement le fichier existant — la politique de
    déduplication (§8.5) est appliquée par la couche route avant
    d'appeler cette fonction.
    """
    path = paths.document_path(data_dir, document.hash)
    write_json(path, document.to_dict())
    logger.debug("Document %s sauvegardé (%s)", document.hash[:12], path)


def load_document(data_dir: Path, document_hash: str) -> Document:
    """Charger un Document depuis le disque.

    Applique les migrations de schéma si nécessaire et ré-enregistre
    le fichier migré pour éviter de repayer le coût à chaque lecture.

    Lève StorageError si le document n'existe pas ou est corrompu.
    """
    path = paths.document_path(data_dir, document_hash)
    if not path.exists():
        raise StorageError(f"Document introuvable : {document_hash[:12]}.")

    try:
        data = read_json(path)
    except ValueError as e:
        raise StorageError(f"Le document {document_hash[:12]} est corrompu : {e}") from e

    from_version = int(data.get("schema_version", 1))
    if from_version > CURRENT_SCHEMA_VERSION:
        # Délègue à migrate() le soin de lever une StorageError française.
        migrate(data, from_version)
    if needs_migration(data):
        logger.info(
            "Migration du document %s depuis schema v%d",
            document_hash[:12],
            from_version,
        )
        data = migrate(data, from_version)
        write_json(path, data)

    return Document.from_dict(data)


def document_exists(data_dir: Path, document_hash: str) -> bool:
    """Indique si un Document existe déjà dans la bibliothèque."""
    return paths.document_path(data_dir, document_hash).exists()


def list_documents(data_dir: Path) -> list[Document]:
    """Lister tous les Documents stockés.

    Les fichiers corrompus sont loggés et ignorés, pour ne pas bloquer
    le dashboard à cause d'un seul fichier cassé.
    """
    docs_dir = paths.docs_dir(data_dir)
    if not docs_dir.exists():
        return []

    result: list[Document] = []
    for path in sorted(docs_dir.glob("*.json")):
        document_hash = path.stem
        try:
            result.append(load_document(data_dir, document_hash))
        except StorageError as e:
            logger.warning("Document ignoré (%s) : %s", document_hash[:12], e.message)
    return result


def delete_document(data_dir: Path, document_hash: str) -> None:
    """Supprimer un Document et toutes ses Versions et son HTML brut.

    Supprime dans l'ordre : versions → HTML brut → Document lui-même.
    Si le Document n'existe pas, lève StorageError.
    """
    if not document_exists(data_dir, document_hash):
        raise StorageError(f"Document introuvable : {document_hash[:12]}.")

    document = load_document(data_dir, document_hash)

    # Supprimer les versions associées
    for version_ref in document.versions:
        version_file = paths.version_path(data_dir, version_ref.id)
        if version_file.exists():
            version_file.unlink()

    # Supprimer le HTML brut en cache (s'il existe)
    raw_file = paths.raw_html_path(data_dir, document_hash)
    if raw_file.exists():
        raw_file.unlink()

    # Supprimer le document lui-même
    paths.document_path(data_dir, document_hash).unlink()
    logger.info("Document %s supprimé", document_hash[:12])
