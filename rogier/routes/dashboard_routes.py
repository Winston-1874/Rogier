"""Route du dashboard (page d'accueil)."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from rogier.dependencies import AuthDep, ConfigDep, TemplatesDep
from rogier.parsing.tree import NodeKind
from rogier.storage.documents import list_documents

logger = logging.getLogger(__name__)

router = APIRouter()


def _count_articles(node) -> int:
    """Compter récursivement les articles dans un arbre."""
    count = 0
    if node.kind == NodeKind.ARTICLE:
        count = 1
    for child in node.children:
        count += _count_articles(child)
    return count


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    config: ConfigDep,
    templates: TemplatesDep,
    csrf_token: AuthDep,
) -> HTMLResponse:
    """Page d'accueil — liste des documents."""
    documents = list_documents(config.data_dir)

    doc_rows = []
    for doc in documents:
        doc_rows.append({
            "hash": doc.hash,
            "name": doc.name,
            "family": doc.family,
            "article_count": _count_articles(doc.tree),
            "created_at": doc.created_at,
        })

    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "documents": doc_rows,
            "csrf_token": csrf_token,
            "authenticated": True,
        },
    )
