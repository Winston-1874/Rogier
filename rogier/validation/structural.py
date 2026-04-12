"""Invariants structurels (niveau 1) — SPEC §11.1.

Huit invariants (S001–S008) vérifiés sur l'arbre du document.
Chaque invariant opère sur le contenu effectif (overlay manual_edits).
"""

from __future__ import annotations

import re

from rogier.overlay import get_effective_content, walk_articles, walk_descendants
from rogier.parsing.tree import Node, NodeKind

# Regex pour extraire la partie numérique initiale d'un numéro d'article.
# Exemples : "2" → 2, "2bis" → 2, "14ter" → 14, "1er" → 1.
_RE_LEADING_INT = re.compile(r"^(\d+)")


def _extract_leading_int(number: str) -> int | None:
    """Extraire la partie entière initiale d'un numéro d'article.

    Retourne None si le numéro ne commence pas par un chiffre.
    """
    m = _RE_LEADING_INT.match(number.strip())
    if m:
        return int(m.group(1))
    return None


# ---------------------------------------------------------------------------
# Dataclass résultat (importée depuis report.py pour éviter la circularité)
# → on utilise un dict simple ici, report.py construit InvariantResult.
# ---------------------------------------------------------------------------


def _pass(
    invariant_id: str, description: str, detail: str,
    data: dict | None = None,
) -> dict:
    result = {
        "id": invariant_id,
        "level": 1,
        "description": description,
        "status": "pass",
        "detail": detail,
    }
    if data is not None:
        result["data"] = data
    return result


def _fail(
    invariant_id: str, description: str, detail: str,
    data: dict | None = None,
) -> dict:
    result = {
        "id": invariant_id,
        "level": 1,
        "description": description,
        "status": "fail",
        "detail": detail,
    }
    if data is not None:
        result["data"] = data
    return result


# ---------------------------------------------------------------------------
# Invariants S001–S008
# ---------------------------------------------------------------------------


def check_s001(root: Node, manual_edits: dict[str, str]) -> dict:
    """S001 : au moins 1 article dans le document."""
    articles = walk_articles(root)
    if articles:
        return _pass("S001", "Au moins 1 article", f"{len(articles)} article(s) trouvé(s).")
    return _fail("S001", "Au moins 1 article", "Aucun article trouvé dans le document.")


def check_s002(root: Node, manual_edits: dict[str, str]) -> dict:
    """S002 : tous les articles ont un contenu non vide."""
    empty: list[str] = []
    for article, path in walk_articles(root):
        content = get_effective_content(article, path, manual_edits)
        if not content.strip():
            label = f"Art. {article.number}" if article.number else f"(chemin {path})"
            empty.append(label)
    if not empty:
        return _pass("S002", "Articles non vides", "Tous les articles ont du contenu.")
    return _fail(
        "S002",
        "Articles non vides",
        f"{len(empty)} article(s) vide(s) : {', '.join(empty[:10])}."
        + (" (liste tronquée)" if len(empty) > 10 else ""),
    )


def check_s003(root: Node, manual_edits: dict[str, str]) -> dict:
    """S003 : aucun article n'a une longueur < 20 caractères."""
    short: list[str] = []
    for article, path in walk_articles(root):
        content = get_effective_content(article, path, manual_edits)
        if content.strip() and len(content.strip()) < 20:
            label = f"Art. {article.number}" if article.number else f"(chemin {path})"
            short.append(f"{label} ({len(content.strip())} car.)")
    if not short:
        return _pass(
            "S003", "Longueur minimale des articles (≥ 20 car.)",
            "Aucun article trop court.",
        )
    return _fail(
        "S003",
        "Longueur minimale des articles (≥ 20 car.)",
        f"{len(short)} article(s) trop court(s) : {', '.join(short[:10])}."
        + (" (liste tronquée)" if len(short) > 10 else ""),
    )


def check_s004(root: Node, manual_edits: dict[str, str]) -> dict:
    """S004 : aucun article n'a une longueur > 20 000 caractères."""
    long: list[str] = []
    for article, path in walk_articles(root):
        content = get_effective_content(article, path, manual_edits)
        if len(content) > 20_000:
            label = f"Art. {article.number}" if article.number else f"(chemin {path})"
            long.append(f"{label} ({len(content)} car.)")
    if not long:
        return _pass(
            "S004", "Longueur maximale des articles (≤ 20 000 car.)",
            "Aucun article trop long.",
        )
    return _fail(
        "S004",
        "Longueur maximale des articles (≤ 20 000 car.)",
        f"{len(long)} article(s) trop long(s) : {', '.join(long[:10])}."
        + (" (liste tronquée)" if len(long) > 10 else ""),
    )


def check_s005(root: Node, manual_edits: dict[str, str]) -> dict:
    """S005 : numérotation des articles monotone dans chaque conteneur.

    Compare la partie entière initiale des numéros d'articles au sein
    de chaque conteneur direct. Les suffixes bis/ter/quater sont ignorés
    pour la comparaison : "2", "2bis", "2ter", "3" est monotone (2 ≤ 2 ≤ 2 ≤ 3).
    "2", "3", "2bis" est NON monotone (3 > 2).
    Les articles sans numéro exploitable sont ignorés.
    """
    violations: list[str] = []
    _check_monotone_recursive(root, "", violations)
    if not violations:
        return _pass(
            "S005", "Numérotation monotone des articles",
            "Numérotation cohérente dans tous les conteneurs.",
        )
    return _fail(
        "S005",
        "Numérotation monotone des articles",
        f"{len(violations)} rupture(s) de monotonie : {', '.join(violations[:10])}."
        + (" (liste tronquée)" if len(violations) > 10 else ""),
    )


def _check_monotone_recursive(
    node: Node,
    current_path: str,
    violations: list[str],
) -> None:
    """Vérifier la monotonie dans les enfants directs, puis récurser."""
    last_num: int | None = None
    last_label = ""
    for i, child in enumerate(node.children):
        child_path = f"{current_path}.{i}" if current_path else str(i)
        if child.kind == NodeKind.ARTICLE:
            num = _extract_leading_int(child.number)
            if num is not None:
                if last_num is not None and num < last_num:
                    violations.append(
                        f"Art. {child.number} (n={num}) après {last_label} (n={last_num})"
                    )
                last_num = num
                last_label = f"Art. {child.number}"
        else:
            _check_monotone_recursive(child, child_path, violations)


def check_s006(root: Node, manual_edits: dict[str, str]) -> dict:
    """S006 : aucun doublon d'identifiant d'article."""
    seen: dict[str, int] = {}
    for article, _path in walk_articles(root):
        key = article.number.strip()
        if key:
            seen[key] = seen.get(key, 0) + 1
    duplicates = [f"Art. {num} (×{count})" for num, count in seen.items() if count > 1]
    if not duplicates:
        return _pass("S006", "Pas de doublons d'articles", "Aucun identifiant d'article dupliqué.")
    return _fail(
        "S006",
        "Pas de doublons d'articles",
        f"{len(duplicates)} doublon(s) : {', '.join(duplicates[:10])}."
        + (" (liste tronquée)" if len(duplicates) > 10 else ""),
    )


def check_s007(root: Node, manual_edits: dict[str, str]) -> dict:
    """S007 : profondeur maximale de l'arbre ≤ 7 (DOC + 6 niveaux)."""
    max_depth = _max_depth(root, 0)
    if max_depth <= 7:
        return _pass("S007", "Profondeur maximale ≤ 7", f"Profondeur maximale : {max_depth}.")
    return _fail(
        "S007",
        "Profondeur maximale ≤ 7",
        f"Profondeur maximale : {max_depth} (limite : 7).",
    )


def _max_depth(node: Node, current: int) -> int:
    """Calculer la profondeur maximale de l'arbre."""
    if not node.children:
        return current
    return max(_max_depth(child, current + 1) for child in node.children)


def check_s008(root: Node, manual_edits: dict[str, str]) -> dict:
    """S008 : tous les warnings de parsing sont listés dans le rapport.

    Collecte tous les warnings de NodeMetadata dans l'arbre entier.
    Le rapport de validation doit les référencer tous.
    Ce check retourne la liste complète des warnings trouvés — le rapport
    (report.py) se charge de vérifier qu'aucun n'est manquant.
    """
    all_warnings: list[str] = []
    for node, _path in walk_descendants(root):
        all_warnings.extend(node.metadata.warnings)
    # On inclut aussi les warnings de la racine elle-même
    all_warnings.extend(root.metadata.warnings)

    count = len(all_warnings)
    if count == 0:
        return _pass(
            "S008", "Warnings de parsing référencés",
            "Aucun warning de parsing dans l'arbre.",
            data={"count": 0},
        )

    return _pass(
        "S008",
        "Warnings de parsing référencés",
        f"{count} warning(s) de parsing collecté(s).",
        data={"count": count},
    )


def collect_all_warnings(root: Node) -> list[str]:
    """Collecter tous les warnings de parsing dans l'arbre (pour S008 cross-check)."""
    all_warnings: list[str] = []
    all_warnings.extend(root.metadata.warnings)
    for node, _path in walk_descendants(root):
        all_warnings.extend(node.metadata.warnings)
    return all_warnings


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

_ALL_CHECKS = [
    check_s001,
    check_s002,
    check_s003,
    check_s004,
    check_s005,
    check_s006,
    check_s007,
    check_s008,
]


def run_structural(
    root: Node,
    manual_edits: dict[str, str] | None = None,
) -> list[dict]:
    """Exécuter tous les invariants structurels et retourner les résultats."""
    if manual_edits is None:
        manual_edits = {}
    return [check(root, manual_edits) for check in _ALL_CHECKS]
