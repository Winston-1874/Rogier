"""Routes document : affichage arbre, redirect, suppression."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from rogier.csrf import check_csrf_token
from rogier.dependencies import AuthDep, ConfigDep, TemplatesDep
from rogier.parsing.tree import Node, NodeKind
from rogier.storage.documents import delete_document, load_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/document")


def _find_node_by_path(root: Node, path: str) -> Node | None:
    """Trouver un noeud par son chemin d'index (ex: '0', '0.2', '0.2.1')."""
    if not path:
        return root

    parts = path.split(".")
    current = root
    for part in parts:
        try:
            idx = int(part)
        except ValueError:
            return None
        if idx < 0 or idx >= len(current.children):
            return None
        current = current.children[idx]
    return current


def _build_breadcrumb(root: Node, path: str) -> list[dict[str, str]]:
    """Construire le fil d'Ariane depuis la racine jusqu'au noeud cible."""
    crumbs = [{"label": root.label, "path": ""}]
    if not path:
        return crumbs

    parts = path.split(".")
    current = root
    for i, part in enumerate(parts):
        idx = int(part)
        current = current.children[idx]
        crumbs.append({
            "label": current.label,
            "path": ".".join(parts[: i + 1]),
        })
    return crumbs


def _build_tree_data(node: Node, current_path: str = "") -> list[dict]:
    """Construire la structure de données pour le rendu de l'arbre en template.

    Chaque noeud a : label, title, kind, path, has_children, children,
    has_warnings, is_article, depth.
    """
    items = []
    for i, child in enumerate(node.children):
        child_path = f"{current_path}.{i}" if current_path else str(i)
        item = {
            "label": child.label,
            "title": child.title,
            "kind": child.kind.value,
            "path": child_path,
            "has_children": len(child.children) > 0,
            "has_warnings": len(child.metadata.warnings) > 0,
            "is_article": child.kind == NodeKind.ARTICLE,
            "depth": child_path.count("."),
            "children": _build_tree_data(child, child_path),
        }
        items.append(item)
    return items


def _count_by_kind(node: Node) -> dict[str, int]:
    """Compter les noeuds par kind dans l'arbre."""
    counts: dict[str, int] = {}
    kind_key = node.kind.value
    counts[kind_key] = counts.get(kind_key, 0) + 1
    for child in node.children:
        for k, v in _count_by_kind(child).items():
            counts[k] = counts.get(k, 0) + v
    return counts


@router.get("/{doc_hash}")
async def document_redirect(doc_hash: str) -> RedirectResponse:
    """Rediriger vers l'affichage arbre du document."""
    return RedirectResponse(url=f"/document/{doc_hash}/tree", status_code=302)


@router.get("/{doc_hash}/tree", response_class=HTMLResponse)
async def document_tree(
    request: Request,
    doc_hash: str,
    config: ConfigDep,
    templates: TemplatesDep,
    csrf_token: AuthDep,
    node: str = "",
    warnings: str = "",
) -> HTMLResponse:
    """Afficher l'arbre du document avec le noeud selectionne."""
    doc = load_document(config.data_dir, doc_hash)

    # Noeud sélectionné
    selected_node = _find_node_by_path(doc.tree, node)
    if selected_node is None:
        raise HTTPException(status_code=404, detail="Noeud introuvable.")

    breadcrumb = _build_breadcrumb(doc.tree, node)
    tree_data = _build_tree_data(doc.tree)
    counts = _count_by_kind(doc.tree)

    return templates.TemplateResponse(
        request,
        "step_tree.html",
        {
            "document": doc,
            "tree_data": tree_data,
            "selected_node": selected_node,
            "selected_path": node,
            "breadcrumb": breadcrumb,
            "counts": counts,
            "show_warnings_banner": warnings == "1",
            "csrf_token": csrf_token,
            "authenticated": True,
        },
    )


@router.post("/{doc_hash}/delete")
async def document_delete(
    request: Request,
    doc_hash: str,
    config: ConfigDep,
    csrf_token: AuthDep,
    form_csrf: str = Form(None, alias="csrf_token"),
) -> RedirectResponse:
    """Supprimer un document et rediriger vers le dashboard."""
    check_csrf_token(form_csrf, csrf_token)
    delete_document(config.data_dir, doc_hash)
    return RedirectResponse(url="/", status_code=302)
