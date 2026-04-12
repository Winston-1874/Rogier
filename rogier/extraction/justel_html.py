"""Extracteur HTML Justel → arbre hiérarchique.

Prend en entrée un HTML Justel brut (déjà décodé en UTF-8) et produit
un arbre ``Node`` conforme au modèle de ``rogier.parsing.tree``.

Adapté du prototype ``pre-app/justel_extract.py`` validé sur le CSA complet
(18 livres, 1 278 articles).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from rogier.errors import JustelParseError
from rogier.parsing.tree import Node, NodeKind, NodeMetadata

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Profondeur logique par niveau hiérarchique.
LEVEL_DEPTH: dict[str, int] = {
    "PARTIE": 0,
    "LIVRE": 1,
    "TITRE": 2,
    "CHAPITRE": 3,
    "Section": 4,
    "Sous-section": 5,
}

# Mapping texte HTML → NodeKind
_LEVEL_TO_KIND: dict[str, NodeKind] = {
    "PARTIE": NodeKind.PARTIE,
    "LIVRE": NodeKind.LIVRE,
    "TITRE": NodeKind.TITRE,
    "CHAPITRE": NodeKind.CHAPITRE,
    "Section": NodeKind.SECTION,
    "Sous-section": NodeKind.SOUS_SECTION,
}


# ---------------------------------------------------------------------------
# Expressions régulières
# ---------------------------------------------------------------------------

# Toute ancre, hiérarchique (LNK\d+) ou article (Art.X)
# Supporte guillemets doubles et simples, balises majuscules et minuscules.
RE_ANY_ANCHOR = re.compile(
    r"""<[aA]\s+[nN][aA][mM][eE]=['"](LNK\d+|Art\.[^'"]+)['"]"""
)

# Entrée hiérarchique.
# IMPORTANT : Sous-section avant Section pour éviter le match préfixe.
RE_HIERARCHY_ENTRY = re.compile(
    r"""<[aA]\s+[nN][aA][mM][eE]=['"]LNK\d+['"][^>]*>"""
    r"(PARTIE|LIVRE|TITRE|CHAPITRE|Sous-section|Section)"
    r"\s+([^<]+?)</[aA]>"
    r"([^<]*)"
)

# Titre encapsulé dans un marqueur de modification (§7.8 cas 1).
# Le HTML réel contient des balises imbriquées dans le marqueur :
#   [<sup><font color="red"><a...><span...>N</span></a></font></sup> Titre]<sup>
# On cherche le texte lisible entre le </sup> fermant du numéro et le ]<sup> fermant.
RE_MOD_TITLE = re.compile(
    r"\[<sup>.*?</sup>\s*(.+?)\]<sup>",
    re.DOTALL,
)

# Entités HTML non reconnues résiduelles
RE_UNKNOWN_ENTITY = re.compile(r"&[a-zA-Z]+;|&#\d+;")


# ---------------------------------------------------------------------------
# Entrée brute (avant placement dans l'arbre)
# ---------------------------------------------------------------------------

@dataclass
class RawEntry:
    """Entrée extraite linéairement du HTML."""

    kind: str  # 'hierarchy' ou 'article'
    position: int
    level: str = ""
    number: str = ""
    title: str = ""
    content: str = ""
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Rapport de parsing
# ---------------------------------------------------------------------------

@dataclass
class ParsingReport:
    """Rapport global retourné à côté du Document."""

    total_articles: int = 0
    total_hierarchy: int = 0
    warnings: list[str] = field(default_factory=list)
    counts_by_kind: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------

def _find_case_insensitive(html: str, candidates: list[str], start: int = 0) -> int:
    """Chercher la première occurrence parmi plusieurs variantes."""
    best = -1
    for candidate in candidates:
        pos = html.find(candidate, start)
        if pos != -1 and (best == -1 or pos < best):
            best = pos
    return best


def locate_body(html: str) -> str:
    """Isoler la zone 3 (corps du texte) du HTML Justel.

    Exclut l'entête, la TOC et la section « Articles modifiés ».
    Supporte les deux formats : navigateur (minuscules, guillemets doubles)
    et serveur Justel brut (majuscules, guillemets simples).
    """
    toc_marker = _find_case_insensitive(html, [
        'id="list-title-2"',
        "id='list-title-2'",
    ])
    if toc_marker == -1:
        raise JustelParseError(
            'Marqueur de table des matières (id="list-title-2") introuvable '
            "dans le HTML. Le format du fichier est peut-être inattendu."
        )

    body_start = _find_case_insensitive(html, [
        '<a name="LNK0001"',
        "<a name='LNK0001'",
        '<A NAME="LNK0001"',
        "<A NAME='LNK0001'",
    ], toc_marker + 1000)
    if body_start == -1:
        raise JustelParseError(
            "Ancre de début du corps (LNK0001) introuvable après la table "
            "des matières. Le HTML semble tronqué ou corrompu."
        )

    mods_start = html.find("Articles modifiés", body_start)
    body_end = mods_start if mods_start > 0 else len(html)

    return html[body_start:body_end]


def _scan_anchors(body: str) -> list[tuple[int, str]]:
    """Lister (position, nom) de toutes les ancres dans l'ordre."""
    return [(m.start(), m.group(1)) for m in RE_ANY_ANCHOR.finditer(body)]


def _find_article_content_start(raw: str) -> int:
    """Trouver le début du texte d'un article après ses ancres d'ouverture.

    Gère la forme A (standard, 2 balises <a>) et la forme B (dernier article,
    1 seule balise <a>).
    """
    i = 0
    # Sauter les blocs <a>...</a> successifs
    while True:
        while i < len(raw) and raw[i] in " \t\n\r":
            i += 1
        if i + 1 >= len(raw) or raw[i : i + 2].lower() != "<a":
            break
        close_lower = raw.find("</a>", i)
        close_upper = raw.find("</A>", i)
        if close_lower == -1:
            close = close_upper
        elif close_upper == -1:
            close = close_lower
        else:
            close = min(close_lower, close_upper)
        if close == -1:
            break
        i = close + 4

    # Espaces
    while i < len(raw) and raw[i] in " \t\n\r":
        i += 1

    # Forme B : numéro en texte direct (ex: "18:8.")
    m = re.match(r"[\d:/\-a-z]+\.", raw[i:])
    if m:
        i += m.end()
    # Forme A : le deuxième <a> contenait le numéro, on saute juste le "."
    elif i < len(raw) and raw[i] == ".":
        i += 1

    # Espaces avant le vrai contenu
    while i < len(raw) and raw[i] in " \t\n\r":
        i += 1

    return i


def _clean_content(html: str) -> str:
    """Convertir un fragment HTML en texte brut lisible.

    Préserve les marqueurs de modification sous la forme ``[ΔN ... ΔN]``.
    """
    # 1. Marqueurs de modification ouvrants et fermants
    html = re.sub(
        r'\[<sup><font color="red">(\d+)</font></sup>',
        r"[Δ\1 ",
        html,
    )
    html = re.sub(
        r'\]<sup><font color="red">(\d+)</font></sup>',
        r" Δ\1]",
        html,
    )

    # 2. Balises <a> : garder le contenu textuel
    html = re.sub(r"<a[^>]*>|</a>", "", html)

    # 3. <br> → saut de ligne
    html = re.sub(r"<br\s*/?>", "\n", html)

    # 4. Balises résiduelles
    html = re.sub(r"<[^>]+>", "", html)

    # 5. Entités HTML courantes
    for old, new in {
        "&nbsp;": " ",
        "&amp;": "&",
        "&lt;": "<",
        "&gt;": ">",
        "&quot;": '"',
        "&#39;": "'",
        "\xa0": " ",
    }.items():
        html = html.replace(old, new)

    # 6. Normalisation des espaces
    html = re.sub(r"[ \t]+", " ", html)
    html = re.sub(r"\n[ \t]+", "\n", html)
    html = re.sub(r"\n{3,}", "\n\n", html)

    return html.strip()


def _extract_mod_title(raw_block: str) -> str | None:
    """Extraire le vrai titre d'un bloc contenant un marqueur de modification.

    Retourne le titre nettoyé ou None si aucun marqueur trouvé.
    """
    m = RE_MOD_TITLE.search(raw_block)
    if m:
        return m.group(1).strip(" .\n")
    return None


def _extract_entries(body: str) -> list[RawEntry]:
    """Extraire séquentiellement les entrées hiérarchiques et articles."""
    anchors = _scan_anchors(body)
    entries: list[RawEntry] = []

    for i, (pos, name) in enumerate(anchors):
        next_pos = anchors[i + 1][0] if i + 1 < len(anchors) else len(body)
        raw = body[pos:next_pos]

        if name.startswith("LNK"):
            m = RE_HIERARCHY_ENTRY.match(raw)
            if not m:
                continue
            level = m.group(1)
            number = m.group(2).rstrip(". ").strip()
            title = m.group(3).strip(" .\n")

            # §7.8 cas 1 : titre tronqué par marqueur de modification
            # Détecté quand le titre capturé se réduit à "[" (le début du
            # marqueur [<sup>...) — les titres réellement vides restent vides.
            if "[" in title and re.match(r"^\s*\[+\s*$", title):
                # Limiter la recherche au fragment entre le </a> de
                # l'entrée hiérarchique et le prochain saut de ligne ou ancre,
                # pour ne pas déborder dans un article.
                header_end = raw.find("\n", m.end())
                if header_end == -1:
                    header_end = min(len(raw), m.end() + 1000)
                extracted = _extract_mod_title(raw[: header_end])
                if extracted:
                    title = extracted
                    entry_warnings = [
                        "Titre extrait d'un marqueur de modification"
                    ]
                else:
                    entry_warnings = []
            else:
                entry_warnings = []

            entries.append(
                RawEntry(
                    kind="hierarchy",
                    position=pos,
                    level=level,
                    number=number,
                    title=title,
                    warnings=entry_warnings,
                )
            )
        else:
            number = name[len("Art."):]
            content_start = _find_article_content_start(raw)
            content = _clean_content(raw[content_start:])
            entries.append(
                RawEntry(
                    kind="article",
                    position=pos,
                    number=number,
                    content=content,
                )
            )

    return entries


def _build_tree(entries: list[RawEntry], doc_title: str) -> Node:
    """Reconstruire l'arbre hiérarchique à partir de la liste plate.

    Algorithme à pile : on maintient une pile des conteneurs ouverts avec
    leur profondeur. Les articles s'attachent au conteneur en sommet de pile.
    """
    root = Node(kind=NodeKind.DOCUMENT, title=doc_title)
    stack: list[Node] = [root]
    depths: list[int] = [-1]

    for e in entries:
        if e.kind == "hierarchy":
            depth = LEVEL_DEPTH[e.level]
            kind = _LEVEL_TO_KIND[e.level]

            while depths and depths[-1] >= depth:
                stack.pop()
                depths.pop()

            metadata = NodeMetadata(warnings=list(e.warnings))

            node = Node(
                kind=kind,
                number=e.number,
                title=e.title,
                metadata=metadata,
            )
            stack[-1].children.append(node)
            stack.append(node)
            depths.append(depth)

        else:
            metadata = NodeMetadata()
            content = e.content

            # Warnings sur le contenu de l'article
            if not content:
                metadata.warnings.append("Contenu d'article vide")
            elif len(content) < 20:
                metadata.warnings.append(
                    f"Contenu inhabituellement court ({len(content)} caractères)"
                )
            if len(content) > 15000:
                metadata.warnings.append(
                    f"Contenu inhabituellement long ({len(content)} caractères)"
                )

            # Entités HTML non reconnues résiduelles
            unknown = RE_UNKNOWN_ENTITY.findall(content)
            if unknown:
                unique = sorted(set(unknown))
                metadata.warnings.append(
                    f"Entité HTML non reconnue : {', '.join(unique)}"
                )

            node = Node(
                kind=NodeKind.ARTICLE,
                number=e.number,
                content=content,
                metadata=metadata,
            )
            stack[-1].children.append(node)

    return root


def _count_nodes(node: Node) -> dict[str, int]:
    """Compter les nœuds par type de NodeKind."""
    counts: dict[str, int] = {}

    def rec(n: Node) -> None:
        key = n.kind.value
        counts[key] = counts.get(key, 0) + 1
        for c in n.children:
            rec(c)

    rec(node)
    return counts


def _collect_warnings(node: Node) -> list[str]:
    """Collecter tous les warnings de l'arbre sous forme lisible."""
    result: list[str] = []

    def rec(n: Node) -> None:
        for w in n.metadata.warnings:
            result.append(f"{n.label} : {w}")
        for c in n.children:
            rec(c)

    rec(node)
    return result


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------

def parse_justel_html(html: str, doc_title: str = "") -> tuple[Node, ParsingReport]:
    """Parser un HTML Justel complet et retourner l'arbre + rapport.

    Parameters
    ----------
    html:
        Le contenu HTML complet d'une page Justel, décodé en UTF-8.
    doc_title:
        Titre du document racine. Si vide, utilise "Document".

    Returns
    -------
    tuple[Node, ParsingReport]
        L'arbre hiérarchique et le rapport de parsing.

    Raises
    ------
    JustelParseError
        Si le HTML ne contient pas les marqueurs structurels attendus.
    """
    body = locate_body(html)
    entries = _extract_entries(body)

    tree = _build_tree(entries, doc_title)
    counts = _count_nodes(tree)

    all_warnings = _collect_warnings(tree)

    report = ParsingReport(
        total_articles=counts.get("ARTICLE", 0),
        total_hierarchy=sum(
            v for k, v in counts.items() if k not in ("DOCUMENT", "ARTICLE")
        ),
        warnings=all_warnings,
        counts_by_kind=counts,
    )

    return tree, report


def find_article(node: Node, number: str) -> Node | None:
    """Retrouver un article par son numéro dans l'arbre."""
    if node.kind == NodeKind.ARTICLE and node.number == number:
        return node
    for child in node.children:
        result = find_article(child, number)
        if result:
            return result
    return None
