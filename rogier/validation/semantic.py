"""Invariants sémantiques (niveau 2) — SPEC §11.2.

Vérifie les contraintes must_contain / must_not_contain sur le texte
concaténé de tous les articles (contenu effectif après overlay).
Les comparaisons sont littérales (pas de regex en v0.1).
"""

from __future__ import annotations

from rogier.overlay import get_effective_content, walk_articles
from rogier.parsing.tree import Node, ValidationConfig


def run_semantic(
    root: Node,
    validation_config: ValidationConfig,
    manual_edits: dict[str, str] | None = None,
) -> list[dict]:
    """Exécuter les invariants sémantiques et retourner les résultats.

    Concatène le contenu effectif de tous les articles, puis vérifie
    chaque entrée must_contain et must_not_contain.
    """
    if manual_edits is None:
        manual_edits = {}

    # Concaténer le texte de tous les articles
    full_text = _build_full_text(root, manual_edits)
    results: list[dict] = []

    for needle in validation_config.must_contain:
        inv_id = f"must_contain:{needle}"
        if needle in full_text:
            results.append(
                {
                    "id": inv_id,
                    "level": 2,
                    "description": f"Le texte doit contenir « {needle} »",
                    "status": "pass",
                    "detail": f"« {needle} » trouvé dans le document.",
                }
            )
        else:
            results.append(
                {
                    "id": inv_id,
                    "level": 2,
                    "description": f"Le texte doit contenir « {needle} »",
                    "status": "fail",
                    "detail": f"« {needle} » absent du document.",
                }
            )

    for needle in validation_config.must_not_contain:
        inv_id = f"must_not_contain:{needle}"
        if needle not in full_text:
            results.append(
                {
                    "id": inv_id,
                    "level": 2,
                    "description": f"Le texte ne doit pas contenir « {needle} »",
                    "status": "pass",
                    "detail": f"« {needle} » absent du document (attendu).",
                }
            )
        else:
            results.append(
                {
                    "id": inv_id,
                    "level": 2,
                    "description": f"Le texte ne doit pas contenir « {needle} »",
                    "status": "fail",
                    "detail": f"« {needle} » trouvé dans le document (interdit).",
                }
            )

    return results


def _build_full_text(
    root: Node,
    manual_edits: dict[str, str],
) -> str:
    """Concaténer le contenu effectif de tous les articles."""
    parts: list[str] = []
    for article, path in walk_articles(root):
        parts.append(get_effective_content(article, path, manual_edits))
    return "\n".join(parts)
