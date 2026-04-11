"""Tests du CRUD des Versions et de l'historique (SPEC §8.3, §8.6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rogier.errors import StorageError
from rogier.parsing.tree import (
    ChunkingConfig,
    Document,
    DocumentConfig,
    Node,
    NodeKind,
    ValidationConfig,
)
from rogier.storage import paths
from rogier.storage.documents import document_exists, load_document, save_document
from rogier.storage.versions import (
    create_initial_version,
    create_new_version,
    label_chunking_changed,
    label_import_initial,
    label_manual_edit_article,
    label_restore,
    load_version,
    restore_version,
)


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "rogier_data"
    paths.ensure_dirs(d)
    return d


@pytest.fixture()
def saved_document(data_dir: Path) -> Document:
    """Un Document simple enregistré sur disque."""
    doc = Document(
        hash="a" * 64,
        name="Document de test",
        created_at="2026-04-10T10:00:00Z",
        tree=Node(
            kind=NodeKind.DOCUMENT,
            title="Document de test",
            children=[Node(kind=NodeKind.ARTICLE, number="1", content="Contenu.")],
        ),
    )
    save_document(data_dir, doc)
    return doc


def test_labels_are_french() -> None:
    assert label_import_initial() == "Import initial"
    assert label_manual_edit_article("1:1") == "Édition manuelle Art. 1:1"
    assert label_chunking_changed() == "Stratégie de chunking modifiée"


def test_label_restore_formats_date() -> None:
    assert label_restore("2026-04-09T15:42:00Z") == "Restauration de la version du 09/04/2026"


def test_label_restore_falls_back_on_bad_date() -> None:
    """Si la date est illisible, on garde la chaîne brute."""
    out = label_restore("pas une date")
    assert "Restauration" in out
    assert "pas une date" in out


def test_create_initial_version_updates_document(data_dir: Path, saved_document: Document) -> None:
    version = create_initial_version(data_dir, saved_document)

    # Le fichier de version existe
    assert paths.version_path(data_dir, version.id).exists()

    # Le document a été mis à jour
    reloaded = load_document(data_dir, saved_document.hash)
    assert reloaded.current_version_id == version.id
    assert len(reloaded.versions) == 1
    assert reloaded.versions[0].id == version.id
    assert reloaded.versions[0].label == "Import initial"

    # La version stockée est complète et correcte
    stored = load_version(data_dir, version.id)
    assert stored.document_hash == saved_document.hash
    assert stored.label == "Import initial"
    assert stored.parent_id is None


def test_create_new_version_chains_parent_id(data_dir: Path, saved_document: Document) -> None:
    """Une nouvelle version pointe vers la version active précédente."""
    v1 = create_initial_version(data_dir, saved_document)

    new_config = DocumentConfig(
        chunking=ChunkingConfig(strategy="hybrid", hybrid_threshold=1500),
        validation=ValidationConfig(must_contain=["61 500"]),
    )

    v2 = create_new_version(
        data_dir,
        saved_document,
        config=new_config,
        label=label_chunking_changed(),
    )

    assert v2.parent_id == v1.id
    assert v2.config.chunking.strategy == "hybrid"
    assert v2.config.validation.must_contain == ["61 500"]

    reloaded = load_document(data_dir, saved_document.hash)
    assert reloaded.current_version_id == v2.id
    assert [vr.id for vr in reloaded.versions] == [v1.id, v2.id]


def test_create_new_version_persists_config_roundtrip(
    data_dir: Path, saved_document: Document
) -> None:
    """La DocumentConfig est correctement sérialisée/désérialisée."""
    create_initial_version(data_dir, saved_document)

    config = DocumentConfig(
        chunking=ChunkingConfig(
            strategy="hybrid",
            hybrid_threshold=3000,
            include_node_titles=False,
        ),
        validation=ValidationConfig(
            must_contain=["Code", "société"],
            must_not_contain=["Table des matières"],
        ),
        manual_edits={"tree.children.0.children.0": "Nouveau contenu"},
    )
    v = create_new_version(data_dir, saved_document, config=config, label="Test")

    stored = load_version(data_dir, v.id)
    assert stored.config.chunking.strategy == "hybrid"
    assert stored.config.chunking.hybrid_threshold == 3000
    assert stored.config.chunking.include_node_titles is False
    assert stored.config.validation.must_contain == ["Code", "société"]
    assert stored.config.validation.must_not_contain == ["Table des matières"]
    assert stored.config.manual_edits == {"tree.children.0.children.0": "Nouveau contenu"}


def test_restore_version_creates_new_version_with_source_config(
    data_dir: Path, saved_document: Document
) -> None:
    """Un rollback crée une nouvelle version, n'écrase pas l'ancienne."""
    v1 = create_initial_version(data_dir, saved_document)
    v2 = create_new_version(
        data_dir,
        saved_document,
        config=DocumentConfig(chunking=ChunkingConfig(strategy="hybrid")),
        label=label_chunking_changed(),
    )

    # Rollback vers v1
    v3 = restore_version(data_dir, saved_document, source_version_id=v1.id)

    # v1 et v2 existent toujours
    assert paths.version_path(data_dir, v1.id).exists()
    assert paths.version_path(data_dir, v2.id).exists()
    assert paths.version_path(data_dir, v3.id).exists()

    # v3 a la config de v1 mais le parent est v2 (version active au moment du rollback)
    stored_v3 = load_version(data_dir, v3.id)
    assert stored_v3.parent_id == v2.id
    assert stored_v3.config.chunking.strategy == "per_article"  # config de v1
    assert stored_v3.label.startswith("Restauration de la version du ")

    # Le document pointe maintenant vers v3
    reloaded = load_document(data_dir, saved_document.hash)
    assert reloaded.current_version_id == v3.id
    assert len(reloaded.versions) == 3


def test_load_missing_version_raises(data_dir: Path) -> None:
    with pytest.raises(StorageError, match="introuvable"):
        load_version(data_dir, "v-inexistant")


def test_delete_document_also_deletes_versions(data_dir: Path, saved_document: Document) -> None:
    """Supprimer un document supprime toutes ses versions (cf. §8.6)."""
    from rogier.storage.documents import delete_document

    v1 = create_initial_version(data_dir, saved_document)
    v2 = create_new_version(
        data_dir,
        saved_document,
        config=DocumentConfig(),
        label="Test",
    )

    delete_document(data_dir, saved_document.hash)

    assert not document_exists(data_dir, saved_document.hash)
    assert not paths.version_path(data_dir, v1.id).exists()
    assert not paths.version_path(data_dir, v2.id).exists()
