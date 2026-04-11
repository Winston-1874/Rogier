"""Tests de l'infrastructure de migration du schéma (SPEC §8.4)."""

from __future__ import annotations

from pathlib import Path

import pytest

from rogier.errors import StorageError
from rogier.parsing.tree import Document, Node, NodeKind
from rogier.storage import migrations, paths
from rogier.storage.documents import load_document, save_document
from rogier.storage.locks import read_json, write_json
from rogier.storage.migrations import (
    CURRENT_SCHEMA_VERSION,
    MIGRATIONS,
    migrate,
    needs_migration,
)


@pytest.fixture()
def data_dir(tmp_path: Path) -> Path:
    d = tmp_path / "rogier_data"
    paths.ensure_dirs(d)
    return d


def test_current_schema_version_is_1() -> None:
    """En v0.1, le schéma courant est la version 1."""
    assert CURRENT_SCHEMA_VERSION == 1


def test_no_migrations_registered_in_v01() -> None:
    """Aucune migration réelle n'est nécessaire en v0.1."""
    assert MIGRATIONS == {}


def test_needs_migration_false_for_current() -> None:
    data = {"schema_version": CURRENT_SCHEMA_VERSION}
    assert needs_migration(data) is False


def test_needs_migration_true_for_older() -> None:
    data = {"schema_version": 0}
    assert needs_migration(data) is True


def test_migrate_noop_when_already_current() -> None:
    """Si le schéma est déjà courant, migrate ne fait rien."""
    data = {"schema_version": CURRENT_SCHEMA_VERSION, "hash": "x", "name": "Test"}
    out = migrate(data, from_version=CURRENT_SCHEMA_VERSION)
    assert out["schema_version"] == CURRENT_SCHEMA_VERSION


def test_migrate_raises_if_schema_too_new() -> None:
    """Un fichier créé par une version future lève une erreur claire."""
    data = {"schema_version": 99}
    with pytest.raises(StorageError, match="version plus récente"):
        migrate(data, from_version=99)


def test_migrate_raises_if_intermediate_missing() -> None:
    """Si une migration intermédiaire n'existe pas, erreur claire."""
    # Simule un schéma obsolète sans migrateur enregistré
    data = {"schema_version": 0, "hash": "x", "name": "T"}
    with pytest.raises(StorageError, match="Migration de v0 vers v1"):
        migrate(data, from_version=0)


def test_migrate_pipeline_chains_multiple_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test de chaînage : v0 → v1 → v2, en simulant CURRENT_SCHEMA_VERSION = 2."""
    calls: list[int] = []

    def v0_to_v1(d: dict) -> dict:
        calls.append(1)
        d = dict(d)
        d["migrated_to"] = 1
        return d

    def v1_to_v2(d: dict) -> dict:
        calls.append(2)
        d = dict(d)
        d["migrated_to"] = 2
        return d

    monkeypatch.setattr(migrations, "CURRENT_SCHEMA_VERSION", 2)
    monkeypatch.setattr(migrations, "MIGRATIONS", {0: v0_to_v1, 1: v1_to_v2})

    result = migrations.migrate({"schema_version": 0, "payload": "x"}, from_version=0)

    assert calls == [1, 2]
    assert result["migrated_to"] == 2
    assert result["schema_version"] == 2


def test_load_document_applies_migration_and_persists(
    data_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """À la lecture, un document d'un ancien schéma est migré et ré-enregistré."""
    # Enregistrer un document avec un schema_version inventé plus ancien
    doc = Document(
        hash="deadbeef" * 8,
        name="Document ancien",
        tree=Node(kind=NodeKind.DOCUMENT, title="Document ancien"),
    )
    save_document(data_dir, doc)

    # Réécrire le fichier avec schema_version = 0 et un champ inventé
    path = paths.document_path(data_dir, doc.hash)
    raw = read_json(path)
    raw["schema_version"] = 0
    raw["ancien_champ"] = "à supprimer"
    write_json(path, raw)

    # Enregistrer une migration v0 → v1 qui supprime le champ inventé
    def v0_to_v1(d: dict) -> dict:
        d = dict(d)
        d.pop("ancien_champ", None)
        return d

    monkeypatch.setattr(migrations, "MIGRATIONS", {0: v0_to_v1})

    # La lecture doit appliquer la migration
    loaded = load_document(data_dir, doc.hash)
    assert loaded.hash == doc.hash
    assert loaded.schema_version == CURRENT_SCHEMA_VERSION

    # Et persister le résultat migré sur disque
    on_disk = read_json(path)
    assert on_disk["schema_version"] == CURRENT_SCHEMA_VERSION
    assert "ancien_champ" not in on_disk


def test_load_document_raises_if_schema_too_new(
    data_dir: Path,
) -> None:
    """Un document créé par une version future lève une erreur française."""
    doc = Document(
        hash="f" * 64,
        name="Futur",
        tree=Node(kind=NodeKind.DOCUMENT),
    )
    save_document(data_dir, doc)

    # Forcer schema_version à une valeur future
    path = paths.document_path(data_dir, doc.hash)
    raw = read_json(path)
    raw["schema_version"] = CURRENT_SCHEMA_VERSION + 5
    write_json(path, raw)

    with pytest.raises(StorageError, match="version plus récente"):
        load_document(data_dir, doc.hash)
