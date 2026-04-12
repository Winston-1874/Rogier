"""Routes export : page export, téléchargement Markdown, manifest JSON."""

from __future__ import annotations

import json
import logging
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response

from rogier.chunking.export import export_manifest, export_markdown
from rogier.chunking.strategies import chunk_hybrid, chunk_per_article
from rogier.csrf import check_csrf_token
from rogier.dependencies import AuthDep, ConfigDep, TemplatesDep
from rogier.parsing.tree import ChunkingConfig, ValidationConfig
from rogier.storage import paths as storage_paths
from rogier.storage.documents import load_document
from rogier.storage.versions import load_version, save_version
from rogier.validation.report import build_report

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/document")


def _build_chunking_config(
    strategy: str,
    hybrid_threshold: int,
    max_chunk_size: int,
    include_breadcrumb: bool,
    include_node_titles: bool,
) -> ChunkingConfig:
    """Construire un ChunkingConfig à partir des paramètres du formulaire."""
    return ChunkingConfig(
        strategy=strategy,
        hybrid_threshold=hybrid_threshold,
        max_chunk_size=max_chunk_size,
        include_breadcrumb=include_breadcrumb,
        include_node_titles=include_node_titles,
    )


def _run_chunking(root, config, manual_edits):
    """Lancer la stratégie de chunking appropriée."""
    if config.strategy == "hybrid":
        return chunk_hybrid(root, config, manual_edits)
    return chunk_per_article(root, config, manual_edits)


@router.get("/{doc_hash}/export", response_class=HTMLResponse)
async def export_page(
    request: Request,
    doc_hash: str,
    config: ConfigDep,
    templates: TemplatesDep,
    csrf_token: AuthDep,
) -> HTMLResponse:
    """Page export avec prévisualisation (§9.8)."""
    doc = load_document(config.data_dir, doc_hash)

    # Version active pour overlay et config
    manual_edits: dict[str, str] = {}
    chunking_config = ChunkingConfig()
    validation_config = ValidationConfig()
    if doc.current_version_id:
        version = load_version(config.data_dir, doc.current_version_id)
        manual_edits = version.config.manual_edits
        chunking_config = version.config.chunking
        validation_config = version.config.validation

    # Preview avec la config par défaut
    chunks = _run_chunking(doc.tree, chunking_config, manual_edits)
    estimated_size = sum(len(c.content) for c in chunks)

    # Rapport de validation
    report = build_report(doc.tree, validation_config, manual_edits)

    return templates.TemplateResponse(
        request,
        "step_export.html",
        {
            "document": doc,
            "strategy": chunking_config.strategy,
            "hybrid_threshold": chunking_config.hybrid_threshold,
            "max_chunk_size": chunking_config.max_chunk_size,
            "include_breadcrumb": chunking_config.include_breadcrumb,
            "include_node_titles": chunking_config.include_node_titles,
            "total_chunks": len(chunks),
            "estimated_size": estimated_size,
            "validation_config": validation_config,
            "report": report,
            "csrf_token": csrf_token,
            "authenticated": True,
        },
    )


@router.post("/{doc_hash}/export")
async def export_download(
    request: Request,
    doc_hash: str,
    config: ConfigDep,
    csrf_token: AuthDep,
    form_csrf: str = Form(None, alias="csrf_token"),
    strategy: str = Form("per_article"),
    hybrid_threshold: int = Form(2000),
    max_chunk_size: int = Form(5000),
    include_breadcrumb: str = Form(""),
    include_node_titles: str = Form(""),
) -> Response:
    """Générer et télécharger le fichier Markdown (§10.6)."""
    check_csrf_token(form_csrf, csrf_token)

    if strategy not in ("per_article", "hybrid"):
        raise HTTPException(status_code=400, detail="Stratégie inconnue.")

    # Clamp paramètres numériques (utilisateur authentifié, mais prudence)
    hybrid_threshold = max(100, min(50_000, hybrid_threshold))
    max_chunk_size = max(500, min(100_000, max_chunk_size))

    doc = load_document(config.data_dir, doc_hash)

    manual_edits: dict[str, str] = {}
    version = None
    if doc.current_version_id:
        version = load_version(config.data_dir, doc.current_version_id)
        manual_edits = version.config.manual_edits

    # Checkboxes : présentes = "1", absentes = ""
    chunking_config = _build_chunking_config(
        strategy=strategy,
        hybrid_threshold=hybrid_threshold,
        max_chunk_size=max_chunk_size,
        include_breadcrumb=bool(include_breadcrumb),
        include_node_titles=bool(include_node_titles),
    )

    chunks = _run_chunking(doc.tree, chunking_config, manual_edits)

    # Fallback version pour l'export
    if version is None:
        from rogier.parsing.tree import DocumentConfig
        from rogier.parsing.tree import Version as VersionModel
        version = VersionModel(
            id="no-version",
            document_hash=doc.hash,
            created_at="",
            label="",
            config=DocumentConfig(chunking=chunking_config),
        )

    from datetime import UTC, datetime
    exported_at = datetime.now(tz=UTC)

    md_content = export_markdown(doc, version, chunks, exported_at=exported_at)

    # Rapport de validation pour le manifest
    validation_config = version.config.validation
    report = build_report(doc.tree, validation_config, manual_edits)

    # Stocker le manifest
    manifest = export_manifest(
        doc, version, chunks, chunking_config,
        exported_at=exported_at, validation_report=report,
    )
    exp_dir = storage_paths.exports_dir(config.data_dir, doc_hash)
    exp_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = exp_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # Nom du fichier téléchargé (RFC 6266 / RFC 5987)
    filename = f"{doc.name[:60]}.md"
    filename_encoded = quote(filename)

    return Response(
        content=md_content,
        media_type="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": (
                f"attachment; filename*=UTF-8''{filename_encoded}"
            ),
        },
    )


@router.post("/{doc_hash}/export/validation")
async def save_validation_config(
    request: Request,
    doc_hash: str,
    config: ConfigDep,
    csrf_token: AuthDep,
    form_csrf: str = Form(None, alias="csrf_token"),
    must_contain: str = Form(""),
    must_not_contain: str = Form(""),
) -> RedirectResponse:
    """Sauvegarder les invariants sémantiques et recharger la page export.

    Mute la ValidationConfig de la version active sans créer de nouvelle
    version — la ValidationConfig est une configuration d'affichage,
    pas du contenu versionnable (cohérent avec l'approche append-only
    du projet pour le contenu uniquement).
    """
    check_csrf_token(form_csrf, csrf_token)

    doc = load_document(config.data_dir, doc_hash)
    if not doc.current_version_id:
        raise HTTPException(status_code=400, detail="Aucune version active.")

    version = load_version(config.data_dir, doc.current_version_id)

    # Parser les listes (une entrée par ligne, ignorer les lignes vides)
    mc = [s.strip() for s in must_contain.splitlines() if s.strip()]
    mnc = [s.strip() for s in must_not_contain.splitlines() if s.strip()]

    version.config.validation = ValidationConfig(
        must_contain=mc,
        must_not_contain=mnc,
    )
    save_version(config.data_dir, version)

    return RedirectResponse(
        url=f"/document/{doc_hash}/export",
        status_code=302,
    )


@router.get("/{doc_hash}/export/manifest")
async def export_manifest_view(
    request: Request,
    doc_hash: str,
    config: ConfigDep,
    csrf_token: AuthDep,
) -> JSONResponse:
    """Consulter le dernier manifest d'export (§10.6)."""
    exp_dir = storage_paths.exports_dir(config.data_dir, doc_hash)
    manifest_path = exp_dir / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Aucun export disponible pour ce document.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return JSONResponse(manifest)
