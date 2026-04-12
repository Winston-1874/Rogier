"""Tests des invariants structurels (S001–S008)."""

from rogier.parsing.tree import Node, NodeKind, NodeMetadata
from rogier.validation.structural import (
    check_s001,
    check_s002,
    check_s003,
    check_s004,
    check_s005,
    check_s006,
    check_s007,
    check_s008,
    collect_all_warnings,
    run_structural,
)

# ---------------------------------------------------------------------------
# Helpers pour construire des arbres de test
# ---------------------------------------------------------------------------


def _article(number: str, content: str, warnings: list[str] | None = None) -> Node:
    meta = NodeMetadata(warnings=warnings or [])
    return Node(kind=NodeKind.ARTICLE, number=number, content=content, metadata=meta)


def _container(kind: NodeKind, number: str, children: list[Node]) -> Node:
    return Node(kind=kind, number=number, children=children)


def _doc(children: list[Node], warnings: list[str] | None = None) -> Node:
    meta = NodeMetadata(warnings=warnings or [])
    return Node(kind=NodeKind.DOCUMENT, title="Test", children=children, metadata=meta)


def _simple_tree() -> Node:
    """Arbre simple : DOC > CHAPITRE > 3 articles."""
    return _doc(
        [
            _container(
                NodeKind.CHAPITRE,
                "1",
                [
                    _article("1", "Contenu de l'article premier suffisamment long."),
                    _article("2", "Contenu de l'article deux suffisamment long aussi."),
                    _article("3", "Contenu du troisième article pour les tests."),
                ],
            ),
        ]
    )


# ---------------------------------------------------------------------------
# S001 — Au moins 1 article
# ---------------------------------------------------------------------------


class TestS001:
    def test_pass(self):
        result = check_s001(_simple_tree(), {})
        assert result["status"] == "pass"
        assert result["id"] == "S001"

    def test_fail_empty_tree(self):
        tree = _doc([_container(NodeKind.CHAPITRE, "1", [])])
        result = check_s001(tree, {})
        assert result["status"] == "fail"


# ---------------------------------------------------------------------------
# S002 — Articles non vides
# ---------------------------------------------------------------------------


class TestS002:
    def test_pass(self):
        result = check_s002(_simple_tree(), {})
        assert result["status"] == "pass"

    def test_fail_empty_article(self):
        tree = _doc(
            [
                _container(
                    NodeKind.CHAPITRE,
                    "1",
                    [
                        _article("1", ""),
                    ],
                ),
            ]
        )
        result = check_s002(tree, {})
        assert result["status"] == "fail"
        assert "Art. 1" in result["detail"]

    def test_overlay_fixes_empty(self):
        """Un article vide corrigé par manual_edits → pass."""
        tree = _doc(
            [
                _container(
                    NodeKind.CHAPITRE,
                    "1",
                    [
                        _article("1", ""),
                    ],
                ),
            ]
        )
        edits = {"0.0": "Contenu ajouté par édition manuelle."}
        result = check_s002(tree, edits)
        assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# S003 — Longueur minimale (≥ 20 car.)
# ---------------------------------------------------------------------------


class TestS003:
    def test_pass(self):
        result = check_s003(_simple_tree(), {})
        assert result["status"] == "pass"

    def test_fail_short_article(self):
        tree = _doc(
            [
                _container(
                    NodeKind.CHAPITRE,
                    "1",
                    [
                        _article("1", "Court."),
                    ],
                ),
            ]
        )
        result = check_s003(tree, {})
        assert result["status"] == "fail"

    def test_empty_article_not_flagged(self):
        """Un article vide n'est PAS flaggé par S003 (c'est S002)."""
        tree = _doc(
            [
                _container(
                    NodeKind.CHAPITRE,
                    "1",
                    [
                        _article("1", ""),
                    ],
                ),
            ]
        )
        result = check_s003(tree, {})
        assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# S004 — Longueur maximale (≤ 20 000 car.)
# ---------------------------------------------------------------------------


class TestS004:
    def test_pass(self):
        result = check_s004(_simple_tree(), {})
        assert result["status"] == "pass"

    def test_fail_long_article(self):
        tree = _doc(
            [
                _container(
                    NodeKind.CHAPITRE,
                    "1",
                    [
                        _article("1", "x" * 20_001),
                    ],
                ),
            ]
        )
        result = check_s004(tree, {})
        assert result["status"] == "fail"


# ---------------------------------------------------------------------------
# S005 — Numérotation monotone
# ---------------------------------------------------------------------------


class TestS005:
    def test_pass_simple(self):
        result = check_s005(_simple_tree(), {})
        assert result["status"] == "pass"

    def test_pass_with_bis_ter(self):
        """2, 2bis, 2ter, 3 est monotone (partie entière : 2, 2, 2, 3)."""
        tree = _doc(
            [
                _container(
                    NodeKind.CHAPITRE,
                    "1",
                    [
                        _article("2", "Contenu suffisamment long pour le test."),
                        _article("2bis", "Contenu suffisamment long pour le test."),
                        _article("2ter", "Contenu suffisamment long pour le test."),
                        _article("3", "Contenu suffisamment long pour le test."),
                    ],
                ),
            ]
        )
        result = check_s005(tree, {})
        assert result["status"] == "pass"

    def test_fail_bis_after_higher(self):
        """2, 3, 2bis → fail (le bis arrive après le 3)."""
        tree = _doc(
            [
                _container(
                    NodeKind.CHAPITRE,
                    "1",
                    [
                        _article("2", "Contenu suffisamment long pour le test."),
                        _article("3", "Contenu suffisamment long pour le test."),
                        _article("2bis", "Contenu suffisamment long pour le test."),
                    ],
                ),
            ]
        )
        result = check_s005(tree, {})
        assert result["status"] == "fail"

    def test_fail_decreasing(self):
        tree = _doc(
            [
                _container(
                    NodeKind.CHAPITRE,
                    "1",
                    [
                        _article("5", "Contenu suffisamment long pour le test."),
                        _article("3", "Contenu suffisamment long pour le test."),
                    ],
                ),
            ]
        )
        result = check_s005(tree, {})
        assert result["status"] == "fail"

    def test_monotone_per_container(self):
        """La monotonie est vérifiée par conteneur, pas globalement."""
        tree = _doc(
            [
                _container(
                    NodeKind.CHAPITRE,
                    "1",
                    [
                        _article("1", "Contenu suffisamment long pour le test."),
                        _article("2", "Contenu suffisamment long pour le test."),
                    ],
                ),
                _container(
                    NodeKind.CHAPITRE,
                    "2",
                    [
                        _article("1", "Contenu suffisamment long pour le test."),
                        _article("2", "Contenu suffisamment long pour le test."),
                    ],
                ),
            ]
        )
        result = check_s005(tree, {})
        assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# S006 — Pas de doublons d'identifiants
# ---------------------------------------------------------------------------


class TestS006:
    def test_pass(self):
        result = check_s006(_simple_tree(), {})
        assert result["status"] == "pass"

    def test_fail_duplicate(self):
        tree = _doc(
            [
                _container(
                    NodeKind.CHAPITRE,
                    "1",
                    [
                        _article("1", "Contenu suffisamment long pour le test."),
                        _article("1", "Autre contenu suffisamment long pour le test."),
                    ],
                ),
            ]
        )
        result = check_s006(tree, {})
        assert result["status"] == "fail"
        assert "Art. 1" in result["detail"]


# ---------------------------------------------------------------------------
# S007 — Profondeur maximale ≤ 7
# ---------------------------------------------------------------------------


class TestS007:
    def test_pass(self):
        result = check_s007(_simple_tree(), {})
        assert result["status"] == "pass"

    def test_fail_too_deep(self):
        """Arbre de profondeur 8 : DOC > 7 niveaux imbriqués."""
        node = _article("1", "Contenu suffisamment long pour le test.")
        for i in range(7):
            node = _container(NodeKind.SECTION, str(i), [node])
        tree = _doc([node])
        result = check_s007(tree, {})
        assert result["status"] == "fail"
        assert "8" in result["detail"]

    def test_pass_at_limit(self):
        """Profondeur exactement 7 → pass."""
        node = _article("1", "Contenu suffisamment long pour le test.")
        for i in range(6):
            node = _container(NodeKind.SECTION, str(i), [node])
        tree = _doc([node])
        result = check_s007(tree, {})
        assert result["status"] == "pass"


# ---------------------------------------------------------------------------
# S008 — Warnings de parsing référencés
# ---------------------------------------------------------------------------


class TestS008:
    def test_pass_no_warnings(self):
        result = check_s008(_simple_tree(), {})
        assert result["status"] == "pass"
        assert "Aucun warning" in result["detail"]

    def test_pass_with_warnings(self):
        tree = _doc(
            [
                _container(
                    NodeKind.CHAPITRE,
                    "1",
                    [
                        _article("1", "Contenu long", warnings=["Contenu court"]),
                        _article("2", "Contenu long aussi", warnings=["Titre tronqué"]),
                    ],
                ),
            ]
        )
        result = check_s008(tree, {})
        assert result["status"] == "pass"
        assert "2 warning" in result["detail"]

    def test_collect_all_warnings_complete(self):
        """collect_all_warnings récupère les warnings de tous les nœuds."""
        tree = _doc(
            [
                _container(
                    NodeKind.CHAPITRE,
                    "1",
                    [
                        _article("1", "Contenu", warnings=["warn_a"]),
                    ],
                ),
            ],
            warnings=["warn_root"],
        )
        warnings = collect_all_warnings(tree)
        assert "warn_a" in warnings
        assert "warn_root" in warnings
        assert len(warnings) == 2

    def test_data_count_field(self):
        """S008 retourne un champ data.count structuré."""
        tree = _doc(
            [
                _container(
                    NodeKind.CHAPITRE,
                    "1",
                    [
                        _article("1", "Contenu long", warnings=["w1", "w2"]),
                    ],
                ),
            ]
        )
        result = check_s008(tree, {})
        assert result["data"]["count"] == 2

    def test_data_count_zero(self):
        result = check_s008(_simple_tree(), {})
        assert result["data"]["count"] == 0


# ---------------------------------------------------------------------------
# run_structural — API publique
# ---------------------------------------------------------------------------


class TestRunStructural:
    def test_all_pass_on_simple_tree(self):
        results = run_structural(_simple_tree())
        assert len(results) == 8
        assert all(r["status"] == "pass" for r in results)

    def test_ids_are_s001_to_s008(self):
        results = run_structural(_simple_tree())
        ids = [r["id"] for r in results]
        assert ids == [f"S00{i}" for i in range(1, 9)]
