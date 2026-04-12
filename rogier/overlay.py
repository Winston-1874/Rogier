"""Overlay des modifications manuelles sur l'arbre de nœuds.

Module partagé entre le chunker, la validation structurelle et la
validation sémantique. Centralise la logique d'application des
manual_edits pour éviter toute duplication.
"""

from __future__ import annotations

from rogier.parsing.tree import Node, NodeKind


def get_effective_content(
    node: Node,
    node_path: str,
    manual_edits: dict[str, str],
) -> str:
    """Contenu effectif d'un article après overlay manual_edits.

    Pour un ARTICLE, retourne le contenu modifié s'il existe dans
    manual_edits, sinon le contenu original.
    """
    if node_path in manual_edits:
        return manual_edits[node_path]
    return node.content


def get_effective_title(
    node: Node,
    node_path: str,
    manual_edits: dict[str, str],
) -> str:
    """Titre effectif d'un conteneur après overlay manual_edits.

    Pour un conteneur (non-ARTICLE), retourne le titre modifié
    s'il existe dans manual_edits, sinon le titre original.
    """
    if node_path in manual_edits:
        return manual_edits[node_path]
    return node.title


def walk_articles(
    node: Node,
    current_path: str = "",
) -> list[tuple[Node, str]]:
    """Parcourir l'arbre et collecter tous les articles avec leur chemin."""
    results: list[tuple[Node, str]] = []
    for i, child in enumerate(node.children):
        child_path = f"{current_path}.{i}" if current_path else str(i)
        if child.kind == NodeKind.ARTICLE:
            results.append((child, child_path))
        else:
            results.extend(walk_articles(child, child_path))
    return results


def walk_descendants(
    node: Node,
    current_path: str = "",
) -> list[tuple[Node, str]]:
    """Parcourir l'arbre et collecter tous les nœuds avec leur chemin."""
    results: list[tuple[Node, str]] = []
    for i, child in enumerate(node.children):
        child_path = f"{current_path}.{i}" if current_path else str(i)
        results.append((child, child_path))
        results.extend(walk_descendants(child, child_path))
    return results
