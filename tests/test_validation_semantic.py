"""Tests des invariants sémantiques et du rapport de validation."""

from rogier.parsing.tree import Node, NodeKind, ValidationConfig
from rogier.validation.report import build_report
from rogier.validation.semantic import run_semantic

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _article(number: str, content: str) -> Node:
    return Node(kind=NodeKind.ARTICLE, number=number, content=content)


def _doc(children: list[Node]) -> Node:
    return Node(kind=NodeKind.DOCUMENT, title="Test", children=children)


def _simple_tree() -> Node:
    """Arbre avec contenu contenant « 61 500 » et « Code des sociétés »."""
    return _doc([
        Node(kind=NodeKind.CHAPITRE, number="1", children=[
            _article("1", "Le seuil est fixé à 61 500 euros conformément au Code des sociétés."),
            _article("2", "Les administrateurs veillent au respect de la présente loi."),
        ]),
    ])


# ---------------------------------------------------------------------------
# run_semantic
# ---------------------------------------------------------------------------


class TestMustContain:
    def test_pass_string_present(self):
        tree = _simple_tree()
        config = ValidationConfig(must_contain=["61 500"])
        results = run_semantic(tree, config)
        assert len(results) == 1
        assert results[0]["status"] == "pass"
        assert results[0]["id"] == "must_contain:61 500"

    def test_fail_string_absent(self):
        tree = _simple_tree()
        config = ValidationConfig(must_contain=["99 999"])
        results = run_semantic(tree, config)
        assert len(results) == 1
        assert results[0]["status"] == "fail"

    def test_multiple(self):
        tree = _simple_tree()
        config = ValidationConfig(must_contain=["61 500", "absent"])
        results = run_semantic(tree, config)
        assert results[0]["status"] == "pass"
        assert results[1]["status"] == "fail"


class TestMustNotContain:
    def test_pass_string_absent(self):
        tree = _simple_tree()
        config = ValidationConfig(must_not_contain=["Table des matières"])
        results = run_semantic(tree, config)
        assert len(results) == 1
        assert results[0]["status"] == "pass"

    def test_fail_string_present(self):
        tree = _simple_tree()
        config = ValidationConfig(must_not_contain=["61 500"])
        results = run_semantic(tree, config)
        assert len(results) == 1
        assert results[0]["status"] == "fail"


class TestSemanticWithOverlay:
    def test_overlay_changes_validation(self):
        """Un edit qui supprime « 61 500 » fait échouer must_contain."""
        tree = _simple_tree()
        config = ValidationConfig(must_contain=["61 500"])

        # Sans overlay → pass
        results = run_semantic(tree, config)
        assert results[0]["status"] == "pass"

        # Avec overlay qui remplace le contenu de l'article 1 (chemin 0.0)
        edits = {"0.0": "Le seuil a été modifié."}
        results = run_semantic(tree, config, edits)
        assert results[0]["status"] == "fail"


class TestEmptyConfig:
    def test_no_invariants(self):
        tree = _simple_tree()
        config = ValidationConfig()
        results = run_semantic(tree, config)
        assert results == []


# ---------------------------------------------------------------------------
# build_report — rapport global
# ---------------------------------------------------------------------------


class TestBuildReport:
    def test_overall_pass_healthy_tree(self):
        tree = _simple_tree()
        report = build_report(tree)
        assert report.overall == "pass"
        assert len(report.structural) == 8
        assert all(r.status == "pass" for r in report.structural)

    def test_overall_fail_with_semantic(self):
        tree = _simple_tree()
        config = ValidationConfig(must_contain=["introuvable"])
        report = build_report(tree, config)
        assert report.overall == "fail"
        assert any(r.status == "fail" for r in report.semantic)

    def test_overall_pass_with_semantic(self):
        tree = _simple_tree()
        config = ValidationConfig(
            must_contain=["61 500"],
            must_not_contain=["Table des matières"],
        )
        report = build_report(tree, config)
        assert report.overall == "pass"
        assert len(report.semantic) == 2

    def test_generated_at_is_set(self):
        report = build_report(_simple_tree())
        assert report.generated_at
        assert "T" in report.generated_at  # ISO format

    def test_to_dict(self):
        report = build_report(_simple_tree())
        d = report.to_dict()
        assert "structural" in d
        assert "semantic" in d
        assert "overall" in d
        assert d["overall"] == "pass"

    def test_s008_cross_check_consistent(self):
        """S008 data.count matches the actual warning count in the tree."""
        from rogier.parsing.tree import NodeMetadata

        tree = _doc([
            Node(
                kind=NodeKind.CHAPITRE, number="1",
                children=[
                    Node(
                        kind=NodeKind.ARTICLE, number="1",
                        content="Contenu long suffisant pour les tests.",
                        metadata=NodeMetadata(warnings=["warn_a", "warn_b"]),
                    ),
                ],
            ),
        ])
        report = build_report(tree)
        s008 = next(r for r in report.structural if r.id == "S008")
        assert s008.status == "pass"
        assert s008.data["count"] == 2
