"""Tests de l'export Markdown et du manifest JSON (§10.4, §10.5, §10.7)."""

from __future__ import annotations

from pathlib import Path

from rogier.chunking.export import export_manifest, export_markdown
from rogier.chunking.strategies import Chunk, chunk_per_article
from rogier.extraction.justel_html import parse_justel_html
from rogier.parsing.tree import (
    ChunkingConfig,
    Document,
    DocumentConfig,
    Version,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_HTML = FIXTURES_DIR / "csa_sample.html"


def _make_doc() -> Document:
    return Document(
        hash="a" * 64,
        name="Code des sociétés et des associations",
        source_url="https://www.ejustice.just.fgov.be/eli/loi/2019/03/23/2019011117/justel",
    )


def _make_version(doc_hash: str = "a" * 64) -> Version:
    return Version(
        id="v-aabbccddeeff",
        document_hash=doc_hash,
        created_at="2026-04-12T10:00:00Z",
        label="Export test",
        config=DocumentConfig(),
    )


def _make_chunks() -> list[Chunk]:
    return [
        Chunk(breadcrumb="CSA > Art. 1:1", content="Première disposition."),
        Chunk(breadcrumb="CSA > Art. 1:2", content="Deuxième disposition."),
        Chunk(breadcrumb="CSA > Art. 1:3", content="Troisième disposition."),
    ]


# ---------------------------------------------------------------------------
# export_markdown
# ---------------------------------------------------------------------------


class TestExportMarkdown:
    """Tests du format Markdown exporté (§10.4)."""

    def test_header_contains_title(self) -> None:
        doc = _make_doc()
        version = _make_version()
        chunks = _make_chunks()
        md = export_markdown(doc, version, chunks)
        assert md.startswith("# Code des sociétés et des associations\n")

    def test_header_contains_source(self) -> None:
        doc = _make_doc()
        version = _make_version()
        md = export_markdown(doc, version, _make_chunks())
        assert "> Source : Justel (ejustice.just.fgov.be)" in md

    def test_header_contains_url(self) -> None:
        doc = _make_doc()
        version = _make_version()
        md = export_markdown(doc, version, _make_chunks())
        assert "> URL : https://www.ejustice.just.fgov.be/" in md

    def test_header_contains_chunk_count(self) -> None:
        doc = _make_doc()
        version = _make_version()
        chunks = _make_chunks()
        md = export_markdown(doc, version, chunks)
        assert "> Nombre de chunks : 3" in md

    def test_header_contains_strategy(self) -> None:
        doc = _make_doc()
        version = _make_version()
        md = export_markdown(doc, version, _make_chunks())
        assert "> Stratégie : un chunk par article" in md

    def test_separator_between_chunks(self) -> None:
        """Les chunks sont séparés par --- (§10.4)."""
        doc = _make_doc()
        version = _make_version()
        chunks = _make_chunks()
        md = export_markdown(doc, version, chunks)
        assert md.count("\n---\n") == 3  # avant chaque chunk

    def test_breadcrumb_format(self) -> None:
        """Chaque chunk commence par **[...]** suivi d'une ligne vide (§10.7)."""
        doc = _make_doc()
        version = _make_version()
        chunks = _make_chunks()
        md = export_markdown(doc, version, chunks)
        assert "**[CSA > Art. 1:1]**\n\n" in md

    def test_chunk_content_present(self) -> None:
        doc = _make_doc()
        version = _make_version()
        chunks = _make_chunks()
        md = export_markdown(doc, version, chunks)
        assert "Première disposition." in md
        assert "Troisième disposition." in md


# ---------------------------------------------------------------------------
# export_manifest
# ---------------------------------------------------------------------------


class TestExportManifest:
    """Tests du manifest JSON (§10.5)."""

    def test_required_fields(self) -> None:
        """Le manifest contient tous les champs obligatoires (§10.5)."""
        doc = _make_doc()
        version = _make_version()
        chunks = _make_chunks()
        config = ChunkingConfig()
        manifest = export_manifest(doc, version, chunks, config)
        for key in (
            "document_hash",
            "document_name",
            "source_url",
            "exported_at",
            "exporter",
            "strategy",
            "parameters",
            "stats",
            "version_id",
            "validation",
        ):
            assert key in manifest, f"Champ manquant : {key}"

    def test_stats_correct(self) -> None:
        """Les stats sont calculées correctement (§10.7)."""
        doc = _make_doc()
        version = _make_version()
        chunks = [
            Chunk(breadcrumb="A", content="x" * 100),
            Chunk(breadcrumb="B", content="y" * 200),
            Chunk(breadcrumb="C", content="z" * 300),
        ]
        config = ChunkingConfig()
        manifest = export_manifest(doc, version, chunks, config)
        stats = manifest["stats"]
        assert stats["total_chunks"] == 3
        assert stats["min_chunk_size"] == 100
        assert stats["max_chunk_size"] == 300
        assert stats["avg_chunk_size"] == 200
        assert stats["median_chunk_size"] == 200

    def test_parameters_match_config(self) -> None:
        doc = _make_doc()
        version = _make_version()
        config = ChunkingConfig(hybrid_threshold=3000, max_chunk_size=8000)
        manifest = export_manifest(doc, version, _make_chunks(), config)
        assert manifest["parameters"]["hybrid_threshold"] == 3000
        assert manifest["parameters"]["max_chunk_size"] == 8000

    def test_version_id(self) -> None:
        doc = _make_doc()
        version = _make_version()
        config = ChunkingConfig()
        manifest = export_manifest(doc, version, _make_chunks(), config)
        assert manifest["version_id"] == "v-aabbccddeeff"

    def test_warnings_collected(self) -> None:
        """Les warnings des chunks sont collectés dans le manifest."""
        doc = _make_doc()
        version = _make_version()
        chunks = [
            Chunk(breadcrumb="A", content="x", warnings=["warn1"]),
            Chunk(breadcrumb="B", content="y", warnings=["warn2"]),
        ]
        config = ChunkingConfig()
        manifest = export_manifest(doc, version, chunks, config)
        assert manifest["validation"]["chunk_warnings"] == ["warn1", "warn2"]


# ---------------------------------------------------------------------------
# Intégration : export sur la fixture CSA sample
# ---------------------------------------------------------------------------


class TestExportCSASample:
    """Tests d'intégration sur la fixture 3 livres."""

    def test_per_article_export_chunk_count(self) -> None:
        html = SAMPLE_HTML.read_text(encoding="utf-8")
        tree, _ = parse_justel_html(html, "CSA (fixture)")
        config = ChunkingConfig()
        chunks = chunk_per_article(tree, config)
        doc = Document(
            hash="b" * 64,
            name="CSA (fixture)",
            source_url="https://example.com",
        )
        version = _make_version(doc.hash)
        md = export_markdown(doc, version, chunks)
        # 336 articles → 336 chunks → 336 séparateurs ---
        # (1 avant chaque chunk)
        assert md.count("**[") == 336
        manifest = export_manifest(doc, version, chunks, config)
        assert manifest["stats"]["total_chunks"] == 336
