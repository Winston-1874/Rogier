"""Construction du breadcrumb hiérarchique pour les chunks exportés.

Conforme au §10.3 du SPEC : le breadcrumb est une chaîne plate
"CSA > Livre 1er > Titre 1er > Art. 1:1" construite à partir du
chemin (liste de nœuds) depuis la racine jusqu'au nœud cible.
"""

from __future__ import annotations

from rogier.parsing.tree import Node


def build_breadcrumb(
    path: list[Node],
    *,
    include_titles: bool = True,
    levels_filter: list[str] | None = None,
) -> str:
    """Construire le breadcrumb d'un nœud à partir du chemin depuis la racine.

    Args:
        path: liste des nœuds de la racine jusqu'au nœud cible (inclus).
        include_titles: inclure les titres humains (ex: "Dispositions générales").
        levels_filter: kinds à inclure ; si None, tous les niveaux présents.

    Returns:
        Chaîne du type "CSA > Livre 1er > Titre 1er > Art. 1:1"
        ou "CSA > Livre 1er — Dispositions introductives > Art. 1:1".
    """
    parts: list[str] = []
    for node in path:
        if levels_filter is not None and node.kind.value not in levels_filter:
            continue
        segment = node.label
        if include_titles and node.title and segment != node.title:
            segment = f"{segment} — {node.title}"
        parts.append(segment)
    return " > ".join(parts)
