"""Routes versioning : historique des versions et restauration."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from rogier.csrf import check_csrf_token
from rogier.dependencies import AuthDep, ConfigDep, TemplatesDep
from rogier.errors import StorageError
from rogier.storage.documents import load_document
from rogier.storage.versions import load_version, restore_version

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/document")


@router.get("/{doc_hash}/versions", response_class=HTMLResponse)
async def version_list(
    request: Request,
    doc_hash: str,
    config: ConfigDep,
    templates: TemplatesDep,
    csrf_token: AuthDep,
) -> HTMLResponse:
    """Afficher l'historique des versions du document."""
    doc = load_document(config.data_dir, doc_hash)

    # Charger les détails de chaque version (chronologie inverse)
    versions = []
    for vref in reversed(doc.versions):
        try:
            v = load_version(config.data_dir, vref.id)
            versions.append({
                "id": v.id,
                "created_at": v.created_at,
                "label": v.label,
                "note": v.note,
                "is_active": v.id == doc.current_version_id,
                "edits_count": len(v.config.manual_edits),
            })
        except StorageError:
            logger.warning("Version %s illisible, ignorée", vref.id)

    return templates.TemplateResponse(
        request,
        "versions.html",
        {
            "document": doc,
            "versions": versions,
            "csrf_token": csrf_token,
            "authenticated": True,
        },
    )


@router.post("/{doc_hash}/versions/{version_id}/restore")
async def version_restore(
    request: Request,
    doc_hash: str,
    version_id: str,
    config: ConfigDep,
    csrf_token: AuthDep,
    form_csrf: str = Form(None, alias="csrf_token"),
) -> RedirectResponse:
    """Restaurer une version antérieure (crée une nouvelle version)."""
    check_csrf_token(form_csrf, csrf_token)
    doc = load_document(config.data_dir, doc_hash)

    # Vérifier que la version source existe
    try:
        load_version(config.data_dir, version_id)
    except StorageError as exc:
        raise HTTPException(status_code=404, detail="Version introuvable.") from exc

    restore_version(config.data_dir, doc, version_id)
    return RedirectResponse(
        url=f"/document/{doc_hash}/versions", status_code=302,
    )
