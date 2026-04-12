"""Test de bout en bout : parcours complet upload -> arbre -> edition -> export.

Verifie que le fichier Markdown exporte contient le contenu edite.
"""

from __future__ import annotations

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
        start = dash.text.index('content="', dash.text.index("csrf-token")) + 9
        end = dash.text.index('"', start)
        csrf_token = dash.text[start:end]
    return csrf_token


def _extract_doc_hash(location: str) -> str:
    """Extraire le hash du document depuis l'URL de redirection."""
    # /document/<hash>/tree ou /document/<hash>/tree?warnings=1
    parts = location.split("/")
    # ['', 'document', '<hash>', 'tree...']
    return parts[2]


@pytest.mark.slow
def test_e2e_upload_edit_export(client: TestClient, test_password: str) -> None:
    """Parcours complet : upload -> arbre -> edition article -> export.

    Verifie que le contenu edite apparait dans le fichier .md exporte.
    """
    csrf = _login(client, test_password)
    html_path = FIXTURES_DIR / "csa_sample.html"
    html_bytes = html_path.read_bytes()

    # --- Etape 1 : Upload ---
    resp = client.post(
        "/upload",
        data={"csrf_token": csrf, "upload_mode": "file", "justel_url": ""},
        files={"html_file": ("csa_sample.html", html_bytes, "text/html")},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    location = resp.headers["location"]
    assert "/document/" in location
    doc_hash = _extract_doc_hash(location)

    # --- Etape 2 : Arbre ---
    tree_resp = client.get(f"/document/{doc_hash}/tree")
    assert tree_resp.status_code == 200
    assert "Partie" in tree_resp.text

    # Naviguer vers le premier article (Art. 1:1 au chemin "0.0.0.0")
    first_article_resp = client.get(f"/document/{doc_hash}/tree?node=0.0.0.0")
    assert first_article_resp.status_code == 200

    # --- Etape 3 : Edition ---
    edited_content = "CONTENU_EDITE_PAR_TEST_E2E_12345"
    edit_resp = client.post(
        f"/document/{doc_hash}/node/edit",
        json={"node_path": "0.0.0.0", "new_content": edited_content},
        headers={"X-CSRF-Token": csrf},
    )
    assert edit_resp.status_code == 200
    edit_data = edit_resp.json()
    assert edit_data["ok"] is True
    assert "version_id" in edit_data

    # Verifier que l'arbre affiche le contenu edite
    tree_after = client.get(f"/document/{doc_hash}/tree?node=0.0.0.0")
    assert tree_after.status_code == 200
    assert edited_content in tree_after.text

    # --- Etape 4 : Export ---
    export_resp = client.post(
        f"/document/{doc_hash}/export",
        data={
            "csrf_token": csrf,
            "strategy": "per_article",
            "hybrid_threshold": "2000",
            "max_chunk_size": "5000",
            "include_breadcrumb": "",
            "include_node_titles": "",
        },
        follow_redirects=False,
    )
    assert export_resp.status_code == 200
    assert "text/markdown" in export_resp.headers["content-type"]

    md_content = export_resp.text
    assert edited_content in md_content, (
        "Le contenu edite doit apparaitre dans le fichier Markdown exporte"
    )


@pytest.mark.slow
def test_e2e_version_restore(client: TestClient, test_password: str) -> None:
    """Parcours : upload -> edition -> restauration -> verification."""
    csrf = _login(client, test_password)
    html_path = FIXTURES_DIR / "csa_sample.html"
    html_bytes = html_path.read_bytes()

    # Upload
    resp = client.post(
        "/upload",
        data={"csrf_token": csrf, "upload_mode": "file", "justel_url": ""},
        files={"html_file": ("csa_sample.html", html_bytes, "text/html")},
        follow_redirects=False,
    )
    doc_hash = _extract_doc_hash(resp.headers["location"])

    # Lire le contenu original de l'article
    original_resp = client.get(f"/document/{doc_hash}/tree?node=0.0.0.0")
    assert original_resp.status_code == 200

    # Editer l'article
    edit_resp = client.post(
        f"/document/{doc_hash}/node/edit",
        json={"node_path": "0.0.0.0", "new_content": "CONTENU_TEMPORAIRE"},
        headers={"X-CSRF-Token": csrf},
    )
    assert edit_resp.status_code == 200

    # Consulter l'historique des versions
    versions_resp = client.get(f"/document/{doc_hash}/versions")
    assert versions_resp.status_code == 200
    assert "Restauration" not in versions_resp.text  # pas encore de restauration

    # Trouver l'ID de la premiere version (version initiale)
    # On restaure la version initiale pour retrouver le contenu original
    # L'historique est en ordre inverse, la version initiale est la derniere
    # On cherche le formulaire de restauration dans le HTML
    html = versions_resp.text
    # Trouver le dernier bouton restore (version initiale)
    restore_marker = "/restore"
    last_restore_idx = html.rfind(restore_marker)
    assert last_restore_idx > 0, "Bouton de restauration introuvable"

    # Extraire l'action du formulaire le plus proche
    form_start = html.rfind('action="', 0, last_restore_idx)
    action_start = form_start + len('action="')
    action_end = html.index('"', action_start)
    restore_url = html[action_start:action_end]

    # Restaurer la version initiale
    restore_resp = client.post(
        restore_url,
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert restore_resp.status_code == 302

    # Verifier que le contenu edite n'est plus affiche
    tree_after_restore = client.get(f"/document/{doc_hash}/tree?node=0.0.0.0")
    assert tree_after_restore.status_code == 200
    assert "CONTENU_TEMPORAIRE" not in tree_after_restore.text

    # Verifier que l'historique mentionne la restauration
    versions_after = client.get(f"/document/{doc_hash}/versions")
    assert "Restauration" in versions_after.text
