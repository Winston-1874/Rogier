"""Tests unitaires pour les dataclasses de rogier.parsing.tree.

Vérifie la sérialisation (to_dict) et la désérialisation (from_dict)
de chaque dataclass du modèle de données, conformément au SPEC §8.4.
"""

from __future__ import annotations

from rogier.parsing.tree import (
    ChunkingConfig,
    Document,
    DocumentConfig,
    ModificationMarker,
    Node,
    NodeKind,
    NodeMetadata,
    ValidationConfig,
    Version,
    VersionRef,
)

# ---------------------------------------------------------------------------
# ModificationMarker
# ---------------------------------------------------------------------------


class TestModificationMarker:
    def test_roundtrip(self) -> None:
        marker = ModificationMarker(number=3, start_pos=10, end_pos=50)
        data = {"number": 3, "start_pos": 10, "end_pos": 50}
        assert ModificationMarker.from_dict(data) == marker

    def test_from_dict_coerces_types(self) -> None:
        """Les valeurs string sont converties en int."""
        data = {"number": "7", "start_pos": "0", "end_pos": "100"}
        m = ModificationMarker.from_dict(data)
        assert m.number == 7
        assert m.start_pos == 0
        assert m.end_pos == 100


# ---------------------------------------------------------------------------
# NodeMetadata
# ---------------------------------------------------------------------------


class TestNodeMetadata:
    def test_roundtrip_default(self) -> None:
        meta = NodeMetadata()
        d = meta.to_dict()
        assert d == {"source_range": None, "warnings": [], "modifications": []}
        assert NodeMetadata.from_dict(d) == meta

    def test_roundtrip_with_data(self) -> None:
        meta = NodeMetadata(
            source_range=(10, 200),
            warnings=["contenu vide", "titre court"],
            modifications=[ModificationMarker(1, 5, 15)],
        )
        d = meta.to_dict()
        restored = NodeMetadata.from_dict(d)
        assert restored.source_range == (10, 200)
        assert restored.warnings == ["contenu vide", "titre court"]
        assert len(restored.modifications) == 1
        assert restored.modifications[0].number == 1

    def test_from_dict_none_returns_default(self) -> None:
        assert NodeMetadata.from_dict(None) == NodeMetadata()

    def test_from_dict_empty_dict_returns_default(self) -> None:
        assert NodeMetadata.from_dict({}) == NodeMetadata()


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------


class TestNode:
    def test_roundtrip_article(self) -> None:
        node = Node(
            kind=NodeKind.ARTICLE,
            number="1:1",
            title="",
            content="Une societe est constituee...",
        )
        d = node.to_dict()
        restored = Node.from_dict(d)
        assert restored.kind == NodeKind.ARTICLE
        assert restored.number == "1:1"
        assert restored.content == "Une societe est constituee..."
        assert restored.children == []

    def test_roundtrip_nested(self) -> None:
        """Un arbre avec conteneur et enfants survit au roundtrip."""
        child = Node(kind=NodeKind.ARTICLE, number="1", content="texte")
        parent = Node(
            kind=NodeKind.TITRE,
            number="1er",
            title="Dispositions generales",
            children=[child],
        )
        root = Node(
            kind=NodeKind.DOCUMENT,
            title="Test",
            children=[parent],
        )
        d = root.to_dict()
        restored = Node.from_dict(d)
        assert restored.kind == NodeKind.DOCUMENT
        assert len(restored.children) == 1
        assert restored.children[0].kind == NodeKind.TITRE
        assert len(restored.children[0].children) == 1
        assert restored.children[0].children[0].content == "texte"

    def test_from_dict_missing_optional_fields(self) -> None:
        """Les champs optionnels absents recoivent des valeurs par defaut."""
        data = {"kind": "ARTICLE"}
        node = Node.from_dict(data)
        assert node.number == ""
        assert node.title == ""
        assert node.content == ""
        assert node.children == []
        assert node.metadata == NodeMetadata()

    def test_label_article(self) -> None:
        assert Node(kind=NodeKind.ARTICLE, number="2:5").label == "Art. 2:5"

    def test_label_container(self) -> None:
        assert Node(kind=NodeKind.CHAPITRE, number="3").label == "Chapitre 3"

    def test_label_document(self) -> None:
        assert Node(kind=NodeKind.DOCUMENT, title="Mon doc").label == "Mon doc"
        assert Node(kind=NodeKind.DOCUMENT).label == "Document"


# ---------------------------------------------------------------------------
# ChunkingConfig
# ---------------------------------------------------------------------------


class TestChunkingConfig:
    def test_roundtrip_default(self) -> None:
        cfg = ChunkingConfig()
        d = cfg.to_dict()
        restored = ChunkingConfig.from_dict(d)
        assert restored.strategy == "per_article"
        assert restored.hybrid_threshold == 2000
        assert restored.max_chunk_size == 5000
        assert restored.include_breadcrumb is True
        assert restored.include_node_titles is True

    def test_roundtrip_custom(self) -> None:
        cfg = ChunkingConfig(
            strategy="hybrid",
            hybrid_threshold=1500,
            max_chunk_size=8000,
            include_breadcrumb=False,
            breadcrumb_levels=["TITRE", "CHAPITRE"],
            include_node_titles=False,
        )
        d = cfg.to_dict()
        restored = ChunkingConfig.from_dict(d)
        assert restored.strategy == "hybrid"
        assert restored.hybrid_threshold == 1500
        assert restored.breadcrumb_levels == ["TITRE", "CHAPITRE"]
        assert restored.include_node_titles is False

    def test_from_dict_none_returns_default(self) -> None:
        assert ChunkingConfig.from_dict(None).strategy == "per_article"

    def test_from_dict_coerces_types(self) -> None:
        data = {"hybrid_threshold": "3000", "max_chunk_size": "10000"}
        cfg = ChunkingConfig.from_dict(data)
        assert cfg.hybrid_threshold == 3000
        assert cfg.max_chunk_size == 10000


# ---------------------------------------------------------------------------
# ValidationConfig
# ---------------------------------------------------------------------------


class TestValidationConfig:
    def test_roundtrip(self) -> None:
        cfg = ValidationConfig(
            must_contain=["61 500"],
            must_not_contain=["Table des matieres"],
        )
        d = cfg.to_dict()
        restored = ValidationConfig.from_dict(d)
        assert restored.must_contain == ["61 500"]
        assert restored.must_not_contain == ["Table des matieres"]

    def test_from_dict_none_returns_default(self) -> None:
        cfg = ValidationConfig.from_dict(None)
        assert cfg.must_contain == []
        assert cfg.must_not_contain == []


# ---------------------------------------------------------------------------
# DocumentConfig
# ---------------------------------------------------------------------------


class TestDocumentConfig:
    def test_roundtrip_default(self) -> None:
        cfg = DocumentConfig()
        d = cfg.to_dict()
        restored = DocumentConfig.from_dict(d)
        assert restored.chunking.strategy == "per_article"
        assert restored.validation.must_contain == []
        assert restored.manual_edits == {}

    def test_roundtrip_with_edits(self) -> None:
        cfg = DocumentConfig(
            manual_edits={"0.2.1": "contenu modifie"},
        )
        d = cfg.to_dict()
        restored = DocumentConfig.from_dict(d)
        assert restored.manual_edits == {"0.2.1": "contenu modifie"}

    def test_from_dict_none_returns_default(self) -> None:
        assert DocumentConfig.from_dict(None).manual_edits == {}


# ---------------------------------------------------------------------------
# VersionRef
# ---------------------------------------------------------------------------


class TestVersionRef:
    def test_roundtrip(self) -> None:
        ref = VersionRef(id="v-abc123def456", created_at="2026-04-12T10:00:00", label="Initiale")
        d = ref.to_dict()
        restored = VersionRef.from_dict(d)
        assert restored == ref


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------


class TestVersion:
    def test_roundtrip(self) -> None:
        ver = Version(
            id="v-abc123def456",
            document_hash="a" * 64,
            created_at="2026-04-12T10:00:00",
            label="Edition article 1:1",
            note="test",
            config=DocumentConfig(manual_edits={"0.0.0.0": "nouveau"}),
            parent_id="v-000000000000",
        )
        d = ver.to_dict()
        restored = Version.from_dict(d)
        assert restored.id == ver.id
        assert restored.document_hash == ver.document_hash
        assert restored.note == "test"
        assert restored.config.manual_edits == {"0.0.0.0": "nouveau"}
        assert restored.parent_id == "v-000000000000"

    def test_from_dict_missing_optional(self) -> None:
        data = {
            "id": "v-abc123def456",
            "document_hash": "a" * 64,
            "created_at": "2026-04-12T10:00:00",
            "label": "Initiale",
        }
        ver = Version.from_dict(data)
        assert ver.note == ""
        assert ver.parent_id is None
        assert ver.config.manual_edits == {}


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------


class TestDocument:
    def test_roundtrip(self) -> None:
        doc = Document(
            hash="b" * 64,
            name="Code des societes et associations",
            source_url="https://www.ejustice.just.fgov.be/cgi_loi/change_lg.pl?...",
            created_at="2026-04-12T10:00:00",
            family="justel_html",
            tree=Node(
                kind=NodeKind.DOCUMENT,
                title="CSA",
                children=[Node(kind=NodeKind.ARTICLE, number="1:1", content="texte")],
            ),
            raw_html_path="/data/raw/bbbb.html",
            current_version_id="v-abc123def456",
            versions=[
                VersionRef(id="v-abc123def456", created_at="2026-04-12T10:00:00", label="Initiale"),
            ],
            schema_version=1,
        )
        d = doc.to_dict()
        restored = Document.from_dict(d)
        assert restored.hash == doc.hash
        assert restored.name == doc.name
        assert restored.source_url == doc.source_url
        assert len(restored.versions) == 1
        assert restored.versions[0].id == "v-abc123def456"
        assert restored.tree.children[0].content == "texte"
        assert restored.schema_version == 1

    def test_from_dict_missing_optional(self) -> None:
        data = {
            "hash": "c" * 64,
            "name": "Test",
            "tree": {"kind": "DOCUMENT"},
        }
        doc = Document.from_dict(data)
        assert doc.source_url is None
        assert doc.source_filename is None
        assert doc.created_at == ""
        assert doc.current_version_id == ""
        assert doc.versions == []
        assert doc.schema_version == 1

    def test_schema_version_coerced(self) -> None:
        """schema_version string est converti en int."""
        data = {
            "hash": "d" * 64,
            "name": "Test",
            "tree": {"kind": "DOCUMENT"},
            "schema_version": "1",
        }
        doc = Document.from_dict(data)
        assert doc.schema_version == 1
        assert isinstance(doc.schema_version, int)
