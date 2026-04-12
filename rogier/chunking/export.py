"""Export Markdown et manifest JSON pour les documents chunkés.

Conforme au §10.4 et §10.5 du SPEC.
"""

from __future__ import annotations

import statistics
from datetime import UTC, datetime
from typing import Any

from rogier.chunking.strategies import Chunk
from rogier.parsing.tree import ChunkingConfig, Document, Version


def export_markdown(
    doc: Document,
    version: Version,
    chunks: list[Chunk],
    *,
    exported_at: datetime | None = None,
) -> str:
    """Générer le fichier Markdown unique conforme au §10.4.

    Retourne le contenu complet du fichier .md.
    """
    strategy_label = {
        "per_article": "un chunk par article",
        "hybrid": "chunking hybride",
    }.get(version.config.chunking.strategy, version.config.chunking.strategy)

    now = exported_at or datetime.now(tz=UTC)
    date_str = now.strftime("%d/%m/%Y à %H:%M")

    lines: list[str] = []
    lines.append(f"# {doc.name}")
    lines.append("")
    lines.append("> Source : Justel (ejustice.just.fgov.be)")
    if doc.source_url:
        lines.append(f"> URL : {doc.source_url}")
    lines.append(f"> Nombre de chunks : {len(chunks)}")
    lines.append(f"> Stratégie : {strategy_label}")
    lines.append(f"> Exporté depuis Rogier v0.1 le {date_str}")
    lines.append("")

    for i, chunk in enumerate(chunks):
        lines.append("---")
        lines.append("")
        if chunk.breadcrumb:
            lines.append(f"**[{chunk.breadcrumb}]**")
            lines.append("")
        lines.append(chunk.content)
        if i < len(chunks) - 1:
            lines.append("")

    return "\n".join(lines) + "\n"


def export_manifest(
    doc: Document,
    version: Version,
    chunks: list[Chunk],
    config: ChunkingConfig,
    *,
    exported_at: datetime | None = None,
    validation_report: Any | None = None,
) -> dict[str, Any]:
    """Générer le manifest JSON conforme au §10.5.

    Retourne un dict sérialisable en JSON.
    Si validation_report (ValidationReport) est fourni, ses résultats
    remplacent les placeholders "pending".
    """
    sizes = [len(c.content) for c in chunks]

    stats: dict[str, Any]
    if sizes:
        stats = {
            "total_chunks": len(chunks),
            "min_chunk_size": min(sizes),
            "max_chunk_size": max(sizes),
            "avg_chunk_size": round(statistics.mean(sizes)),
            "median_chunk_size": round(statistics.median(sizes)),
        }
    else:
        stats = {
            "total_chunks": 0,
            "min_chunk_size": 0,
            "max_chunk_size": 0,
            "avg_chunk_size": 0,
            "median_chunk_size": 0,
        }

    # Collecter les warnings des chunks
    all_warnings: list[str] = []
    for chunk in chunks:
        all_warnings.extend(chunk.warnings)

    return {
        "document_hash": doc.hash,
        "document_name": doc.name,
        "source_url": doc.source_url,
        "exported_at": (exported_at or datetime.now(tz=UTC)).isoformat(),
        "exporter": "Rogier v0.1",
        "strategy": config.strategy,
        "parameters": {
            "hybrid_threshold": config.hybrid_threshold,
            "max_chunk_size": config.max_chunk_size,
            "include_breadcrumb": config.include_breadcrumb,
            "include_node_titles": config.include_node_titles,
        },
        "stats": stats,
        "version_id": version.id,
        "validation": _build_validation_block(
            validation_report, all_warnings,
        ),
    }


def _build_validation_block(
    report: Any | None,
    chunk_warnings: list[str],
) -> dict[str, Any]:
    """Construire le bloc validation du manifest."""
    if report is None:
        return {
            "overall": "not_run",
            "structural": [],
            "semantic": [],
            "chunk_warnings": chunk_warnings,
        }
    return {
        "overall": report.overall,
        "structural": [r.to_dict() for r in report.structural],
        "semantic": [r.to_dict() for r in report.semantic],
        "chunk_warnings": chunk_warnings,
    }
