"""Routes d'upload : formulaire et traitement (fichier local ou URL Justel)."""

from __future__ import annotations

import logging
import os
import tempfile

from fastapi import APIRouter, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

from rogier.csrf import check_csrf_token
from rogier.dependencies import AuthDep, ConfigDep, TemplatesDep
from rogier.errors import JustelFetchError, JustelParseError
from rogier.extraction.justel_html import parse_justel_html
from rogier.fetching.justel_fetcher import fetch_justel_url, validate_justel_url
from rogier.parsing.tree import Document
from rogier.storage import paths as storage_paths
from rogier.storage.documents import compute_hash, document_exists, save_document
from rogier.storage.versions import create_initial_version

logger = logging.getLogger(__name__)

router = APIRouter()

# Marqueurs attendus dans un HTML Justel valide (SPEC §9.5)
_REQUIRED_MARKERS = ("change_lg.pl", "list-title-2")

# Encodings à essayer pour les fichiers Justel téléchargés
_JUSTEL_ENCODINGS = ("utf-8", "windows-1252", "iso-8859-1")


def _decode_html(raw_bytes: bytes) -> str:
    """Décoder du HTML Justel en essayant plusieurs encodings.

    Justel sert nativement en windows-1252. Un fichier sauvegardé
    par le navigateur peut être en UTF-8 (re-encodé) ou en
    windows-1252 original.
    """
    for encoding in _JUSTEL_ENCODINGS:
        try:
            return raw_bytes.decode(encoding)
        except (UnicodeDecodeError, ValueError):
            continue
    # Dernier recours
    return raw_bytes.decode("utf-8", errors="replace")


@router.get("/upload", response_class=HTMLResponse)
async def upload_page(
    request: Request,
    config: ConfigDep,
    templates: TemplatesDep,
    csrf_token: AuthDep,
) -> HTMLResponse:
    """Afficher le formulaire d'upload."""
    return templates.TemplateResponse(
        request,
        "step_upload.html",
        {
            "error": None,
            "csrf_token": csrf_token,
            "authenticated": True,
            "max_upload_mb": config.max_upload_mb,
        },
    )


@router.post("/upload", response_class=HTMLResponse)
async def upload_submit(
    request: Request,
    config: ConfigDep,
    templates: TemplatesDep,
    csrf_token: AuthDep,
    form_csrf: str = Form(None, alias="csrf_token"),
    upload_mode: str = Form(...),
    justel_url: str = Form(""),
    html_file: UploadFile | None = None,
) -> HTMLResponse:
    """Traiter l'upload (fichier ou URL)."""
    check_csrf_token(form_csrf, csrf_token)

    error = None
    raw_bytes: bytes | None = None
    source_url: str | None = None
    source_filename: str | None = None

    if upload_mode == "url":
        raw_bytes, source_url, error = await _handle_url_upload(
            justel_url, config,
        )
    elif upload_mode == "file":
        raw_bytes, source_filename, error = await _handle_file_upload(
            html_file, config,
        )
    else:
        error = "Mode d'upload non reconnu."

    if error:
        return templates.TemplateResponse(
            request,
            "step_upload.html",
            {
                "error": error,
                "csrf_token": csrf_token,
                "authenticated": True,
                "max_upload_mb": config.max_upload_mb,
            },
        )

    # À ce point, raw_bytes est garanti non-None
    assert raw_bytes is not None

    # Déduplication (§8.5) : si le même contenu existe déjà, rediriger
    doc_hash = compute_hash(raw_bytes)
    if document_exists(config.data_dir, doc_hash):
        return RedirectResponse(
            url=f"/document/{doc_hash}/tree",
            status_code=302,
        )

    # Parser le HTML
    html_str = raw_bytes.decode("utf-8", errors="replace")
    try:
        tree, report = parse_justel_html(html_str)
    except JustelParseError as e:
        return templates.TemplateResponse(
            request,
            "step_upload.html",
            {
                "error": f"Le document n'a pas pu etre analyse : {e.message}",
                "csrf_token": csrf_token,
                "authenticated": True,
                "max_upload_mb": config.max_upload_mb,
            },
        )

    # Sauvegarder le HTML brut (écriture atomique : tmpfile + fsync + rename)
    raw_path = storage_paths.raw_html_path(config.data_dir, doc_hash)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_name = tempfile.mkstemp(
        prefix=f".{raw_path.name}.",
        suffix=".tmp",
        dir=str(raw_path.parent),
    )
    try:
        os.write(tmp_fd, raw_bytes)
        os.fsync(tmp_fd)
    finally:
        os.close(tmp_fd)
    os.replace(tmp_name, str(raw_path))

    # Créer le Document
    from datetime import UTC, datetime

    doc = Document(
        hash=doc_hash,
        name=tree.title or "Document",
        source_url=source_url,
        source_filename=source_filename,
        created_at=datetime.now(UTC).isoformat(),
        family="justel_html",
        tree=tree,
        raw_html_path=str(raw_path),
    )
    save_document(config.data_dir, doc)
    create_initial_version(config.data_dir, doc)

    # Redirect avec indicateur de warnings si nécessaire
    redirect_url = f"/document/{doc_hash}/tree"
    if report.warnings:
        redirect_url += "?warnings=1"
    return RedirectResponse(url=redirect_url, status_code=302)


async def _handle_url_upload(
    url: str,
    config,
) -> tuple[bytes | None, str | None, str | None]:
    """Traiter un upload par URL. Retourne (raw_bytes, source_url, error)."""
    if not url.strip():
        return None, None, "Veuillez saisir une URL."

    try:
        validate_justel_url(url.strip())
    except JustelFetchError as e:
        return None, None, e.message

    try:
        result = await fetch_justel_url(
            url.strip(),
            data_dir=config.data_dir,
            contact_url=config.contact_url,
            contact_email=config.contact_email,
        )
    except JustelFetchError as e:
        return None, None, e.message

    return result.html.encode("utf-8"), url.strip(), None


async def _handle_file_upload(
    html_file: UploadFile | None,
    config,
) -> tuple[bytes | None, str | None, str | None]:
    """Traiter un upload par fichier. Retourne (raw_bytes, filename, error)."""
    if html_file is None or html_file.filename == "":
        return None, None, "Veuillez selectionner un fichier HTML."

    max_bytes = config.max_upload_mb * 1024 * 1024
    raw_bytes = await html_file.read()

    if len(raw_bytes) > max_bytes:
        return (
            None,
            None,
            f"Le fichier depasse la taille maximale autorisee ({config.max_upload_mb} Mo).",
        )

    # Décoder le contenu — Justel sert du windows-1252 (§6)
    content = _decode_html(raw_bytes)

    # Vérifier les marqueurs Justel
    for marker in _REQUIRED_MARKERS:
        if marker not in content:
            return (
                None,
                None,
                "Le fichier ne semble pas etre un document Justel valide. "
                "Verifiez qu'il s'agit bien d'une page HTML telechargee "
                "depuis ejustice.just.fgov.be.",
            )

    # Re-encoder en UTF-8 pour stockage uniforme
    return content.encode("utf-8"), html_file.filename, None
