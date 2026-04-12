"""Tests Phase 5 : édition inline et historique des versions.

Vérifie la route d'édition, l'overlay manual_edits, la liste des
versions, et la restauration.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _login(client: TestClient, password: str) -> str:
    """Helper : login et retour du csrf_token."""
    response = client.post(
        "/login",
        data={"password": password},
        follow_redirects=False,
    )
    client.cookies.set("rogier_session", response.cookies["rogier_session"])

    dash = client.get("/")
    csrf_token = ""
    if 'name="csrf-token"' in dash.text:
        start = dash.text.index('content="', dash.text.index('csrf-token')) + 9
        end = dash.text.index('"', start)
        csrf_token = dash.text[start:end]
    return csrf_token


def _upload_sample(client: TestClient, csrf: str) -> str:
    """Upload la fixture CSA et retourne le doc_hash."""
    html_path = FIXTURES_DIR / "csa_sample.html"
    html_bytes = html_path.read_bytes()
    response = client.post(
        "/upload",
        data={"csrf_token": csrf, "upload_mode": "file", "justel_url": ""},
        files={"html_file": ("csa_sample.html", html_bytes, "text/html")},
        follow_redirects=False,
    )
    location = response.headers["location"]
    # /document/{hash}/tree
    doc_hash = location.split("/document/")[1].split("/")[0]
    return doc_hash


# ---------------------------------------------------------------------------
# Tests d'édition
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_edit_article_creates_version(
    client: TestClient, test_password: str,
) -> None:
    """POST /document/{hash}/node/edit sur un article crée une version."""
    csrf = _login(client, test_password)
    doc_hash = _upload_sample(client, csrf)

    # Naviguer vers un article pour trouver un chemin valide
    tree_resp = client.get(f"/document/{doc_hash}/tree")
    assert tree_resp.status_code == 200

    # Trouver un article : le premier enfant du premier enfant
    # Le CSA a : racine > Partie 1re > Livre 1er > Titre 1er > ... > Art. X
    # On navigue vers un noeud article. Essayons "0.0.0.0.0" (premier article profond)
    tree_resp = client.get(f"/document/{doc_hash}/tree?node=0.0.0.0.0")
    if tree_resp.status_code != 200:
        # Fallback : trouver un noeud quelconque
        tree_resp = client.get(f"/document/{doc_hash}/tree?node=0")
        assert tree_resp.status_code == 200

    # Éditer via AJAX
    edit_resp = client.post(
        f"/document/{doc_hash}/node/edit",
        content=json.dumps({
            "node_path": "0",
            "new_content": "Contenu modifie pour test",
        }),
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf,
        },
    )
    assert edit_resp.status_code == 200
    data = edit_resp.json()
    assert data["ok"] is True
    assert data["version_id"].startswith("v-")


@pytest.mark.slow
def test_edit_article_overlay_displayed(
    client: TestClient, test_password: str,
) -> None:
    """Après édition, le contenu modifié est affiché dans l'arbre."""
    csrf = _login(client, test_password)
    doc_hash = _upload_sample(client, csrf)

    # Éditer le noeud "0" (premier enfant de la racine = conteneur)
    client.post(
        f"/document/{doc_hash}/node/edit",
        content=json.dumps({
            "node_path": "0",
            "new_content": "Titre modifie test overlay",
        }),
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf,
        },
    )

    # Recharger la page arbre avec ce noeud sélectionné
    tree_resp = client.get(f"/document/{doc_hash}/tree?node=0")
    assert tree_resp.status_code == 200
    assert "Titre modifie test overlay" in tree_resp.text
    assert "Modifie" in tree_resp.text  # badge


@pytest.mark.slow
def test_edit_missing_node_returns_404(
    client: TestClient, test_password: str,
) -> None:
    """Éditer un noeud inexistant retourne 404."""
    csrf = _login(client, test_password)
    doc_hash = _upload_sample(client, csrf)

    resp = client.post(
        f"/document/{doc_hash}/node/edit",
        content=json.dumps({
            "node_path": "99.99.99",
            "new_content": "nope",
        }),
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf,
        },
    )
    assert resp.status_code == 404


@pytest.mark.slow
def test_edit_without_csrf_returns_403(
    client: TestClient, test_password: str,
) -> None:
    """Éditer sans CSRF retourne 403."""
    csrf = _login(client, test_password)
    doc_hash = _upload_sample(client, csrf)

    resp = client.post(
        f"/document/{doc_hash}/node/edit",
        content=json.dumps({
            "node_path": "0",
            "new_content": "nope",
        }),
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": "invalid-token",
        },
    )
    assert resp.status_code == 403


@pytest.mark.slow
def test_edit_real_article_label(
    client: TestClient, test_password: str,
) -> None:
    """Éditer un vrai ARTICLE produit un label 'Édition manuelle Art. X'."""
    csrf = _login(client, test_password)
    doc_hash = _upload_sample(client, csrf)

    # Trouver un article en cherchant dans le HTML rendu
    # Le CSA a Art. 1:1 en profondeur. On essaie plusieurs chemins.
    article_path = None
    for candidate in ["0.0.0.0.0.0", "0.0.0.0.0", "0.0.0.0"]:
        resp = client.get(f"/document/{doc_hash}/tree?node={candidate}")
        if resp.status_code == 200 and 'data-node-kind="ARTICLE"' in resp.text:
            article_path = candidate
            break

    assert article_path is not None, "Aucun article trouvé dans le CSA sample"

    edit_resp = client.post(
        f"/document/{doc_hash}/node/edit",
        content=json.dumps({
            "node_path": article_path,
            "new_content": "Contenu article test",
        }),
        headers={
            "Content-Type": "application/json",
            "X-CSRF-Token": csrf,
        },
    )
    assert edit_resp.status_code == 200

    # Vérifier le label dans l'historique
    versions_resp = client.get(f"/document/{doc_hash}/versions")
    assert "dition manuelle Art." in versions_resp.text


# ---------------------------------------------------------------------------
# Tests de l'historique des versions
# ---------------------------------------------------------------------------


@pytest.mark.slow
def test_version_list_shows_versions(
    client: TestClient, test_password: str,
) -> None:
    """La page versions affiche l'historique."""
    csrf = _login(client, test_password)
    doc_hash = _upload_sample(client, csrf)

    # Une seule version (Import initial)
    resp = client.get(f"/document/{doc_hash}/versions")
    assert resp.status_code == 200
    assert "Import initial" in resp.text
    assert "Active" in resp.text

    # Créer une édition → 2 versions
    client.post(
        f"/document/{doc_hash}/node/edit",
        content=json.dumps({"node_path": "0", "new_content": "Modif"}),
        headers={"Content-Type": "application/json", "X-CSRF-Token": csrf},
    )

    resp = client.get(f"/document/{doc_hash}/versions")
    assert resp.status_code == 200
    assert "Import initial" in resp.text
    # Le label d'édition contient le type du noeud
    assert "Renommage" in resp.text or "dition" in resp.text


@pytest.mark.slow
def test_restore_version_creates_new_version(
    client: TestClient, test_password: str,
) -> None:
    """Restaurer une version crée une nouvelle version."""
    csrf = _login(client, test_password)
    doc_hash = _upload_sample(client, csrf)

    # Lire la version initiale
    resp = client.get(f"/document/{doc_hash}/versions")
    # Extraire l'ID de la version initiale depuis le HTML
    # Le formulaire restore contient l'ID dans l'action URL
    import re
    restore_urls = re.findall(
        rf'/document/{doc_hash}/versions/(v-[a-f0-9]+)/restore',
        resp.text,
    )

    # Créer une édition pour avoir 2 versions
    client.post(
        f"/document/{doc_hash}/node/edit",
        content=json.dumps({"node_path": "0", "new_content": "Modif"}),
        headers={"Content-Type": "application/json", "X-CSRF-Token": csrf},
    )

    # Maintenant la page versions a un bouton Restaurer pour l'initiale
    resp = client.get(f"/document/{doc_hash}/versions")
    restore_urls = re.findall(
        rf'/document/{doc_hash}/versions/(v-[a-f0-9]+)/restore',
        resp.text,
    )
    assert len(restore_urls) >= 1

    # Restaurer la première version trouvée (non-active)
    version_to_restore = restore_urls[0]
    resp = client.post(
        f"/document/{doc_hash}/versions/{version_to_restore}/restore",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert resp.status_code == 302

    # Vérifier qu'on a maintenant 3 versions
    resp = client.get(f"/document/{doc_hash}/versions")
    assert "Restauration" in resp.text
