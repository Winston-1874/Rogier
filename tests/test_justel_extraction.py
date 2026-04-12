"""Tests du parser HTML Justel (SPEC §7.10)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from rogier.errors import JustelParseError
from rogier.extraction.justel_html import (
    ParsingReport,
    find_article,
    locate_body,
    parse_justel_html,
)
from rogier.parsing.tree import Node, NodeKind

# ---------------------------------------------------------------------------
# Chemins
# ---------------------------------------------------------------------------

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_HTML = FIXTURES_DIR / "csa_sample.html"

# Le CSA complet est dans pre-app/ — utilisé uniquement par le test slow.
CSA_FULL_HTML = Path(__file__).parent.parent / "pre-app" / "Banque de données Justel.html"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _count_by_kind(node: Node) -> dict[str, int]:
    """Compter récursivement les nœuds par kind."""
    counts: dict[str, int] = {}

    def rec(n: Node) -> None:
        key = n.kind.value
        counts[key] = counts.get(key, 0) + 1
        for c in n.children:
            rec(c)

    rec(node)
    return counts


def _all_articles(node: Node) -> list[Node]:
    """Collecter tous les articles de l'arbre."""
    result: list[Node] = []

    def rec(n: Node) -> None:
        if n.kind == NodeKind.ARTICLE:
            result.append(n)
        for c in n.children:
            rec(c)

    rec(node)
    return result


def _max_depth(node: Node, depth: int = 0) -> int:
    """Profondeur maximale de l'arbre."""
    if not node.children:
        return depth
    return max(_max_depth(c, depth + 1) for c in node.children)


# ---------------------------------------------------------------------------
# Tests sur la fixture (3 premiers livres du CSA)
# ---------------------------------------------------------------------------


class TestParseSample:
    """Tests sur csa_sample.html (3 premiers livres)."""

    @pytest.fixture(scope="class")
    def parsed(self) -> tuple[Node, ParsingReport]:
        html = SAMPLE_HTML.read_text(encoding="utf-8")
        return parse_justel_html(html, "CSA (fixture)")

    @pytest.fixture(scope="class")
    def tree(self, parsed: tuple[Node, ParsingReport]) -> Node:
        return parsed[0]

    @pytest.fixture(scope="class")
    def report(self, parsed: tuple[Node, ParsingReport]) -> ParsingReport:
        return parsed[1]

    def test_parse_no_exception(self, tree: Node) -> None:
        """Parse complet sans exception."""
        assert tree.kind == NodeKind.DOCUMENT

    def test_parties_count(self, report: ParsingReport) -> None:
        assert report.counts_by_kind.get("PARTIE", 0) == 2

    def test_livres_count(self, report: ParsingReport) -> None:
        assert report.counts_by_kind.get("LIVRE", 0) == 3

    def test_titres_count(self, report: ParsingReport) -> None:
        assert report.counts_by_kind.get("TITRE", 0) == 28

    def test_chapitres_count(self, report: ParsingReport) -> None:
        assert report.counts_by_kind.get("CHAPITRE", 0) == 36

    def test_sections_count(self, report: ParsingReport) -> None:
        assert report.counts_by_kind.get("SECTION", 0) == 44

    def test_sous_sections_count(self, report: ParsingReport) -> None:
        assert report.counts_by_kind.get("SOUS_SECTION", 0) == 40

    def test_articles_count(self, report: ParsingReport) -> None:
        assert report.total_articles == 336

    def test_article_1_1_content(self, tree: Node) -> None:
        """Art. 1:1 non vide et contient la phrase attendue."""
        art = find_article(tree, "1:1")
        assert art is not None
        assert len(art.content) > 0
        assert "Une société est constituée" in art.content

    def test_article_1_2_content(self, tree: Node) -> None:
        """Art. 1:2 contient la phrase attendue."""
        art = find_article(tree, "1:2")
        assert art is not None
        assert "Une association est constituée" in art.content

    def test_tree_coherence_depth(self, tree: Node) -> None:
        """L'arbre est cohérent : pas de niveaux impossibles."""
        depth_order = {
            NodeKind.DOCUMENT: 0,
            NodeKind.PARTIE: 1,
            NodeKind.LIVRE: 2,
            NodeKind.TITRE: 3,
            NodeKind.CHAPITRE: 4,
            NodeKind.SECTION: 5,
            NodeKind.SOUS_SECTION: 6,
            NodeKind.ARTICLE: 7,
        }

        def check(node: Node, parent_depth: int) -> None:
            d = depth_order.get(node.kind, 99)
            assert d > parent_depth, (
                f"{node.label} (depth {d}) est enfant d'un nœud de depth {parent_depth}"
            )
            for c in node.children:
                check(c, d)

        # Le root est DOCUMENT (depth 0), ses enfants doivent être > 0
        for child in tree.children:
            check(child, 0)

    def test_no_residual_html(self, tree: Node) -> None:
        """Aucun HTML résiduel dans les contenus d'articles.

        Les références législatives ``<L 2020-...>`` ne sont pas du HTML
        résiduel — ce sont des notes de bas de page Justel.
        """
        # On cherche les vraies balises HTML (<a, <br, <div, </span>, etc.),
        # pas les références de type <L ... > ou <AR ... >.
        re_html_tag = re.compile(
            r"</?(?:a|br|div|span|sup|font|p|table|tr|td|th|img|b|i|u|em|strong|h\d)\b[^>]*>"
        )
        articles = _all_articles(tree)
        for art in articles:
            assert not re_html_tag.search(art.content), (
                f"Art. {art.number} contient du HTML résiduel : "
                f"{re_html_tag.search(art.content).group()}"  # type: ignore[union-attr]
            )

    def test_warnings_produced(self, report: ParsingReport) -> None:
        """Des warnings de titre tronqué sont bien produits."""
        mod_warnings = [w for w in report.warnings if "marqueur de modification" in w]
        assert len(mod_warnings) > 0

    def test_truncated_titles_fixed(self, tree: Node) -> None:
        """Les titres 6/1 et 6/2 ont un vrai titre, pas juste '['."""
        def find_titres(node: Node, number: str) -> list[Node]:
            result: list[Node] = []
            if node.kind == NodeKind.TITRE and node.number == number:
                result.append(node)
            for c in node.children:
                result.extend(find_titres(c, number))
            return result

        for num in ("6/1", "6/2"):
            nodes = find_titres(tree, num)
            assert len(nodes) == 1, f"TITRE {num} introuvable"
            assert nodes[0].title != "[", (
                f"TITRE {num} a un titre tronqué : '{nodes[0].title}'"
            )
            assert len(nodes[0].title) > 5, (
                f"TITRE {num} titre trop court : '{nodes[0].title}'"
            )

    def test_articles_no_empty_content(self, tree: Node) -> None:
        """Aucun article ne devrait avoir un contenu vide dans la fixture."""
        articles = _all_articles(tree)
        for art in articles:
            assert art.content, f"Art. {art.number} a un contenu vide"


# ---------------------------------------------------------------------------
# Tests unitaires du locate_body
# ---------------------------------------------------------------------------


class TestLocateBody:

    def test_missing_toc_marker(self) -> None:
        with pytest.raises(JustelParseError, match="table des matières"):
            locate_body("<html><body>pas de marqueur</body></html>")

    def test_missing_body_anchor(self) -> None:
        html = '<div id="list-title-2">' + "x" * 2000 + "</div>"
        with pytest.raises(JustelParseError, match="LNK0001"):
            locate_body(html)

    def test_body_without_articles_modifies(self) -> None:
        """Si 'Articles modifiés' est absent, le body va jusqu'à la fin."""
        html = (
            '<div id="list-title-2">'
            + "x" * 2000
            + '<a name="LNK0001">contenu</a>'
            + "suite du corps"
        )
        body = locate_body(html)
        assert "contenu" in body
        assert "suite du corps" in body


# ---------------------------------------------------------------------------
# Test slow sur le CSA complet
# ---------------------------------------------------------------------------


@pytest.mark.slow
class TestCSAComplet:
    """Tests de bout en bout sur le CSA complet (2.9 MB).

    Skippé si le fichier n'est pas présent.
    """

    @pytest.fixture(scope="class")
    def parsed(self) -> tuple[Node, ParsingReport]:
        if not CSA_FULL_HTML.exists():
            pytest.skip(f"Fichier CSA complet introuvable : {CSA_FULL_HTML}")
        html = CSA_FULL_HTML.read_text(encoding="utf-8")
        return parse_justel_html(
            html, "Code des sociétés et des associations (CSA)"
        )

    @pytest.fixture(scope="class")
    def tree(self, parsed: tuple[Node, ParsingReport]) -> Node:
        return parsed[0]

    @pytest.fixture(scope="class")
    def report(self, parsed: tuple[Node, ParsingReport]) -> ParsingReport:
        return parsed[1]

    def test_parties(self, report: ParsingReport) -> None:
        assert report.counts_by_kind["PARTIE"] == 5

    def test_livres(self, report: ParsingReport) -> None:
        assert report.counts_by_kind["LIVRE"] == 18

    def test_titres(self, report: ParsingReport) -> None:
        assert report.counts_by_kind["TITRE"] == 111

    def test_chapitres(self, report: ParsingReport) -> None:
        assert report.counts_by_kind["CHAPITRE"] == 147

    def test_sections(self, report: ParsingReport) -> None:
        assert report.counts_by_kind["SECTION"] == 227

    def test_sous_sections(self, report: ParsingReport) -> None:
        assert report.counts_by_kind["SOUS_SECTION"] == 127

    def test_articles(self, report: ParsingReport) -> None:
        assert report.total_articles == 1278

    def test_article_1_1(self, tree: Node) -> None:
        art = find_article(tree, "1:1")
        assert art is not None
        assert len(art.content) == 317
        assert art.content.startswith("Une société est constituée")

    def test_article_7_2(self, tree: Node) -> None:
        art = find_article(tree, "7:2")
        assert art is not None
        assert len(art.content) == 49
        assert "61 500 euros" in art.content

    def test_article_18_8_no_number_prefix(self, tree: Node) -> None:
        """Régression : Art. 18:8 (forme B) ne doit pas commencer par '18:8.'."""
        art = find_article(tree, "18:8")
        assert art is not None
        assert not art.content.startswith("18:8.")

    def test_30_truncated_titles(self, report: ParsingReport) -> None:
        """30 titres extraits de marqueurs de modification."""
        mod_warnings = [
            w for w in report.warnings if "marqueur de modification" in w
        ]
        assert len(mod_warnings) == 30
