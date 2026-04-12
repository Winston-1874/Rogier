"""Stratégies de chunking pour l'export de documents législatifs.

Deux stratégies conformes au §10.1 et §10.2 du SPEC :
- per_article : un chunk par article, sans découpage.
- hybrid : articles courts intacts, articles longs découpés par paragraphes §.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rogier.chunking.breadcrumb import build_breadcrumb
from rogier.overlay import get_effective_content, walk_articles
from rogier.parsing.tree import ChunkingConfig, Node

# Regex §10.2 : détection des paragraphes numérotés dans un article
_RE_PARAGRAPH = re.compile(
    r"^(§\s*\d+(?:er|bis|ter|quater)?)\.\s*",
    re.MULTILINE,
)


@dataclass
class Chunk:
    """Un chunk exportable — artefact transitoire, pas persisté."""

    breadcrumb: str
    content: str
    warnings: list[str] = field(default_factory=list)


def _collect_path_to_node(
    root: Node,
    target_path: str,
) -> list[Node]:
    """Reconstituer le chemin (liste de nœuds) depuis la racine jusqu'au nœud."""
    path_nodes = [root]
    current = root
    if target_path:
        for part in target_path.split("."):
            idx = int(part)
            current = current.children[idx]
            path_nodes.append(current)
    return path_nodes


def _get_article_content(
    node: Node,
    node_path: str,
    manual_edits: dict[str, str],
) -> str:
    """Récupérer le contenu d'un article en appliquant l'overlay manual_edits."""
    return get_effective_content(node, node_path, manual_edits)


def chunk_per_article(
    root: Node,
    config: ChunkingConfig,
    manual_edits: dict[str, str] | None = None,
) -> list[Chunk]:
    """Stratégie 1 (§10.1) : un chunk par article.

    Chaque article devient un chunk avec breadcrumb en Markdown gras.
    """
    if manual_edits is None:
        manual_edits = {}

    levels_filter = config.breadcrumb_levels or None
    chunks: list[Chunk] = []

    for article, article_path in walk_articles(root):
        content = _get_article_content(article, article_path, manual_edits)
        if config.include_breadcrumb:
            path_nodes = _collect_path_to_node(root, article_path)
            bc = build_breadcrumb(
                path_nodes,
                include_titles=config.include_node_titles,
                levels_filter=levels_filter,
            )
            chunks.append(Chunk(breadcrumb=bc, content=content))
        else:
            chunks.append(Chunk(breadcrumb="", content=content))

    return chunks


def chunk_hybrid(
    root: Node,
    config: ChunkingConfig,
    manual_edits: dict[str, str] | None = None,
) -> list[Chunk]:
    """Stratégie 2 (§10.2) : chunking hybride.

    Articles courts → un chunk. Articles longs → découpés par paragraphes §.
    """
    if manual_edits is None:
        manual_edits = {}

    levels_filter = config.breadcrumb_levels or None
    chunks: list[Chunk] = []

    for article, article_path in walk_articles(root):
        content = _get_article_content(article, article_path, manual_edits)
        path_nodes = _collect_path_to_node(root, article_path)

        if config.include_breadcrumb:
            bc = build_breadcrumb(
                path_nodes,
                include_titles=config.include_node_titles,
                levels_filter=levels_filter,
            )
        else:
            bc = ""

        # Article court → un seul chunk
        if len(content) <= config.hybrid_threshold:
            chunks.append(Chunk(breadcrumb=bc, content=content))
            continue

        # Article long → tenter de découper par paragraphes §
        splits = list(_RE_PARAGRAPH.finditer(content))
        if not splits:
            # Pas de paragraphes détectés — un seul chunk + warning
            warnings = [
                f"Article {article.number} dépasse le seuil hybride "
                f"({len(content)} car.) mais n'a pas de paragraphes §."
            ]
            chunks.append(Chunk(breadcrumb=bc, content=content, warnings=warnings))
            continue

        # Découper par paragraphes — liste locale puis extend
        article_chunks: list[Chunk] = []

        # Texte avant le premier § (intro)
        intro = content[: splits[0].start()].strip()
        if intro:
            article_chunks.append(Chunk(breadcrumb=bc, content=intro))

        for j, match in enumerate(splits):
            para_start = match.start()
            para_end = splits[j + 1].start() if j + 1 < len(splits) else len(content)
            para_content = content[para_start:para_end].rstrip()
            para_label = match.group(1)  # ex: "§ 1er"

            sub_bc = f"{bc} > {para_label}" if bc else para_label

            para_warnings: list[str] = []
            if len(para_content) > config.max_chunk_size:
                para_warnings.append(
                    f"Paragraphe {para_label} de l'article {article.number} "
                    f"dépasse la taille max ({len(para_content)} car.)."
                )

            article_chunks.append(
                Chunk(
                    breadcrumb=sub_bc,
                    content=para_content,
                    warnings=para_warnings,
                )
            )

        chunks.extend(article_chunks)

    return chunks
