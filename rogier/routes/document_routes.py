"""Routes document : affichage arbre, redirect, suppression."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from rogier.csrf import check_csrf_token
from rogier.dependencies import AuthDep, ConfigDep, TemplatesDep
from rogier.parsing.tree import Node, NodeKind
from rogier.storage import paths as storage_paths
from rogier.storage.documents import delete_document, load_document

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/document")


# ---------------------------------------------------------------------------
# Dismissed warnings (preferences UI par document)
# ---------------------------------------------------------------------------


def _load_dismissed(data_dir, doc_hash: str) -> list[str]:
    """Charger les types de warnings ignores pour un document."""
    path = storage_paths.dismissed_warnings_path(data_dir, doc_hash)
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def _save_dismissed(data_dir, doc_hash: str, dismissed: list[str]) -> None:
    """Sauvegarder les types de warnings ignores."""
    path = storage_paths.dismissed_warnings_path(data_dir, doc_hash)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dismissed, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Helpers arbre
# ---------------------------------------------------------------------------


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
    """Construire la structure pour le rendu de l'arbre en template."""
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


def _flatten_paths(node: Node, current_path: str = "") -> list[tuple[str, NodeKind]]:
    """Aplatir l'arbre en liste (path, kind) en ordre document."""
    result: list[tuple[str, NodeKind]] = []
    for i, child in enumerate(node.children):
        child_path = f"{current_path}.{i}" if current_path else str(i)
        result.append((child_path, child.kind))
        result.extend(_flatten_paths(child, child_path))
    return result


def _find_prev_next(
    root: Node, selected_path: str, selected_kind: NodeKind,
) -> tuple[str | None, str | None]:
    """Trouver les chemins precedent et suivant du meme kind."""
    flat = _flatten_paths(root)
    same_kind = [path for path, kind in flat if kind == selected_kind]
    if selected_path not in same_kind:
        return None, None
    idx = same_kind.index(selected_path)
    prev_path = same_kind[idx - 1] if idx > 0 else None
    next_path = same_kind[idx + 1] if idx < len(same_kind) - 1 else None
    return prev_path, next_path


def _collect_warning_nodes(
    node: Node,
    dismissed: list[str],
    current_path: str = "",
) -> list[dict]:
    """Collecter les noeuds avec warnings non ignores."""
    result: list[dict] = []
    for i, child in enumerate(node.children):
        child_path = f"{current_path}.{i}" if current_path else str(i)
        active_warnings = [
            w for w in child.metadata.warnings if w not in dismissed
        ]
        if active_warnings:
            result.append({
                "path": child_path,
                "label": child.label,
                "title": child.title,
                "warnings": active_warnings,
            })
        result.extend(_collect_warning_nodes(child, dismissed, child_path))
    return result


def _find_prev_next_warning(
    warning_nodes: list[dict], selected_path: str,
) -> tuple[str | None, str | None]:
    """Trouver le warning precedent et suivant par rapport au noeud courant."""
    paths = [wn["path"] for wn in warning_nodes]
    if not paths:
        return None, None
    if selected_path in paths:
        idx = paths.index(selected_path)
        prev_w = paths[idx - 1] if idx > 0 else None
        next_w = paths[idx + 1] if idx < len(paths) - 1 else None
        return prev_w, next_w
    # Noeud courant n'est pas un warning — trouver le plus proche
    # avant et apres dans l'ordre document
    prev_w = None
    next_w = None
    for p in paths:
        if p < selected_path:
            prev_w = p
        elif p > selected_path and next_w is None:
            next_w = p
    return prev_w, next_w


def _count_by_kind(node: Node) -> dict[str, int]:
    """Compter les noeuds par kind dans l'arbre."""
    counts: dict[str, int] = {}
    kind_key = node.kind.value
    counts[kind_key] = counts.get(kind_key, 0) + 1
    for child in node.children:
        for k, v in _count_by_kind(child).items():
            counts[k] = counts.get(k, 0) + v
    return counts


def _unique_warning_types(warning_nodes: list[dict]) -> list[str]:
    """Extraire les types de warnings uniques."""
    seen: set[str] = set()
    result: list[str] = []
    for wn in warning_nodes:
        for w in wn["warnings"]:
            if w not in seen:
                seen.add(w)
                result.append(w)
    return result


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


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
    show_warnings: str = "",
) -> HTMLResponse:
    """Afficher l'arbre du document avec le noeud selectionne."""
    doc = load_document(config.data_dir, doc_hash)

    # Noeud selectionne
    selected_node = _find_node_by_path(doc.tree, node)
    if selected_node is None:
        raise HTTPException(status_code=404, detail="Noeud introuvable.")

    breadcrumb = _build_breadcrumb(doc.tree, node)
    tree_data = _build_tree_data(doc.tree)
    counts = _count_by_kind(doc.tree)

    # Warnings filtres par les types ignores
    dismissed = _load_dismissed(config.data_dir, doc_hash)
    warning_nodes = _collect_warning_nodes(doc.tree, dismissed)
    warning_types = _unique_warning_types(warning_nodes)

    # Warnings actifs du noeud selectionne (filtres)
    active_warnings = [
        w for w in selected_node.metadata.warnings if w not in dismissed
    ]

    # Navigation precedent/suivant (meme kind)
    prev_path, next_path = (None, None)
    if node:
        prev_path, next_path = _find_prev_next(
            doc.tree, node, selected_node.kind,
        )

    # Navigation precedent/suivant warning
    prev_warning, next_warning = _find_prev_next_warning(
        warning_nodes, node,
    )

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
            "prev_path": prev_path,
            "next_path": next_path,
            "prev_warning": prev_warning,
            "next_warning": next_warning,
            "warning_nodes": warning_nodes,
            "warning_types": warning_types,
            "active_warnings": active_warnings,
            "dismissed": dismissed,
            "show_warnings_banner": warnings == "1",
            "show_warnings_only": show_warnings == "1",
            "csrf_token": csrf_token,
            "authenticated": True,
        },
    )


@router.post("/{doc_hash}/dismiss-warning")
async def dismiss_warning(
    request: Request,
    doc_hash: str,
    config: ConfigDep,
    csrf_token: AuthDep,
    form_csrf: str = Form(None, alias="csrf_token"),
    warning_type: str = Form(...),
    return_node: str = Form(""),
    return_mode: str = Form(""),
) -> RedirectResponse:
    """Ignorer un type de warning pour ce document."""
    check_csrf_token(form_csrf, csrf_token)
    dismissed = _load_dismissed(config.data_dir, doc_hash)
    if warning_type not in dismissed:
        dismissed.append(warning_type)
        _save_dismissed(config.data_dir, doc_hash, dismissed)
    url = f"/document/{doc_hash}/tree"
    params = []
    if return_node:
        params.append(f"node={return_node}")
    if return_mode:
        params.append(f"show_warnings={return_mode}")
    if params:
        url += "?" + "&".join(params)
    return RedirectResponse(url=url + "#content", status_code=302)


@router.post("/{doc_hash}/restore-warning")
async def restore_warning(
    request: Request,
    doc_hash: str,
    config: ConfigDep,
    csrf_token: AuthDep,
    form_csrf: str = Form(None, alias="csrf_token"),
    warning_type: str = Form(...),
    return_node: str = Form(""),
) -> RedirectResponse:
    """Restaurer un type de warning precedemment ignore."""
    check_csrf_token(form_csrf, csrf_token)
    dismissed = _load_dismissed(config.data_dir, doc_hash)
    if warning_type in dismissed:
        dismissed.remove(warning_type)
        _save_dismissed(config.data_dir, doc_hash, dismissed)
    url = f"/document/{doc_hash}/tree"
    if return_node:
        url += f"?node={return_node}"
    return RedirectResponse(url=url + "#content", status_code=302)


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
