"""Tests des stratégies de chunking (§10.1, §10.2, §10.7)."""

from __future__ import annotations

from pathlib import Path

from rogier.chunking.breadcrumb import build_breadcrumb
from rogier.chunking.strategies import (
    chunk_hybrid,
    chunk_per_article,
)
from rogier.extraction.justel_html import parse_justel_html
from rogier.parsing.tree import ChunkingConfig, Node, NodeKind

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_HTML = FIXTURES_DIR / "csa_sample.html"


def _parse_sample() -> Node:
    """Parser la fixture CSA sample (3 livres, 336 articles)."""
    html = SAMPLE_HTML.read_text(encoding="utf-8")
    tree, _ = parse_justel_html(html, "CSA (fixture)")
    return tree


# ---------------------------------------------------------------------------
# build_breadcrumb
# ---------------------------------------------------------------------------


class TestBuildBreadcrumb:
    """Tests pour build_breadcrumb (§10.3)."""

    def test_simple_breadcrumb(self) -> None:
        root = Node(kind=NodeKind.DOCUMENT, title="CSA")
        livre = Node(kind=NodeKind.LIVRE, number="1er", title="Dispositions introductives")
        article = Node(kind=NodeKind.ARTICLE, number="1:1")
        path = [root, livre, article]
        bc = build_breadcrumb(path, include_titles=True)
        assert bc == "CSA > Livre 1er — Dispositions introductives > Art. 1:1"

    def test_breadcrumb_without_titles(self) -> None:
        root = Node(kind=NodeKind.DOCUMENT, title="CSA")
        livre = Node(kind=NodeKind.LIVRE, number="1er", title="Dispositions introductives")
        article = Node(kind=NodeKind.ARTICLE, number="1:1")
        path = [root, livre, article]
        bc = build_breadcrumb(path, include_titles=False)
        assert bc == "CSA > Livre 1er > Art. 1:1"

    def test_breadcrumb_levels_filter(self) -> None:
        root = Node(kind=NodeKind.DOCUMENT, title="CSA")
        partie = Node(kind=NodeKind.PARTIE, number="1re")
        livre = Node(kind=NodeKind.LIVRE, number="1er")
        article = Node(kind=NodeKind.ARTICLE, number="1:1")
        path = [root, partie, livre, article]
        bc = build_breadcrumb(
            path,
            include_titles=False,
            levels_filter=["DOCUMENT", "ARTICLE"],
        )
        assert bc == "CSA > Art. 1:1"

    def test_breadcrumb_document_title_no_duplicate(self) -> None:
        """Le nœud DOCUMENT avec title == label ne duplique pas."""
        root = Node(kind=NodeKind.DOCUMENT, title="Mon doc")
        bc = build_breadcrumb([root], include_titles=True)
        assert bc == "Mon doc"
        assert "—" not in bc


# ---------------------------------------------------------------------------
# chunk_per_article
# ---------------------------------------------------------------------------


class TestChunkPerArticle:
    """Tests pour la stratégie per_article (§10.1)."""

    def test_count_matches_articles(self) -> None:
        """Le nombre de chunks == le nombre d'articles (336 pour la fixture)."""
        tree = _parse_sample()
        config = ChunkingConfig()
        chunks = chunk_per_article(tree, config)
        assert len(chunks) == 336

    def test_each_chunk_has_breadcrumb(self) -> None:
        tree = _parse_sample()
        config = ChunkingConfig()
        chunks = chunk_per_article(tree, config)
        for chunk in chunks:
            assert chunk.breadcrumb, f"Chunk sans breadcrumb : {chunk.content[:50]}"

    def test_breadcrumb_format_art_1_1(self) -> None:
        """Vérifier le breadcrumb de Art. 1:1 (§10.7)."""
        tree = _parse_sample()
        config = ChunkingConfig()
        chunks = chunk_per_article(tree, config)
        first = chunks[0]
        assert "Art. 1:1" in first.breadcrumb
        assert first.breadcrumb.startswith("CSA (fixture)")

    def test_no_breadcrumb_when_disabled(self) -> None:
        tree = _parse_sample()
        config = ChunkingConfig(include_breadcrumb=False)
        chunks = chunk_per_article(tree, config)
        assert all(c.breadcrumb == "" for c in chunks)

    def test_manual_edits_overlay(self) -> None:
        """Les manual_edits remplacent le contenu de l'article."""
        tree = _parse_sample()
        config = ChunkingConfig()
        # Trouver le chemin du premier article
        chunks_before = chunk_per_article(tree, config)
        original = chunks_before[0].content

        # Appliquer un edit sur le premier article (chemin "0.0.0.0.0")
        # On doit trouver le vrai chemin
        from rogier.chunking.strategies import _walk_articles
        articles = _walk_articles(tree, "")
        first_path = articles[0][1]

        edits = {first_path: "Contenu modifié par test"}
        chunks_after = chunk_per_article(tree, config, edits)
        assert chunks_after[0].content == "Contenu modifié par test"
        assert chunks_after[0].content != original


# ---------------------------------------------------------------------------
# chunk_hybrid
# ---------------------------------------------------------------------------


class TestChunkHybrid:
    """Tests pour la stratégie hybrid (§10.2)."""

    def test_short_article_single_chunk(self) -> None:
        """Un article court (< threshold) produit un seul chunk."""
        root = Node(kind=NodeKind.DOCUMENT, title="Test")
        art = Node(kind=NodeKind.ARTICLE, number="1", content="Contenu court.")
        root.children = [art]
        config = ChunkingConfig(strategy="hybrid", hybrid_threshold=2000)
        chunks = chunk_hybrid(root, config)
        assert len(chunks) == 1
        assert chunks[0].content == "Contenu court."

    def test_long_article_with_paragraphs_split(self) -> None:
        """Un article long avec §§ est découpé en sous-chunks."""
        long_content = (
            "Introduction de l'article.\n"
            "§ 1er. Premier paragraphe très long " + "x" * 500 + "\n"
            "§ 2. Deuxième paragraphe " + "y" * 500
        )
        root = Node(kind=NodeKind.DOCUMENT, title="Test")
        art = Node(kind=NodeKind.ARTICLE, number="3:6", content=long_content)
        root.children = [art]
        config = ChunkingConfig(strategy="hybrid", hybrid_threshold=100)
        chunks = chunk_hybrid(root, config)
        # Intro + 2 paragraphes = 3 chunks
        assert len(chunks) == 3
        # Les sous-chunks de § ont le numéro dans le breadcrumb
        para_bcs = [c.breadcrumb for c in chunks if "§" in c.breadcrumb]
        assert len(para_bcs) == 2
        assert "§ 1er" in para_bcs[0]
        assert "§ 2" in para_bcs[1]

    def test_long_article_no_paragraphs_warning(self) -> None:
        """Un article long sans § reste en un chunk avec un warning."""
        long_content = "Contenu sans paragraphes. " * 200
        root = Node(kind=NodeKind.DOCUMENT, title="Test")
        art = Node(kind=NodeKind.ARTICLE, number="99", content=long_content)
        root.children = [art]
        config = ChunkingConfig(strategy="hybrid", hybrid_threshold=100)
        chunks = chunk_hybrid(root, config)
        assert len(chunks) == 1
        assert len(chunks[0].warnings) == 1
        assert "pas de paragraphes" in chunks[0].warnings[0]

    def test_paragraph_exceeds_max_chunk_size_warning(self) -> None:
        """Un paragraphe dépassant max_chunk_size génère un warning."""
        long_content = "§ 1er. " + "z" * 6000
        root = Node(kind=NodeKind.DOCUMENT, title="Test")
        art = Node(kind=NodeKind.ARTICLE, number="5", content=long_content)
        root.children = [art]
        config = ChunkingConfig(
            strategy="hybrid",
            hybrid_threshold=100,
            max_chunk_size=5000,
        )
        chunks = chunk_hybrid(root, config)
        assert len(chunks) == 1
        assert any("taille max" in w for w in chunks[0].warnings)
