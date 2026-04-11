"""Tests du CRUD des Documents (SPEC §8.6)."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from rogier.errors import StorageError
from rogier.parsing.tree import Document, Node, NodeKind
from rogier.storage import paths
from rogier.storage.documents import (
    compute_hash,
    delete_document,
    document_exists,
    list_documents,
    load_document,
    save_document,
)


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    """Répertoire de données isolé pour chaque test."""
    d = tmp_path / "rogier_data"
    paths.ensure_dirs(d)
    return d


def _sample_document(name: str = "Code de test") -> Document:
    """Construire un Document d'exemple avec un petit arbre."""
    tree = Node(
        kind=NodeKind.DOCUMENT,
        title=name,
        children=[
            Node(
                kind=NodeKind.LIVRE,
                number="1er",
                title="Dispositions générales",
                children=[
                    Node(
                        kind=NodeKind.ARTICLE,
                        number="1:1",
                        content="Une société est constituée par un acte juridique.",
                    ),
                    Node(
                        kind=NodeKind.ARTICLE,
                        number="1:2",
                        content="Une association est constituée par un acte juridique.",
                    ),
                ],
            ),
        ],
    )
    return Document(
        hash=compute_hash(name.encode("utf-8")),
        name=name,
        source_url="https://www.ejustice.just.fgov.be/cgi_loi/change_lg.pl?fake",
        created_at="2026-04-10T10:00:00Z",
        tree=tree,
    )


def test_compute_hash_is_deterministic() -> None:
    """Le hash d'un même HTML est stable et reproductible."""
    html = b"<html>contenu Justel</html>"
    assert compute_hash(html) == compute_hash(html)
    assert len(compute_hash(html)) == 64  # SHA-256 en hex


def test_compute_hash_differs_on_different_content() -> None:
    assert compute_hash(b"a") != compute_hash(b"b")


def test_save_and_load_document_roundtrip(data_dir: Path) -> None:
    """Un Document sauvé puis relu doit être identique structurellement."""
    doc = _sample_document()
    save_document(data_dir, doc)

    loaded = load_document(data_dir, doc.hash)

    assert loaded.hash == doc.hash
    assert loaded.name == doc.name
    assert loaded.source_url == doc.source_url
    assert loaded.tree.kind == NodeKind.DOCUMENT
    assert len(loaded.tree.children) == 1
    livre = loaded.tree.children[0]
    assert livre.kind == NodeKind.LIVRE
    assert livre.number == "1er"
    assert len(livre.children) == 2
    assert livre.children[0].kind == NodeKind.ARTICLE
    assert livre.children[0].number == "1:1"
    assert "société" in livre.children[0].content


def test_document_json_is_readable(data_dir: Path) -> None:
    """Le JSON sur disque est lisible par un json.load standard."""
    doc = _sample_document()
    save_document(data_dir, doc)

    path = paths.document_path(data_dir, doc.hash)
    raw = json.loads(path.read_text(encoding="utf-8"))

    assert raw["hash"] == doc.hash
    assert raw["schema_version"] == 1
    assert raw["tree"]["kind"] == "DOCUMENT"
    assert raw["family"] == "justel_html"


def test_load_missing_document_raises(data_dir: Path) -> None:
    with pytest.raises(StorageError, match="introuvable"):
        load_document(data_dir, "deadbeef" * 8)


def test_load_corrupt_document_raises(data_dir: Path) -> None:
    """Un fichier JSON corrompu produit une erreur claire en français."""
    doc_hash = "a" * 64
    path = paths.document_path(data_dir, doc_hash)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ pas du json", encoding="utf-8")

    with pytest.raises(StorageError, match="corrompu"):
        load_document(data_dir, doc_hash)


def test_document_exists(data_dir: Path) -> None:
    doc = _sample_document()
    assert not document_exists(data_dir, doc.hash)
    save_document(data_dir, doc)
    assert document_exists(data_dir, doc.hash)


def test_list_documents(data_dir: Path) -> None:
    """list_documents renvoie tous les documents enregistrés."""
    doc_a = _sample_document("Code A")
    doc_b = _sample_document("Code B")
    save_document(data_dir, doc_a)
    save_document(data_dir, doc_b)

    listed = list_documents(data_dir)
    names = sorted(d.name for d in listed)
    assert names == ["Code A", "Code B"]


def test_list_documents_ignores_corrupt_files(data_dir: Path) -> None:
    """Un fichier corrompu est loggé et ignoré, pas de crash global."""
    doc = _sample_document()
    save_document(data_dir, doc)

    corrupt = paths.document_path(data_dir, "b" * 64)
    corrupt.write_text("{", encoding="utf-8")

    listed = list_documents(data_dir)
    assert len(listed) == 1
    assert listed[0].hash == doc.hash


def test_delete_document_removes_files_and_versions(data_dir: Path) -> None:
    """La suppression enlève le doc, son HTML brut et ses versions."""
    from rogier.storage.versions import create_initial_version

    doc = _sample_document()
    save_document(data_dir, doc)

    raw_file = paths.raw_html_path(data_dir, doc.hash)
    raw_file.parent.mkdir(parents=True, exist_ok=True)
    raw_file.write_text("<html></html>", encoding="utf-8")

    version = create_initial_version(data_dir, doc)

    delete_document(data_dir, doc.hash)

    assert not document_exists(data_dir, doc.hash)
    assert not raw_file.exists()
    assert not paths.version_path(data_dir, version.id).exists()


def test_delete_missing_document_raises(data_dir: Path) -> None:
    with pytest.raises(StorageError, match="introuvable"):
        delete_document(data_dir, "c" * 64)


def test_save_is_atomic_under_concurrent_writes(data_dir: Path) -> None:
    """Deux écritures concurrentes ne doivent pas corrompre le fichier JSON."""
    doc = _sample_document()
    save_document(data_dir, doc)  # crée le fichier initial

    # Construire deux variantes distinctes
    variants = [_sample_document(f"Variant {i}") for i in range(20)]
    # Toutes partagent le même hash pour viser le même fichier
    for v in variants:
        v.hash = doc.hash

    errors: list[Exception] = []

    def writer(variant: Document) -> None:
        try:
            save_document(data_dir, variant)
        except Exception as e:  # noqa: BLE001 — test de robustesse
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(v,)) for v in variants]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []

    # Le fichier final doit être un JSON valide et décrivant un Document cohérent
    loaded = load_document(data_dir, doc.hash)
    assert loaded.hash == doc.hash
    assert loaded.name.startswith("Variant ") or loaded.name == doc.name
