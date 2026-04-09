# SPEC — Rogier v0.1

**Destinataire :** Claude Code
**Commanditaire :** utilisateur non-développeur (juriste belge)
**Version du document :** 1.0
**Date :** avril 2026

---

## Table des matières

0. [Lecture préalable](#0-lecture-préalable)
1. [Vision et non-vision](#1-vision-et-non-vision)
2. [Stack technique figée](#2-stack-technique-figée)
3. [Interdictions non-négociables](#3-interdictions-non-négociables)
4. [Modèle de données](#4-modèle-de-données)
5. [Architecture et arborescence du repo](#5-architecture-et-arborescence-du-repo)
6. [Spec du fetcher Justel](#6-spec-du-fetcher-justel)
7. [Spec du parser HTML Justel](#7-spec-du-parser-html-justel)
8. [Spec du stockage et du versioning](#8-spec-du-stockage-et-du-versioning)
9. [Spec de l'interface web](#9-spec-de-linterface-web)
10. [Spec du chunker et de l'export](#10-spec-du-chunker-et-de-lexport)
11. [Spec de la validation](#11-spec-de-la-validation)
12. [Sécurité](#12-sécurité)
13. [Règles de qualité de code](#13-règles-de-qualité-de-code)
14. [Phasage d'implémentation](#14-phasage-dimplémentation)
15. [Tests d'acceptation](#15-tests-dacceptation)
16. [Instructions comportementales](#16-instructions-comportementales)

---

## 0. Lecture préalable

### 0.1 Comment utiliser ce document

Ce document est **la référence unique** pour l'implémentation de Rogier v0.1. Il doit être copié dans le repo à la racine sous le nom `SPEC.md` dès le premier commit. Chaque fois qu'une question architecturale se pose, la réponse doit d'abord être cherchée ici.

Si une consigne est absente, contradictoire, ou techniquement impossible : **s'arrêter et demander**. Ne pas deviner.

Si une consigne de ce document semble en contradiction avec les bonnes pratiques générales du développement Python, ce document prévaut sauf si l'écart crée un bug ou une faille de sécurité — auquel cas s'arrêter et demander.

### 0.2 Utilisateur cible

L'utilisateur final de Rogier est un **juriste belge, non-développeur**. Les conséquences :

- Les messages d'erreur sont en français clair, jamais des traces Python nues
- Les décisions techniques ne doivent jamais rester silencieuses : elles sont expliquées en français dans un commentaire, un commit message, ou un message de fin de phase
- L'interface web est sobre, sans jargon technique, sans anglicismes inutiles
- Les fonctionnalités « avancées » sont masquées ou repliées par défaut

### 0.3 Nature du projet

Rogier est nommé d'après **Charles Rogier** (1800-1885), membre du gouvernement provisoire belge de 1830, rédacteur de dispositions de la Constitution belge, signataire de l'acte d'indépendance. Le nom est une référence explicite à la fondation du droit belge. Le README doit mentionner cette origine de façon sobre, sans en faire une dissertation.

Rogier v0.1 est une étape d'un projet plus large visant à rendre le droit belge plus accessible. Cette v0.1 se concentre sur **une seule chaîne fonctionnelle** : prendre un texte législatif belge publié sur Justel et produire des chunks Markdown prêts à ingérer dans un système RAG.

---

## 1. Vision et non-vision

### 1.1 Ce que Rogier v0.1 fait

Rogier v0.1 est une application web mono-utilisateur qui :

1. **Accepte** un texte législatif belge en entrée, sous deux formes :
   - Upload d'un fichier HTML sauvegardé depuis Justel (ejustice.just.fgov.be)
   - URL directe vers une page Justel, que l'application fetche elle-même

2. **Parse** ce HTML en arbre structuré hiérarchique respectant l'organisation belge : Partie → Livre → Titre → Chapitre → Section → Sous-section → Article

3. **Affiche** cet arbre dans une interface web navigable, avec le contenu nettoyé de chaque article, les métadonnées, et les avertissements de parsing éventuels

4. **Permet** à l'utilisateur d'éditer manuellement le contenu d'un nœud pour corriger une erreur de parsing, avec versioning automatique de chaque modification

5. **Exporte** le corpus en fichier Markdown chunké, selon deux stratégies :
   - Un chunk par article (défaut, recommandé pour la plupart des usages)
   - Chunking hybride (articles courts intacts, articles longs découpés par paragraphes)

6. **Valide** le résultat via deux niveaux d'invariants (structurels et sémantiques) et affiche un rapport de qualité avant l'export

### 1.2 Ce que Rogier v0.1 ne fait PAS

Pour éviter la dérive de périmètre qui tuerait l'atteinte de v0.1, les fonctionnalités suivantes sont **explicitement reportées** à des versions ultérieures :

- **Pas de conversion vers Akoma Ntoso (AKN) XML.** Uniquement Markdown en sortie. AKN est prévu pour v0.2 ou ultérieur.
- **Pas d'intégration LLM.** Pas de clé API OpenRouter, pas de Paramètres « clé + modèle », pas d'autoconfig, pas de suggestion par règle, pas de QC niveau 3. Toute intervention IA est reportée. **Conséquence : il n'y a pas d'écran Paramètres du tout en v0.1.** Le seul réglage personnel est le mot de passe administrateur.
- **Pas de mode regex fallback.** Rogier v0.1 ne parse **que** le format HTML Justel. Tout autre format est rejeté avec un message d'erreur clair.
- **Pas d'extraction depuis PDF.** Pas de pymupdf4llm. Uniquement HTML.
- **Pas de système de presets importables / exportables.** La configuration d'un document reste attachée au document lui-même, avec versioning interne. Il n'y a pas de « preset partageable » en v0.1.
- **Pas d'export multi-fichiers par niveau hiérarchique.** Uniquement un fichier Markdown unique + son manifest JSON. L'export découpé par livre est prévu pour v0.2.
- **Pas de détection de famille.** Tout est Justel HTML, la famille est fixée.
- **Pas de multi-utilisateurs.** Un seul login, une seule instance.
- **Pas de base de données.** Stockage JSON sur disque avec verrouillage fcntl, comme dans le cahier des charges initial.
- **Pas de Docker.** Déploiement direct via systemd + nginx sur Ubuntu 24.
- **Pas de serveur MCP.** Pas encore.

### 1.3 Cible documentaire

La **seule** source acceptée en v0.1 est une page HTML servie par `https://www.ejustice.just.fgov.be/cgi_loi/change_lg.pl?...`. Cette source a été inspectée en détail sur le Code des sociétés et des associations (CSA) et les patterns structurels sont documentés en §7.

L'objectif de référence pour v0.1 est de parser **correctement le CSA complet** (1 278 articles, 18 livres) et de produire un export Markdown utilisable dans un système RAG.

### 1.4 Utilisation prévue

Rogier v0.1 est conçu pour un usage **solo** par son auteur, déployé sur un VPS Linux Ubuntu 24. Exposition publique minimale, derrière un reverse proxy nginx avec HTTPS. Pas de multi-tenant, pas d'inscription, un seul compte administrateur.

---

## 2. Stack technique figée

Les choix techniques ci-dessous ne sont pas négociables sauf si un obstacle technique réel émerge, auquel cas demander.

### 2.1 Langage et runtime

- **Python 3.11 ou 3.12** (pas 3.10, pas 3.13 encore)
- `from __future__ import annotations` en tête de chaque fichier .py
- Type hints obligatoires sur toutes les signatures publiques

### 2.2 Frameworks et bibliothèques

| Rôle | Choix imposé | Justification |
|---|---|---|
| Serveur web | **FastAPI** + **Uvicorn** | Léger, asynchrone natif, bonne DX |
| Templates | **Jinja2** | Livré avec FastAPI via `starlette` |
| Frontend | **HTML + CSS vanilla** + JS minimal | Pas de React, pas de Vue, pas de build step |
| Stockage | **JSON sur disque** + `fcntl` pour verrouillage | Simplicité, auditabilité |
| Auth | **itsdangerous** (cookies signés) + **bcrypt** (hash mdp) | Standard, robuste, peu de code |
| Fetcher HTTP | **httpx** | Moderne, supporte async, rate limiting implémentable |
| Parser HTML | **stdlib `re`** + logique manuelle, éventuellement **BeautifulSoup4** si besoin | Le prototype validé utilise uniquement `re`, c'est suffisant |
| Tests | **pytest** | Standard Python |
| Env vars | **python-dotenv** (dev uniquement) | Variables système en prod |
| Templating MDs | Aucune dépendance | Génération directe par `str.join` et f-strings |

### 2.3 Ce qui est explicitement interdit

- Pas de **Django** (trop lourd)
- Pas de **SQLAlchemy** ni ORM (pas de BDD)
- Pas de **React**, **Vue**, **Svelte**, aucun framework frontend
- Pas de **Webpack**, **Vite**, aucun bundler
- Pas de **Docker** (ni `Dockerfile`, ni `docker-compose.yml` dans la v0.1)
- Pas de **Celery**, **Redis**, **RabbitMQ** (pas de tâches asynchrones nécessaires)
- Pas de **gunicorn** (uvicorn suffit avec `--workers 2`)
- Pas de **logging externe** (Sentry, Datadog) — uniquement logging standard Python vers stdout et fichier

### 2.4 Versions et dépendances

Le fichier `pyproject.toml` doit fixer les versions majeures mais laisser les mineures flexibles :

```toml
[project]
name = "rogier"
version = "0.1.0"
requires-python = ">=3.11,<3.13"
dependencies = [
    "fastapi>=0.110,<1.0",
    "uvicorn[standard]>=0.27,<1.0",
    "jinja2>=3.1,<4.0",
    "httpx>=0.26,<1.0",
    "itsdangerous>=2.1,<3.0",
    "bcrypt>=4.1,<5.0",
    "python-dotenv>=1.0,<2.0",
    "python-multipart>=0.0.9,<1.0",  # pour l'upload
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0,<9.0",
    "pytest-asyncio>=0.23,<1.0",
    "httpx[cli]",  # pour tester les routes
]
```

Pas de `requirements.txt` séparé : tout est dans `pyproject.toml`. Le fichier `requirements.txt` reste optionnel et, s'il existe, est généré par `pip-compile` ou `uv` pour le déploiement reproductible.

### 2.5 Style et outillage

- **Formatage** : `ruff format` (équivalent `black`)
- **Linting** : `ruff check` avec règles par défaut + `E`, `F`, `I`, `N`, `UP`, `B`, `SIM`
- **Type check** : optionnel, `mypy` bienvenu mais pas bloquant pour v0.1
- **Ligne max** : 100 caractères

---

## 3. Interdictions non-négociables

Cette section liste ce qui **ne doit jamais apparaître** dans le code Rogier v0.1, quelles que soient les circonstances.

### 3.1 Sécurité

- **Aucun secret en dur.** Aucune clé API, aucun mot de passe, aucun token en valeur littérale dans le code. Les secrets sont lus strictement via `os.environ[...]` et l'application **refuse de démarrer** si une variable requise manque.
- **Aucune valeur par défaut sensible.** La fonction `os.environ.get("X", "default_password")` est interdite. Toujours `os.environ["X"]` avec échec clair au démarrage si absent.
- **Aucun `shell=True`** dans les appels `subprocess`. Toujours la forme liste d'arguments.
- **Aucun fichier écrit hors du répertoire `data/`** du projet, sauf logs (explicites, configurés).
- **Aucune désérialisation `pickle`** d'un input utilisateur. JSON exclusivement.
- **Aucun `eval`** ni `exec` sur du contenu provenant de l'utilisateur.

### 3.2 Qualité de code

- **Aucun `except Exception: pass`** ni `except: pass`. Toujours attraper une exception précise, logger explicitement, et soit relever, soit retourner un état d'erreur documenté.
- **Aucun `print` en dehors des scripts utilitaires** (`scripts/`). Le code applicatif utilise `logging`.
- **Aucun `import *`**.
- **Aucun code mort.** Pas de fonctions non utilisées, pas d'imports inutiles.
- **Aucun fichier de plus de 500 lignes** sans justification écrite dans un commentaire en tête.
- **Aucune fonction de plus de 50 lignes** sans justification.

### 3.3 Dérive de périmètre

- **Aucune feature ajoutée « en passant »** qui ne soit pas listée dans ce document.
- **Aucun endpoint LLM**, aucun appel `openai`, `anthropic`, `httpx` vers `api.openrouter.ai`, etc.
- **Aucun import de `lxml`**, `pymupdf4llm`, `bluebell`, `akomantoso`, ou toute lib liée à AKN ou au PDF, dans le code livré. Ces libs sont reportées à v0.2+.

### 3.4 Réseau

- **Aucune requête HTTP sortante sans rate limiting.** Les appels à Justel sont espacés d'au moins 5 secondes et passent par le module `fetching/justel_fetcher.py` qui centralise cette logique.
- **Aucun décodage implicite du texte Justel.** L'encodage `windows-1252` est explicité à chaque fetch (voir §6).
- **Aucun scraping massif parallèle.** Une requête à la fois, jamais d'async concurrent sur le même domaine.

---

## 4. Modèle de données

### 4.1 Structures principales

Toutes les structures sont des `@dataclass` Python, sérialisables en JSON via `dataclasses.asdict`. Les types complexes imbriqués sont reconstruits à la lecture par des fonctions `from_dict` explicites (pas d'auto-hydratation magique).

```python
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class NodeKind(str, Enum):
    DOCUMENT = "DOCUMENT"
    PARTIE = "PARTIE"
    LIVRE = "LIVRE"
    TITRE = "TITRE"
    CHAPITRE = "CHAPITRE"
    SECTION = "SECTION"
    SOUS_SECTION = "SOUS_SECTION"
    ARTICLE = "ARTICLE"


@dataclass
class ModificationMarker:
    """Marqueur [N...]N trouvé dans un contenu d'article.

    Ne contient pas la référence à la loi source (pas disponible inline
    dans le HTML Justel). Pour v0.1, on préserve juste le numéro et
    les positions. L'enrichissement avec la loi source viendra en v0.2.
    """
    number: int              # le N du [N...]N
    start_pos: int           # position de début dans content (après nettoyage)
    end_pos: int             # position de fin


@dataclass
class NodeMetadata:
    """Métadonnées attachées à un nœud de l'arbre."""
    source_range: tuple[int, int] | None = None  # positions dans le HTML brut, pour debug
    warnings: list[str] = field(default_factory=list)
    modifications: list[ModificationMarker] = field(default_factory=list)


@dataclass
class Node:
    """Nœud de l'arbre document. Tous les niveaux partagent la même classe."""
    kind: NodeKind
    number: str = ""          # '1re', '1er', '1:1', '1:14/1'
    title: str = ""           # 'Dispositions générales' (vide pour les articles sauf titre explicite)
    content: str = ""         # uniquement renseigné pour les ARTICLE
    metadata: NodeMetadata = field(default_factory=NodeMetadata)
    children: list[Node] = field(default_factory=list)

    @property
    def label(self) -> str:
        if self.kind == NodeKind.DOCUMENT:
            return self.title or "Document"
        if self.kind == NodeKind.ARTICLE:
            return f"Art. {self.number}"
        return f"{self._kind_label()} {self.number}"

    def _kind_label(self) -> str:
        return {
            NodeKind.PARTIE: "Partie",
            NodeKind.LIVRE: "Livre",
            NodeKind.TITRE: "Titre",
            NodeKind.CHAPITRE: "Chapitre",
            NodeKind.SECTION: "Section",
            NodeKind.SOUS_SECTION: "Sous-section",
        }.get(self.kind, self.kind.value)


@dataclass
class ChunkingConfig:
    """Paramètres du chunker."""
    strategy: str = "per_article"  # 'per_article' ou 'hybrid'
    hybrid_threshold: int = 2000    # caractères (déclenchement du mode hybride)
    max_chunk_size: int = 5000      # alerte si dépassé
    include_breadcrumb: bool = True
    breadcrumb_levels: list[str] = field(default_factory=list)  # vide = tous les niveaux présents
    include_node_titles: bool = True  # inclure les titres humains dans le breadcrumb


@dataclass
class ValidationConfig:
    """Invariants sémantiques paramétrables par document."""
    must_contain: list[str] = field(default_factory=list)
    must_not_contain: list[str] = field(default_factory=list)


@dataclass
class DocumentConfig:
    """Configuration complète d'un document (versionnée)."""
    chunking: ChunkingConfig = field(default_factory=ChunkingConfig)
    validation: ValidationConfig = field(default_factory=ValidationConfig)
    # Modifications manuelles appliquées aux nœuds (path -> nouveau contenu)
    # path = liste d'indices ['children', 0, 'children', 3, ...] ou identifiant stable
    manual_edits: dict[str, str] = field(default_factory=dict)


@dataclass
class VersionRef:
    """Référence courte vers une version, stockée dans Document.versions."""
    id: str
    created_at: str
    label: str


@dataclass
class Version:
    """Version complète d'une configuration. Stockée séparément."""
    id: str                           # uuid4
    document_hash: str                # hash du Document parent
    created_at: str                   # ISO datetime
    label: str                        # auto-généré, ex: "Édition manuelle Art. 1:1"
    note: str = ""                    # optionnel, saisi par l'utilisateur
    config: DocumentConfig = field(default_factory=DocumentConfig)
    parent_id: str | None = None      # version précédente


@dataclass
class Document:
    """Document complet : arbre + métadonnées + historique."""
    hash: str                         # sha256 du HTML source
    name: str                         # nom affiché, éditable
    source_url: str | None = None     # si fetchée depuis Justel
    source_filename: str | None = None  # si uploadée depuis un fichier
    created_at: str = ""
    family: str = "justel_html"       # fixé en v0.1
    tree: Node = field(default_factory=lambda: Node(kind=NodeKind.DOCUMENT))
    raw_html_path: str = ""           # chemin relatif vers le HTML d'origine mis en cache
    current_version_id: str = ""      # pointeur vers la version active
    versions: list[VersionRef] = field(default_factory=list)
    schema_version: int = 1           # incrémenté à chaque évolution du modèle
```

### 4.2 Règles d'invariant du modèle

- Le **seul** niveau obligatoirement présent dans tout arbre parsé est `NodeKind.ARTICLE`. Tous les autres niveaux intermédiaires sont optionnels et dépendent de la structure réelle du texte.
- Un `Node` de kind `ARTICLE` n'a **jamais** d'enfants en v0.1 (pas de parsing des paragraphes `§` comme nœuds distincts — ils restent dans `content`).
- Un `Node` de kind non-ARTICLE a un `content` vide (mais pas None). Le contenu textuel est uniquement dans les feuilles ARTICLE.
- Le `schema_version` est incrémenté à chaque changement du modèle de données. Toute lecture d'un JSON de version antérieure doit passer par une fonction de migration explicite (voir §8.4).

### 4.3 Sérialisation JSON

Les dataclasses se sérialisent via `dataclasses.asdict`. Pour les `Enum`, la valeur `str` est utilisée. Pour la désérialisation, une fonction `Node.from_dict(data: dict) -> Node` récursive reconstruit l'arbre.

**Format JSON d'un Document stocké** :

```json
{
  "hash": "sha256_abc...",
  "name": "Code des sociétés et des associations",
  "source_url": "https://www.ejustice.just.fgov.be/cgi_loi/change_lg.pl?...",
  "source_filename": null,
  "created_at": "2026-04-09T15:42:00Z",
  "family": "justel_html",
  "tree": { ... structure récursive ... },
  "raw_html_path": "data/raw/sha256_abc.html",
  "current_version_id": "v-uuid4-initial",
  "versions": [
    {"id": "v-uuid4-initial", "created_at": "...", "label": "Import initial"}
  ],
  "schema_version": 1
}
```

---

## 5. Architecture et arborescence du repo

### 5.1 Arborescence cible

```
rogier/
├── rogier/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app, montage static/templates, démarrage
│   ├── config_app.py              # lecture env vars, validation au démarrage
│   ├── logging_setup.py           # configuration logging stdlib
│   ├── auth.py                    # login, cookie session, dépendance @require_login
│   ├── csrf.py                    # génération/vérification token CSRF
│   ├── errors.py                  # exceptions métier + handler FastAPI
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── paths.py               # chemins standard (data/docs/, data/versions/, data/raw/)
│   │   ├── locks.py               # helpers fcntl
│   │   ├── documents.py           # CRUD Document
│   │   ├── versions.py            # CRUD Version
│   │   └── migrations.py          # migrations schema_version
│   │
│   ├── fetching/
│   │   ├── __init__.py
│   │   ├── rate_limiter.py        # rate limit par domaine
│   │   ├── cache.py               # cache HTML local par hash d'URL
│   │   └── justel_fetcher.py      # fetch URL Justel avec encoding correct
│   │
│   ├── extraction/
│   │   ├── __init__.py
│   │   └── justel_html.py         # HTML Justel → Document (cœur technique)
│   │
│   ├── parsing/
│   │   ├── __init__.py
│   │   └── tree.py                # dataclasses Node, Document, Version, Config, etc.
│   │
│   ├── chunking/
│   │   ├── __init__.py
│   │   ├── breadcrumb.py          # construction du breadcrumb hiérarchique
│   │   ├── strategies.py          # per_article, hybrid
│   │   └── export.py              # écriture Markdown + manifest JSON
│   │
│   ├── validation/
│   │   ├── __init__.py
│   │   ├── structural.py          # invariants niveau 1
│   │   ├── semantic.py            # invariants niveau 2
│   │   └── report.py              # assemblage rapport de QC
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth_routes.py         # /login, /logout
│   │   ├── dashboard_routes.py    # /
│   │   ├── upload_routes.py       # /upload (GET + POST)
│   │   ├── document_routes.py     # /document/{hash}/tree, /document/{hash}/edit
│   │   ├── version_routes.py      # /document/{hash}/versions, rollback
│   │   └── export_routes.py       # /document/{hash}/export
│   │
│   ├── templates/
│   │   ├── base.html              # layout commun, CSRF token meta
│   │   ├── login.html
│   │   ├── dashboard.html
│   │   ├── step_upload.html
│   │   ├── step_tree.html         # affichage arbre + édition
│   │   ├── step_export.html       # config chunker + invariants + bouton export
│   │   ├── versions.html          # historique et rollback
│   │   └── error.html
│   │
│   └── static/
│       ├── css/
│       │   └── style.css          # fichier unique, CSS vanilla
│       └── js/
│           ├── tree_navigation.js # collapse/expand de l'arbre
│           └── edit_node.js       # édition inline d'un nœud
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                # fixtures communes (app de test, client httpx)
│   ├── fixtures/
│   │   ├── csa_sample.html        # sous-extrait du CSA pour tests rapides
│   │   └── constitution_sample.html  # optionnel, deuxième fixture
│   ├── test_config_app.py         # env vars requises, échec sans elles
│   ├── test_auth.py
│   ├── test_storage_documents.py
│   ├── test_storage_versions.py
│   ├── test_storage_migrations.py
│   ├── test_fetching_rate_limiter.py
│   ├── test_fetching_cache.py
│   ├── test_justel_fetcher.py     # mock httpx
│   ├── test_justel_extraction.py  # sur csa_sample.html
│   ├── test_chunking_strategies.py
│   ├── test_chunking_export.py
│   ├── test_validation_structural.py
│   ├── test_validation_semantic.py
│   ├── test_routes_auth.py
│   ├── test_routes_upload.py
│   └── test_routes_export.py
│
├── scripts/
│   ├── create_admin_password_hash.py   # utilitaire : lit ROGIER_ADMIN_PASSWORD, output le hash bcrypt
│   └── run_dev.sh                       # démarrage développement
│
├── data/                          # créé au runtime, gitignored
│   ├── docs/                      # {hash}.json par document
│   ├── versions/                  # {version_id}.json
│   └── raw/                       # {hash}.html HTML brut en cache
│
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
├── DEPLOYMENT.md
├── SPEC.md                        # ce document
└── LICENSE                        # MIT
```

### 5.2 Règles architecturales

1. **Les routes sont fines.** Une fonction de route FastAPI ne contient que : parsing de l'input, appel à une ou plusieurs fonctions pures, sérialisation de la sortie. Aucune logique métier directement dans un handler.

2. **La logique métier est dans des fonctions pures testables.** Tout le parsing, le chunking, la validation et le versioning doivent être appelables sans passer par FastAPI. C'est la préparation pour un éventuel serveur MCP en v0.3+.

3. **Le stockage est centralisé dans `storage/`.** Aucun autre module ne lit ni n'écrit directement dans `data/`. Toutes les opérations passent par `storage.documents` ou `storage.versions`.

4. **Un seul fichier CSS, un JS minimal.** Pas de framework, pas de bundler. Le JS sert uniquement aux interactions (collapse arbre, édition inline).

---

## 6. Spec du fetcher Justel

### 6.1 Module `fetching/justel_fetcher.py`

Ce module est la **seule** porte d'entrée pour récupérer du HTML depuis Justel. Toute autre partie du code qui voudrait faire une requête HTTP vers `ejustice.just.fgov.be` doit passer par lui.

### 6.2 Contraintes obligatoires

1. **Rate limiting** : au moins 5 secondes entre deux requêtes vers `ejustice.just.fgov.be`. Implémenté via `fetching/rate_limiter.py` qui maintient un timestamp par domaine et bloque si nécessaire.

2. **User-Agent identifiable** : format `Rogier/0.1 (+https://github.com/USER/rogier; contact@exemple.be)`. Le GitHub URL et l'email sont configurables via variables d'environnement `ROGIER_CONTACT_URL` et `ROGIER_CONTACT_EMAIL`, avec des valeurs par défaut génériques documentées dans `.env.example`.

3. **Encoding explicite** : la réponse HTTP est décodée via `response.content.decode("windows-1252")`. **Ne jamais** utiliser `response.text` qui devine l'encoding de manière peu fiable.

4. **Cache local** : toute réponse fetchée est stockée dans `data/raw/{sha256_url}.html` avec son ETag et sa date. Si le cache existe et a moins de 24 heures, il est réutilisé sans nouvelle requête.

5. **Timeout** : 30 secondes par requête. Au-delà, une `JustelFetchError` est levée avec un message en français : « Le serveur Justel n'a pas répondu dans les temps. Réessayez dans quelques minutes. »

6. **Gestion d'erreur HTTP** : les codes 4xx et 5xx sont transformés en `JustelFetchError` avec un message utilisateur français (pas une trace).

### 6.3 Interface publique

```python
from dataclasses import dataclass


@dataclass
class JustelFetchResult:
    url: str
    html: str                    # contenu décodé en windows-1252
    cache_hit: bool
    fetched_at: str              # ISO datetime
    content_hash: str            # sha256 du HTML brut


async def fetch_justel_url(url: str, force_refresh: bool = False) -> JustelFetchResult:
    """Fetcher une page Justel avec cache et rate limiting.

    Lève JustelFetchError en cas d'échec, avec un message utilisateur en français.
    """
    ...
```

### 6.4 Validation de l'URL

Avant tout fetch, l'URL fournie est validée :

- Doit commencer par `https://www.ejustice.just.fgov.be/` (ou `http://`, autorisé)
- Doit être une URL de type `change_lg.pl` ou un ELI `/eli/loi/...` ou `/eli/arrete/...`
- Toute URL hors de ce périmètre est rejetée avec un message clair : « Cette URL n'est pas reconnue comme une page Justel valide. Rogier accepte uniquement les textes publiés sur ejustice.just.fgov.be. »

### 6.5 Tests requis

- Test mock de `fetch_justel_url` avec httpx-mock ou équivalent
- Test : cache hit ne déclenche pas de requête
- Test : rate limiting bloque effectivement une seconde requête dans la fenêtre des 5s
- Test : URL invalide lève `JustelFetchError` avec message français
- Test : timeout lève `JustelFetchError`
- Test : encoding windows-1252 est correctement appliqué (fixture avec caractères accentués)

---

## 7. Spec du parser HTML Justel

### 7.1 Mission du module

`extraction/justel_html.py` prend en entrée un HTML Justel brut (déjà décodé en UTF-8 à ce stade, après passage par le fetcher) et produit un `Document` complet avec son arbre hiérarchique.

### 7.2 Structure du HTML Justel observée

Le HTML Justel est organisé en **4 zones séquentielles** :

```
Zone 1 : Entête + métadonnées
  Positions 0 → premier <div id="list-title-2">
  Contient : titre, date de mise à jour, liens versions archivées

Zone 2 : Table des matières
  Positions : <div id="list-title-2"> → premier <a name="LNK0001"> hors TOC
  Ancres de forme : <a name="LNKR0001"> (avec R pour "retour")
  Liens vers les ancres du corps (#LNK0001 sans R)

Zone 3 : CORPS DU TEXTE (la zone à parser)
  Ancres hiérarchiques : <a name="LNK0001"> (sans R)
  Ancres articles : <a name="Art.1:1">, <a name="Art.18:8">
  Contenu quasi plat avec <br> et &nbsp; pour la mise en forme

Zone 4 : Liste des lois modificatives
  Démarre par la chaîne "Articles modifiés"
  Contient la liste des lois ayant modifié le texte consolidé
```

**Règle de séparation TOC vs corps** : les ancres de la TOC suivent le pattern `LNKR\d+` (avec R) ; les ancres du corps suivent `LNK\d+` (sans R). C'est la règle fiable pour distinguer les deux zones.

### 7.3 Fonction `locate_body(html: str) -> str`

Isole la zone 3 en recherchant le marqueur `id="list-title-2"` (fin de la TOC), puis la première ancre `<a name="LNK0001"` située au-delà (début du corps), puis la chaîne `Articles modifiés` (début de la zone 4). Retourne la sous-chaîne du corps.

**Gestion des erreurs** : si un de ces marqueurs est absent, lève `JustelParseError` avec un message français précis indiquant quelle zone n'a pas pu être localisée. Ces cas doivent être rares mais gérés.

### 7.4 Expressions régulières centrales

Le parser utilise principalement trois regex, qui ont été validées sur le CSA complet (1 278 articles, 635 entrées hiérarchiques).

```python
import re

# Toute ancre, hiérarchique ou article
RE_ANY_ANCHOR = re.compile(r'<a name="(LNK\d+|Art\.[^"]+)"')

# Entrée hiérarchique : <a name="LNK1">PARTIE 1re.</a> Dispositions générales.
# IMPORTANT : Sous-section avant Section dans l'alternation pour éviter
# que "Section" matche d'abord comme préfixe de "Sous-section".
RE_HIERARCHY_ENTRY = re.compile(
    r'<a name="LNK\d+"[^>]*>'
    r'(PARTIE|LIVRE|TITRE|CHAPITRE|Sous-section|Section)'
    r'\s+([^<]+?)</a>'
    r'([^<]*)'
)
```

### 7.5 Fonction `find_article_content_start(raw: str) -> int`

Trouve, dans un bloc de texte HTML commençant par une ancre d'article, la position à laquelle le contenu textuel de l'article commence. Gère **deux formes** observées dans Justel :

**Forme A** (standard, 1 277 articles sur 1 278 dans le CSA) :
```html
<a name="Art.1:1">Article </a> <a href="...#Art.1:2"> 1:1</a>. Une société est...
```

**Forme B** (dernier article du document, 1 article sur 1 278) :
```html
<a name="Art.18:8" href="...">Art.</a> 18:8. Par dérogation...
```

Algorithme :

```python
def find_article_content_start(raw: str) -> int:
    i = 0
    # Sauter tous les blocs <a>...</a> successifs (1 ou 2 selon la forme)
    while True:
        while i < len(raw) and raw[i] in " \t\n\r":
            i += 1
        if raw[i:i+2] != "<a":
            break
        close = raw.find("</a>", i)
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
    # Forme A : le deuxième <a> contenait déjà le numéro, on saute juste le point
    elif i < len(raw) and raw[i] == ".":
        i += 1
    # Espaces finaux
    while i < len(raw) and raw[i] in " \t\n\r":
        i += 1
    return i
```

### 7.6 Fonction `clean_content(html: str) -> str`

Convertit un fragment HTML en texte brut lisible, en préservant les marqueurs de modification.

**Traitement des marqueurs de modification** : le HTML Justel contient des marqueurs `[1 ... ]1` (où 1 est un numéro d'amendement) signalant les portions de texte insérées ou modifiées. En v0.1, on **préserve** ces marqueurs sous une forme textuelle lisible :

```
[Δ1 Chiffre d'affaires net. Δ1]
```

Le caractère `Δ` (U+0394, delta grec capital) est utilisé comme marqueur visuel. Ça permet de retrouver facilement ces zones dans le texte final et éventuellement de les traiter en v0.2 pour enrichir les métadonnées avec les lois sources (zone 4).

Algorithme de nettoyage :

1. Convertir les marqueurs de modification ouvrants et fermants (`[<sup><font color="red">N</font></sup>` → `[ΔN `, et pareillement pour la fermeture)
2. Supprimer toutes les balises `<a>...</a>` en gardant leur contenu textuel
3. Remplacer `<br>` et `<br/>` par des sauts de ligne `\n`
4. Supprimer toutes les balises restantes (`<sup>`, `<font>`, etc.)
5. Décoder les entités HTML principales : `&nbsp;`, `&amp;`, `&lt;`, `&gt;`, `&quot;`, `&#39;`, `\xa0`
6. Normaliser les espaces : multiples espaces → un seul, lignes vides multiples → max 2

Code de référence (repris du prototype validé) :

```python
def clean_content(html: str) -> str:
    # 1. Marqueurs de modification
    html = re.sub(
        r'\[<sup><font color="red">(\d+)</font></sup>',
        r'[Δ\1 ',
        html,
    )
    html = re.sub(
        r'\]<sup><font color="red">(\d+)</font></sup>',
        r' Δ\1]',
        html,
    )
    # 2. Balises <a>
    html = re.sub(r'<a[^>]*>|</a>', '', html)
    # 3. <br>
    html = re.sub(r'<br\s*/?>', '\n', html)
    # 4. Autres balises
    html = re.sub(r'<[^>]+>', '', html)
    # 5. Entités
    for old, new in {
        '&nbsp;': ' ', '&amp;': '&', '&lt;': '<', '&gt;': '>',
        '&quot;': '"', '&#39;': "'", '\xa0': ' ',
    }.items():
        html = html.replace(old, new)
    # 6. Normalisation des espaces
    html = re.sub(r'[ \t]+', ' ', html)
    html = re.sub(r'\n[ \t]+', '\n', html)
    html = re.sub(r'\n{3,}', '\n\n', html)
    return html.strip()
```

### 7.7 Algorithme de reconstruction de l'arbre

Le HTML Justel est **plat** : toutes les ancres hiérarchiques sont au même niveau dans le DOM, sans imbrication. La hiérarchie est **implicite** via l'ordre séquentiel et le type de chaque entrée (PARTIE est plus haut que LIVRE qui est plus haut que TITRE, etc.).

La reconstruction utilise un **algorithme à pile** :

```python
LEVEL_DEPTH = {
    NodeKind.PARTIE: 0,
    NodeKind.LIVRE: 1,
    NodeKind.TITRE: 2,
    NodeKind.CHAPITRE: 3,
    NodeKind.SECTION: 4,
    NodeKind.SOUS_SECTION: 5,
}


def build_tree(entries: list[RawEntry], doc_title: str) -> Node:
    root = Node(kind=NodeKind.DOCUMENT, title=doc_title)
    stack: list[Node] = [root]
    depths: list[int] = [-1]  # profondeur du root = plus haut que tout

    for e in entries:
        if e.kind == "hierarchy":
            depth = LEVEL_DEPTH[e.level]
            # Fermer tous les conteneurs de profondeur >= courante
            while depths and depths[-1] >= depth:
                stack.pop()
                depths.pop()
            node = Node(kind=e.level, number=e.number, title=e.title)
            stack[-1].children.append(node)
            stack.append(node)
            depths.append(depth)
        else:  # article
            node = Node(kind=NodeKind.ARTICLE, number=e.number, content=e.content)
            stack[-1].children.append(node)

    return root
```

Cet algorithme gère correctement :
- Les niveaux qui sautent (un TITRE qui contient directement des ARTICLES sans CHAPITRE intermédiaire)
- Les retours à un niveau supérieur (passage de TITRE 3 dans LIVRE 1 à LIVRE 2 : referme TITRE 3, referme LIVRE 1, ouvre LIVRE 2)
- Les articles attachés au conteneur le plus profond actuellement ouvert

### 7.8 Gestion des cas de bord connus

**Cas 1 — Titres tronqués par marqueur de modification.** Dans le CSA, 3 titres (`TITRE 6/1`, `TITRE 6/2`, `TITRE 4` du Livre 3) ont leur intitulé encapsulé dans un marqueur `[1 ...]1` parce qu'ils ont été insérés par modification postérieure. La regex `RE_HIERARCHY_ENTRY` actuelle capture jusqu'au premier `<`, ce qui la fait s'arrêter au `<sup>` du marqueur, ne laissant qu'un `[` comme titre.

**Fix attendu en v0.1** : après application de la regex, si le titre capturé est exclusivement composé de `[` ou d'espaces blancs, appliquer un nettoyage secondaire qui continue la lecture à l'intérieur du marqueur de modification pour extraire le vrai titre. Algorithme proposé :

1. Si le titre brut matche `^\s*\[\s*$`, on a affaire à un titre dans une modification
2. Rechercher dans le bloc raw le pattern `\[<sup><font color="red">\d+</font></sup>([^<]+)\]<sup>` et extraire le groupe 1
3. C'est le vrai titre
4. Ajouter un warning `"Titre extrait d'un marqueur de modification"` dans les métadonnées du nœud

**Cas 2 — Article unique sans lien "suivant".** Déjà géré par `find_article_content_start` via la détection de la forme B.

**Cas 3 — Numéros d'articles avec suffixes.** Les articles peuvent avoir des numéros composés comme `1:14/1`, `1:31/2`, ou des suffixes `bis`, `ter`, `quater`. La regex extrait le numéro depuis l'ancre `<a name="Art.X">` et ne le valide pas : tout ce qui suit `Art.` dans l'ancre est accepté comme numéro. Pas de problème en pratique sur le CSA.

**Cas 4 — Entités HTML inhabituelles.** Le nettoyeur ne couvre que les entités courantes. Si une entité rare apparaît et reste dans le texte final, un warning est ajouté au nœud : `"Entité HTML non reconnue : &xyz;"`.

### 7.9 Warnings et rapport de parsing

À la fin du parsing, l'extracteur produit non seulement un `Document` mais aussi une liste de warnings qui sont :

- Stockés dans `Node.metadata.warnings` pour chaque nœud concerné
- Agrégés dans un `ParsingReport` global retourné à côté du Document

**Types de warnings à produire** :

- `"Titre extrait d'un marqueur de modification"` : cas 1 ci-dessus
- `"Contenu d'article vide"` : si un article se retrouve avec un contenu vide
- `"Contenu inhabituellement court (< 20 caractères)"` : potentiel artefact
- `"Contenu inhabituellement long (> 15000 caractères)"` : à vérifier
- `"Entité HTML non reconnue"` : normalisation incomplète
- `"Numérotation non séquentielle"` : gap ou doublon dans les numéros d'articles d'un même conteneur

Ces warnings ne bloquent **jamais** l'import. Ils sont affichés dans l'interface à côté des nœuds concernés (triangle orange cliquable) et dans le rapport de validation.

### 7.10 Tests requis

Le fichier de test `tests/test_justel_extraction.py` doit utiliser `tests/fixtures/csa_sample.html` (un sous-extrait du CSA, pas le fichier complet de 2.9 MB, à préparer à la main en prenant par exemple les 3 premiers livres). Les tests attendus :

- Parse complet : aucune exception
- Nombre de PARTIES, LIVRES, TITRES, CHAPITRES, Sections, Sous-sections correspond à un compte connu de la fixture
- Nombre d'articles correspond à un compte connu
- L'article 1:1 a un contenu non vide et contient bien la chaîne "Une société est constituée"
- L'article 1:2 contient bien "Une association est constituée"
- L'arbre est cohérent : profondeur monotone, pas de niveau plus profond que son parent
- Aucun HTML résiduel dans les contenus
- Les warnings attendus sont bien produits

**Fixture réelle complète** : un test de bout en bout utilise le fichier CSA complet (si présent dans `/home/claude` ou un chemin configurable par env var) et vérifie :
- 5 PARTIES, 18 LIVRES, 111 TITRES, 147 CHAPITRES, 227 SECTIONS, 127 SOUS_SECTIONS, 1278 ARTICLES
- Article 1:1 : 317 caractères, commence par "Une société est constituée"
- Article 7:2 : 49 caractères, contient "61 500 euros" (espace, pas point)
- Article 18:8 : ne contient pas "18:8." au début (test de régression pour le bug de la forme B)

Ce test complet est marqué `@pytest.mark.slow` et peut être skippé par défaut.

---

## 8. Spec du stockage et du versioning

### 8.1 Structure des fichiers sur disque

Tout le stockage est dans le dossier `data/`, créé au runtime et listé dans `.gitignore`.

```
data/
├── admin.json              # hash bcrypt du mdp (uniquement, pas d'autre info)
├── docs/
│   └── {hash}.json         # un Document par fichier
├── versions/
│   └── {version_id}.json   # une Version par fichier
└── raw/
    └── {hash}.html         # HTML source en cache
```

### 8.2 Verrouillage

Chaque opération d'écriture sur un fichier JSON utilise un lock `fcntl.LOCK_EX` pour éviter la corruption en cas de concurrence (même si Rogier est mono-utilisateur, un double refresh rapide peut provoquer des races).

Helper dans `storage/locks.py` :

```python
import fcntl
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def locked_write(path: Path):
    """Context manager pour écrire un fichier JSON sous lock exclusif."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)
        yield f
        f.flush()
        f.fdatasync() if hasattr(f, 'fdatasync') else None
    tmp.replace(path)  # rename atomique
```

L'écriture passe toujours par un fichier temporaire `.tmp` puis un `rename` atomique, pour éviter de laisser un JSON corrompu en cas d'interruption.

### 8.3 Versioning des configurations

À chaque modification de configuration d'un document (édition manuelle d'un nœud, changement de stratégie de chunking, ajout d'un invariant sémantique), une **nouvelle Version** est créée automatiquement :

1. Le `Document.current_version_id` est mis à jour pour pointer vers la nouvelle version
2. La nouvelle `Version` est écrite dans `data/versions/{id}.json`
3. Une `VersionRef` est ajoutée à `Document.versions`
4. Le `Document` est sauvegardé

Le `parent_id` de chaque nouvelle version pointe vers la version précédente active, formant un arbre d'historique (les rollbacks créent des branches).

**Auto-génération des labels** :

- `"Import initial"` pour la première version à la création du document
- `"Édition manuelle Art. X:Y"` pour une édition de contenu d'un article
- `"Renommage Livre N"` pour une édition de titre d'un conteneur
- `"Stratégie de chunking modifiée"` pour un changement de `ChunkingConfig`
- `"Invariants sémantiques modifiés"` pour un changement de `ValidationConfig`
- `"Restauration de la version du {date}"` pour un rollback

### 8.4 Schema version et migrations

Chaque fichier JSON de Document porte un champ `schema_version`. La constante `CURRENT_SCHEMA_VERSION = 1` est définie dans `storage/migrations.py`.

À la lecture d'un Document, si `schema_version < CURRENT_SCHEMA_VERSION`, la fonction `migrate(data, from_version) -> data` est appelée. Les migrations sont des fonctions Python nommées `migrate_v1_to_v2`, `migrate_v2_to_v3`, chaînées en pipeline :

```python
def migrate(data: dict, from_version: int) -> dict:
    migrations = {
        1: migrate_v1_to_v2,
        # 2: migrate_v2_to_v3,
        # ...
    }
    current = from_version
    while current < CURRENT_SCHEMA_VERSION:
        if current not in migrations:
            raise StorageError(f"Migration de v{current} vers v{current+1} non disponible")
        data = migrations[current](data)
        current += 1
    return data
```

**En v0.1**, il n'y a qu'une seule version du schéma (`CURRENT_SCHEMA_VERSION = 1`) et donc aucune migration à écrire. Mais l'infrastructure de migration doit être en place **dès le départ**, pour que v0.2 puisse migrer proprement depuis v0.1 sans casser les données existantes.

**Test requis** : un test unitaire vérifie que la lecture d'un JSON de schema 0 (à inventer, simulé) passerait par `migrate` ; et un test qui vérifie que la lecture d'un JSON de schema supérieur à CURRENT_SCHEMA_VERSION lève une exception claire.

### 8.5 Hash et déduplication

Le `hash` d'un Document est le SHA-256 du HTML source brut (pas du HTML nettoyé, ni du texte). Si deux uploads produisent le même hash, on refuse le deuxième avec un message : « Ce document existe déjà dans votre bibliothèque (importé le JJ/MM/AAAA). Souhaitez-vous le remplacer ? ». Si l'utilisateur confirme, l'ancien document et toutes ses versions sont supprimés, le nouveau est importé à sa place.

### 8.6 Tests requis

- Création d'un Document → fichier JSON créé correctement
- Lecture d'un Document existant → dataclass correctement reconstruite
- Édition → nouvelle Version créée, `current_version_id` mis à jour
- Rollback → nouvelle Version créée (n'écrase pas l'ancienne), label "Restauration..."
- Hash identique → refus d'import avec message
- Schema version incorrecte → migration appelée ou exception
- Concurrence : deux écritures simultanées ne corrompent pas le fichier (simulation avec threads)

---

## 9. Spec de l'interface web

### 9.1 Principes généraux

- **HTML sobre et sémantique.** Balises correctes (`<main>`, `<nav>`, `<section>`, `<article>`, `<form>`), pas de `<div>` partout.
- **Pas de framework CSS**. Un fichier `style.css` unique, écrit à la main, court (< 500 lignes).
- **JavaScript minimal.** Un fichier par page au maximum. Pas de jQuery, pas de build step. Utilisation des APIs DOM natives.
- **Toutes les interactions restent fonctionnelles sans JS** (progressive enhancement). Le JS améliore l'expérience (collapse/expand, édition inline) mais n'est jamais indispensable.
- **Messages d'erreur en français clair.** Pas de trace Python. Pas de code HTTP nu. Phrases complètes, ton neutre, proposent une action corrective quand c'est possible.
- **Pas d'emoji** dans l'interface sauf si explicitement approuvé.

### 9.2 Routes et écrans

| Méthode | Route | Écran | Authentifié ? |
|---|---|---|---|
| GET | `/login` | Login form | Non |
| POST | `/login` | Traitement login | Non |
| POST | `/logout` | Déconnexion + redirect | Oui |
| GET | `/` | Dashboard (liste documents) | Oui |
| GET | `/upload` | Formulaire upload/URL | Oui |
| POST | `/upload` | Traitement (fetch/upload + parse) | Oui |
| GET | `/document/{hash}` | Redirige vers `/document/{hash}/tree` | Oui |
| GET | `/document/{hash}/tree` | Affichage arbre + contenu nœud | Oui |
| POST | `/document/{hash}/node/{node_id}/edit` | Édition d'un nœud | Oui |
| GET | `/document/{hash}/versions` | Historique des versions | Oui |
| POST | `/document/{hash}/versions/{version_id}/restore` | Rollback | Oui |
| GET | `/document/{hash}/export` | Config export + validation | Oui |
| POST | `/document/{hash}/export` | Génération et téléchargement | Oui |
| POST | `/document/{hash}/delete` | Suppression | Oui |

### 9.3 Login

- Un formulaire simple : champ mot de passe, bouton "Se connecter"
- Pas de champ "nom d'utilisateur" (un seul utilisateur)
- Échec → message : « Mot de passe incorrect. » (pas de détail)
- Succès → cookie de session signé `itsdangerous`, redirect vers `/`
- Cookie : `httponly=True`, `secure=True` en prod (détection via env var), `samesite=Lax`, expiration 30 jours

### 9.4 Dashboard (`/`)

Contenu :

- En-tête : « Rogier — bibliothèque » + bouton « Nouveau document »
- Tableau des documents existants, colonnes :
  - Nom (cliquable → `/document/{hash}/tree`)
  - Famille (`justel_html` pour tous en v0.1)
  - Articles (nombre)
  - Dernière modification
  - Actions (bouton Supprimer avec confirmation)
- Pas de pagination en v0.1 (l'usage solo ne devrait pas générer des centaines de documents)
- Si la liste est vide : message d'accueil expliquant comment commencer

### 9.5 Upload (`/upload`)

Deux modes côte à côte :

**Mode A — Fichier local**
- Champ `<input type="file" accept=".html,.htm">`
- Limite de taille : 10 MB (variable d'env `ROGIER_MAX_UPLOAD_MB`, défaut 10)
- Validation du type MIME côté serveur
- Validation que le contenu commence bien par du HTML Justel (présence de `change_lg.pl` dans la source, présence du marqueur `list-title-2`)

**Mode B — URL Justel**
- Champ texte URL
- Validation : URL Justel valide (voir §6.4)
- Le fetch est déclenché côté serveur avec affichage d'un spinner pendant l'opération (max 30s)
- Cache : si la même URL a déjà été fetchée dans les dernières 24h, réutilise le cache

Encart de conseils pré-upload (repris du cahier initial §6.4.1) :

> **Avant d'importer un texte dans Rogier :**
> - Utilise uniquement des sources officielles : pour le droit belge, télécharge ou copie le lien depuis Justel sur ejustice.just.fgov.be.
> - Un seul code ou une seule loi par import. Rogier n'est pas conçu pour traiter plusieurs textes dans un même document.
> - Si tu veux importer le CSA, copie-colle simplement cette URL : https://www.ejustice.just.fgov.be/cgi_loi/change_lg.pl?language=fr&la=F&cn=2019032309&table_name=loi

Après traitement :

- Si parsing réussi → redirect vers `/document/{hash}/tree`
- Si parsing échoué → retour sur `/upload` avec message d'erreur clair (« Le document n'a pas pu être analysé : {raison en français}. »)
- Si parsing avec warnings → redirect vers `/document/{hash}/tree` avec une bannière jaune en haut listant les warnings principaux

### 9.6 Affichage de l'arbre (`/document/{hash}/tree`)

Layout en deux colonnes :

**Colonne gauche (35% de la largeur)** : l'arbre hiérarchique
- Chaque nœud est une entrée cliquable avec son icône (dépendant du kind), son numéro, son titre
- Les conteneurs (non-articles) sont collapsibles/expandables via un chevron cliquable
- État initial : développé jusqu'au niveau LIVRE, tout ce qui est plus profond est collapsé
- Un clic sur un nœud le charge dans la colonne droite
- Les nœuds avec warnings affichent un petit triangle orange à droite
- Barre de contrôle en haut : compteurs (X livres, Y articles), bouton « Tout développer », bouton « Tout replier »

**Colonne droite (65%)** : le contenu du nœud sélectionné
- En tête : breadcrumb complet (ex : `Code des sociétés > Partie 1re > Livre 1er > Titre 1er > Art. 1:1`)
- Contenu textuel de l'article (ou titre du conteneur + liste de ses enfants immédiats)
- Bouton « Éditer » qui bascule la zone texte en mode édition
- Métadonnées en bas : position dans le HTML brut, warnings, marqueurs de modification détectés

**Édition inline** :
- Clic « Éditer » → textarea pré-remplie avec le contenu actuel
- Boutons « Enregistrer » et « Annuler »
- Enregistrer déclenche un POST → création d'une nouvelle version → refresh de la colonne droite
- Confirmation visuelle : bandeau vert « Version enregistrée (ID v-abc123) » pendant 3 secondes

**Édition des titres de conteneurs** : même principe, textarea simplifiée pour le titre.

### 9.7 Historique des versions (`/document/{hash}/versions`)

- Liste chronologique inverse (plus récente en haut)
- Pour chaque version : date, label auto-généré, note éventuelle, bouton « Voir la config » (popup/modal), bouton « Restaurer »
- La version actuellement active est marquée par un badge « Active »
- Restauration → confirmation « Créer une nouvelle version à partir de celle-ci ? » → création d'une nouvelle Version avec le label « Restauration de la version du JJ/MM/AAAA »
- Pas de diff graphique sur les contenus en v0.1 (juste le label permet de voir ce qui a changé)

### 9.8 Export (`/document/{hash}/export`)

Page en 4 sections :

**Section 1 — Stratégie de chunking**

Deux radio buttons :
- « Un chunk par article » (défaut)
- « Chunking hybride »

Chacun avec une explication en français en-dessous (reprise du cahier initial §6.7.1).

**Paramètres avancés** (dépliables) :
- Seuil hybride (caractères) : défaut 2000 (révisé depuis le cahier initial, basé sur les articles récents sur le context rot)
- Taille max avant alerte : défaut 5000
- Case à cocher : « Inclure le breadcrumb hiérarchique en tête de chaque chunk » (défaut coché)
- Case à cocher : « Inclure les titres humains des niveaux dans le breadcrumb » (défaut coché)

**Section 2 — Invariants sémantiques**

Deux listes éditables :
- `must_contain` : liste de chaînes devant apparaître dans le corpus
- `must_not_contain` : liste de chaînes qui ne doivent pas y apparaître

Chaque ligne a un bouton « Supprimer ». Un champ + bouton « Ajouter » en bas.

Au-dessus, un bouton « Vérifier » qui lance la validation immédiatement et affiche le résultat à côté de chaque invariant (vert/rouge).

**Section 3 — Rapport de validation**

Niveau 1 (structurels) : affiché automatiquement dès le chargement de la page.
Niveau 2 (sémantiques) : actualisé au clic sur « Vérifier » ou à chaque modification de la liste.

Affichage : liste d'items avec icône ✓ (vert) ou ✗ (rouge) et détail.

Si des invariants échouent, un bandeau orange apparaît au-dessus du bouton Exporter avec le message : « Des avertissements sont présents. Vous pouvez tout de même exporter, mais vérifiez le résultat. »

**Section 4 — Export**

- Aperçu : « Le fichier exporté contiendra X chunks. Taille estimée : Y caractères. »
- Bouton « Exporter » grand et visible
- Au clic → POST → génération du `.md` → téléchargement automatique

### 9.9 Protection CSRF

Toutes les routes POST sont protégées par CSRF :

- Un token CSRF est généré à chaque session (à la connexion), stocké dans le cookie
- Le template `base.html` inclut le token dans une balise `<meta name="csrf-token" content="...">`
- Tous les formulaires incluent un `<input type="hidden" name="csrf_token" value="...">`
- Les requêtes AJAX (édition inline) incluent le token dans un header `X-CSRF-Token`
- Le serveur vérifie le token sur chaque POST ; échec → 403 avec message « Requête invalide. Merci de recharger la page. »

### 9.10 Gestion des erreurs dans l'UI

Template `error.html` pour les erreurs non gérées :
- Titre : « Une erreur est survenue »
- Message en français, pas de trace
- Bouton « Retour au tableau de bord »
- L'erreur complète est logguée côté serveur avec un ID de corrélation
- L'ID est affiché dans l'UI pour faciliter le support (« ID d'erreur : abc123 »)

---

## 10. Spec du chunker et de l'export

### 10.1 Stratégie 1 : un chunk par article

Chaque article du document devient un chunk indépendant. Pas de regroupement, pas de découpage.

Format d'un chunk :

```markdown
**[Code des sociétés et des associations > Partie 1re > Livre 1er > Titre 1er > Art. 1:1]**

Une société est constituée par un acte juridique par lequel une ou plusieurs personnes, dénommées associés, font un apport. Elle a un patrimoine et a pour objet l'exercice d'une ou plusieurs activités déterminées. Un de ses buts est de distribuer ou procurer à ses associés un avantage patrimonial direct ou indirect.
```

Le breadcrumb est en gras Markdown (`**...**`), sur une ligne, suivi d'une ligne vide, puis du contenu brut de l'article.

### 10.2 Stratégie 2 : chunking hybride

Cette stratégie découpe les articles longs par paragraphes tout en gardant les articles courts intacts.

Algorithme :

1. Pour chaque article, mesurer la longueur du contenu
2. Si `len(content) <= hybrid_threshold` (défaut 2000) → un seul chunk (comme stratégie 1)
3. Sinon : découper par paragraphes `§`
   - Détecter les paragraphes avec la regex `^§\s*(\d+(?:er|bis|ter|quater)?)\.\s*`
   - Chaque paragraphe devient un sous-chunk
   - Le titre de l'article (breadcrumb) est répété en tête de chaque sous-chunk, avec l'ajout du numéro de paragraphe
   - Si un paragraphe seul dépasse `max_chunk_size` (défaut 5000), un warning est ajouté mais le chunk reste tel quel (pas de découpage plus fin en v0.1)
4. Si un article dépasse `hybrid_threshold` mais n'a pas de paragraphes `§` (contenu en bloc continu), on le laisse en un seul chunk avec un warning.

Format d'un sous-chunk :

```markdown
**[CSA > Partie 2 > Livre 5 > Titre 2 > Art. 5:3 > § 1er]**

§ 1er. Le capital de départ est constitué... (contenu du paragraphe)
```

Le numéro du paragraphe est ajouté au breadcrumb et conservé dans le contenu (redondance volontaire pour les modèles qui ne lisent pas les métadonnées).

### 10.3 Fonction `build_breadcrumb`

```python
def build_breadcrumb(
    path: list[Node],
    include_titles: bool = True,
    levels_filter: list[str] | None = None,
) -> str:
    """Construire le breadcrumb d'un nœud à partir du chemin depuis la racine.

    Args:
        path: liste des nœuds de la racine jusqu'au nœud cible (inclus)
        include_titles: inclure ou non les titres humains (ex: 'Dispositions générales')
        levels_filter: liste des kinds à inclure ; si None, tous les niveaux présents

    Returns:
        Chaîne du type "CSA > Livre 1er > Titre 1er > Art. 1:1"
        ou "CSA > Livre 1er — Dispositions introductives > Art. 1:1" si include_titles
    """
```

### 10.4 Export Markdown — format du fichier unique

Structure du fichier `.md` exporté :

```markdown
# Code des sociétés et des associations

> Source : Justel (ejustice.just.fgov.be)
> URL : https://www.ejustice.just.fgov.be/cgi_loi/change_lg.pl?...
> Consolidé au : (date extraite de la zone 1 du HTML, si disponible)
> Nombre de chunks : 1278
> Stratégie : un chunk par article
> Exporté depuis Rogier v0.1 le JJ/MM/AAAA à HH:MM

---

**[Code des sociétés et des associations > Partie 1re > Livre 1er > Titre 1er > Art. 1:1]**

Une société est constituée...

---

**[Code des sociétés et des associations > Partie 1re > Livre 1er > Titre 1er > Art. 1:2]**

Une association est constituée...

---

... (1276 chunks suivants)
```

Séparateur entre chunks : une ligne vide, `---`, une ligne vide.

### 10.5 Export du manifest JSON

À côté du fichier `.md`, un fichier `.manifest.json` contient les métadonnées de l'export :

```json
{
  "document_hash": "sha256_abc...",
  "document_name": "Code des sociétés et des associations",
  "source_url": "https://www.ejustice.just.fgov.be/...",
  "exported_at": "2026-04-09T16:45:00Z",
  "exporter": "Rogier v0.1",
  "strategy": "per_article",
  "parameters": {
    "hybrid_threshold": 2000,
    "max_chunk_size": 5000,
    "include_breadcrumb": true,
    "include_node_titles": true
  },
  "stats": {
    "total_chunks": 1278,
    "min_chunk_size": 49,
    "max_chunk_size": 12804,
    "avg_chunk_size": 1112,
    "median_chunk_size": 663
  },
  "version_id": "v-uuid4-current",
  "validation": {
    "structural": "pass",
    "semantic": "pass",
    "warnings": []
  }
}
```

### 10.6 Téléchargement

L'export produit les deux fichiers dans un dossier temporaire, puis :
- Si un seul fichier → téléchargement direct du `.md`
- En v0.1, on ne fait pas de ZIP : on renvoie uniquement le `.md` via HTTP. Le manifest est stocké côté serveur à côté du document et consultable via une URL dédiée `/document/{hash}/export/manifest`.
- En v0.2, on passera en ZIP avec les deux fichiers dedans.

### 10.7 Tests requis

- Export per_article sur la fixture CSA → nombre de chunks = nombre d'articles
- Chaque chunk commence par `**[...]**` suivi d'une ligne vide
- Breadcrumb correct pour Art. 1:1 et Art. 7:2
- Export hybrid : les articles < threshold restent en un chunk ; les articles >= threshold sont découpés
- Le manifest JSON contient les bonnes stats (nombres calculés à partir du corpus)
- Les invariants sémantiques sont appliqués à l'export : `must_contain` matche bien sur le texte exporté

---

## 11. Spec de la validation

### 11.1 Niveau 1 — Invariants structurels

Appliqués automatiquement à chaque parsing, stockés dans le rapport du document. Réévalués à chaque édition.

Liste des invariants niveau 1 :

| ID | Description | Échec signifie |
|---|---|---|
| `S001` | Au moins 1 article dans le document | Parser ne trouve rien |
| `S002` | Tous les articles ont un contenu non vide | Contenu perdu |
| `S003` | Aucun article n'a une longueur < 20 caractères | Parsing incomplet |
| `S004` | Aucun article n'a une longueur > 20000 caractères | Probable fusion involontaire |
| `S005` | Numérotation des articles monotone dans chaque conteneur | Désordre |
| `S006` | Aucun doublon d'identifiant d'article | Conflit |
| `S007` | Profondeur maximale de l'arbre <= 7 (DOC + 6 niveaux) | Arbre anormal |
| `S008` | Tous les warnings de parsing sont listés | Cohérence du rapport |

Chaque invariant produit un résultat `pass` / `fail` avec un détail explicatif en français.

### 11.2 Niveau 2 — Invariants sémantiques

Paramétrables par l'utilisateur via l'écran d'export. Stockés dans `DocumentConfig.validation`.

- `must_contain`: liste de chaînes (littérales, pas regex en v0.1 pour éviter les surprises)
- `must_not_contain`: liste de chaînes (littérales)

Pour chaque chaîne de `must_contain`, vérifier que la chaîne apparaît au moins une fois dans le texte concaténé de tous les articles. Pour `must_not_contain`, vérifier l'absence.

Exemples d'invariants pour le CSA :
- `must_contain: ["61 500", "Art. 1:1", "Code des sociétés"]`
- `must_not_contain: ["Table des matières", "Page \\d+"]`

**Note importante** : les invariants du cahier des charges initial mentionnaient `"61.500"` (avec point). Le prototype a révélé que Justel utilise `61 500` avec espace. Les invariants doivent être construits sur **données réelles observées**, pas devinés.

### 11.3 Rapport de validation

Produit par `validation/report.py`, c'est une dataclass :

```python
@dataclass
class ValidationReport:
    structural: list[InvariantResult]
    semantic: list[InvariantResult]
    overall: str  # 'pass' | 'warnings' | 'fail'
    generated_at: str


@dataclass
class InvariantResult:
    id: str              # 'S001', 'must_contain:61 500'
    level: int           # 1 ou 2
    description: str
    status: str          # 'pass' | 'fail'
    detail: str          # explication en français, visible dans l'UI
```

Affichage dans l'UI export (§9.8) : liste d'items avec icônes vert/rouge.

### 11.4 Tests requis

- Chaque invariant niveau 1 a un test positif (arbre correct → pass) et un test négatif (arbre corrompu → fail)
- Invariants sémantiques : test avec strings présentes → pass, absentes → fail
- Test du rapport global : un doc sain produit `overall = "pass"`

---

## 12. Sécurité

### 12.1 Variables d'environnement requises

L'application **refuse de démarrer** si une de ces variables manque. Le démarrage échoue avec un message d'erreur en français listant la ou les variables manquantes, affiché sur stderr, code de sortie non nul.

| Variable | Description | Exemple (fictif) |
|---|---|---|
| `ROGIER_SECRET_KEY` | Clé de signature des cookies (itsdangerous). Min 32 octets aléatoires | `$(openssl rand -hex 32)` |
| `ROGIER_ADMIN_PASSWORD_HASH` | Hash bcrypt du mot de passe administrateur | `$2b$12$...` |
| `ROGIER_DATA_DIR` | Chemin du répertoire de données | `/var/lib/rogier/data` |

Variables optionnelles (avec valeurs par défaut sûres) :

| Variable | Description | Défaut |
|---|---|---|
| `ROGIER_MAX_UPLOAD_MB` | Taille max upload HTML | `10` |
| `ROGIER_CONTACT_URL` | URL du projet (pour User-Agent) | `https://github.com/` |
| `ROGIER_CONTACT_EMAIL` | Email de contact (pour User-Agent) | `noreply@example.com` |
| `ROGIER_SESSION_MAX_AGE_DAYS` | Durée de session | `30` |
| `ROGIER_LOG_LEVEL` | Niveau de log | `INFO` |
| `ROGIER_DEV_MODE` | Mode développement (désactive `secure=True` sur les cookies) | `0` |

### 12.2 Fichier `.env.example`

À produire à la racine du repo, documenté :

```env
# Rogier — Variables d'environnement
#
# Copier ce fichier vers .env et remplir les valeurs.
# NE JAMAIS commiter le fichier .env.
#
# Pour générer une clé secrète sûre :
#   openssl rand -hex 32
#
# Pour générer le hash bcrypt du mot de passe administrateur :
#   python scripts/create_admin_password_hash.py

# --- Variables obligatoires ---

# Clé de signature des cookies de session
# REMPLACER obligatoirement avant le premier démarrage.
ROGIER_SECRET_KEY=CHANGE_THIS_BEFORE_RUNNING_openssl_rand_hex_32

# Hash bcrypt du mot de passe administrateur
# À générer avec scripts/create_admin_password_hash.py
# REMPLACER obligatoirement.
ROGIER_ADMIN_PASSWORD_HASH=CHANGE_THIS_BEFORE_RUNNING

# Répertoire de stockage des données (créé automatiquement au démarrage)
ROGIER_DATA_DIR=./data

# --- Variables optionnelles ---

# Taille maximale des uploads HTML, en mégaoctets
ROGIER_MAX_UPLOAD_MB=10

# Métadonnées pour le User-Agent des requêtes Justel
ROGIER_CONTACT_URL=https://github.com/utilisateur/rogier
ROGIER_CONTACT_EMAIL=contact@exemple.be

# Durée de validité des sessions, en jours
ROGIER_SESSION_MAX_AGE_DAYS=30

# Niveau de log (DEBUG, INFO, WARNING, ERROR)
ROGIER_LOG_LEVEL=INFO

# Mode développement (désactive la flag secure des cookies pour HTTP localhost)
# Mettre à 0 en production, à 1 en dev local.
ROGIER_DEV_MODE=0
```

**Important** : la valeur `CHANGE_THIS_BEFORE_RUNNING` dans le fichier provoque un échec au démarrage. Le fichier `config_app.py` détecte cette chaîne exacte et refuse de démarrer avec un message explicite.

### 12.3 Script de génération du hash

`scripts/create_admin_password_hash.py` :

```python
"""Générer un hash bcrypt pour le mot de passe administrateur.

Usage:
    python scripts/create_admin_password_hash.py

Le mot de passe est demandé en interactif (getpass), jamais affiché.
Le hash est imprimé sur stdout, à copier dans la variable d'environnement
ROGIER_ADMIN_PASSWORD_HASH.
"""
import getpass
import sys

import bcrypt


def main() -> int:
    pw1 = getpass.getpass("Mot de passe : ")
    if len(pw1) < 10:
        print("Erreur : le mot de passe doit faire au moins 10 caractères.", file=sys.stderr)
        return 1
    pw2 = getpass.getpass("Confirmer : ")
    if pw1 != pw2:
        print("Erreur : les mots de passe ne correspondent pas.", file=sys.stderr)
        return 1
    hashed = bcrypt.hashpw(pw1.encode("utf-8"), bcrypt.gensalt(rounds=12))
    print(hashed.decode("utf-8"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

### 12.4 Vérification au démarrage

Dans `config_app.py`, une fonction `validate_config()` appelée au démarrage de FastAPI :

1. Vérifie que toutes les variables obligatoires sont présentes
2. Vérifie que `ROGIER_SECRET_KEY` n'est pas `CHANGE_THIS_BEFORE_RUNNING_...`
3. Vérifie que `ROGIER_ADMIN_PASSWORD_HASH` commence par `$2b$` (format bcrypt)
4. Vérifie que `ROGIER_DATA_DIR` est un chemin accessible en écriture
5. Crée les sous-dossiers `data/docs/`, `data/versions/`, `data/raw/` si absents
6. Affiche un message de confirmation au démarrage : « Rogier démarre avec ROGIER_DATA_DIR=/chemin/absolu »

En cas d'échec, message d'erreur en français sur stderr et `sys.exit(1)`.

### 12.5 CSRF

Implémentation dans `csrf.py` :

- À la connexion, un token aléatoire de 32 octets est généré et stocké en base64 dans le cookie de session (signé par itsdangerous)
- Le template `base.html` l'expose via `<meta name="csrf-token" content="{{ csrf_token }}">`
- Tous les formulaires incluent un `<input type="hidden" name="csrf_token" value="{{ csrf_token }}">`
- Les requêtes AJAX envoient le token dans un header `X-CSRF-Token`
- Le serveur vérifie la concordance entre le token envoyé et celui du cookie ; échec → 403

### 12.6 Gitignore

```
# Rogier .gitignore
.env
.env.local
data/
*.pyc
__pycache__/
.venv/
venv/
.vscode/
.idea/
.pytest_cache/
.mypy_cache/
.ruff_cache/
*.egg-info/
dist/
build/
*.log
.DS_Store
```

### 12.7 Audit avant premier commit

Avant tout premier `git commit`, Claude Code doit vérifier à la main (ou par script) qu'aucun fichier commité ne contient :

- Une chaîne ressemblant à un mot de passe en clair
- Une clé API
- Un hash bcrypt réel (au-delà de l'exemple fictif dans `.env.example`)
- Un chemin absolu contenant un nom d'utilisateur

Un script `scripts/audit_secrets.sh` peut effectuer cette vérification avec `grep -rE "(password|secret|key)\s*=\s*['\"][^'\"]{8,}" rogier/ tests/`.

---

## 13. Règles de qualité de code

### 13.1 Python

- **Type hints partout**, y compris les retours. `from __future__ import annotations` en tête de chaque fichier.
- **Dataclasses** pour toutes les structures (Document, Node, Version, Config, etc.). Pas de dictionnaires non structurés qui circulent entre fonctions.
- **Fonctions pures testables** : toute la logique de parsing, validation, chunking est dans des fonctions qui prennent des entrées et retournent des sorties, sans effet de bord. Les routes FastAPI appellent ces fonctions, pas l'inverse.
- **Pas de `except Exception: pass` silencieux.** Catch spécifique, log explicite, message utilisateur en français clair.
- **Logging** via le module standard `logging`, format propre, niveau configurable par `ROGIER_LOG_LEVEL`. Jamais de `print` en production.
- **Aucun `import *`**, aucun code mort, aucune dépendance non utilisée.
- **Nommage** : fonctions et variables en `snake_case`, classes en `PascalCase`, constantes en `UPPER_SNAKE_CASE`, fichiers en `snake_case.py`.
- **Commentaires en français** pour la logique métier, docstrings courtes en français pour chaque fonction publique.
- **Imports organisés** : stdlib d'abord, tiers ensuite, interne en dernier, séparés par des lignes vides. Gérable par `ruff` automatiquement.

### 13.2 Tests

Livre des tests pour chaque module critique. Framework : `pytest`. Objectif : **toute fonction métier non triviale a au moins un test**. La couverture exacte n'est pas un objectif mais la présence de tests sur le parser, le chunker, la validation et le stockage est **non négociable**.

Structure des tests :

- **Unit** : une fonction pure testée avec des entrées/sorties
- **Integration** : un module testé en interaction avec le stockage ou le fetcher
- **End-to-end** : un parcours complet (upload → parse → export) via le client FastAPI

Tous les tests passent avec `pytest` sans erreur ni warning. `pytest -q` comme commande de référence.

### 13.3 Documentation livrée dans le repo

À la racine :

- **README.md** : présentation du projet, référence à Charles Rogier (sobre), installation rapide pour développeur, lien vers DEPLOYMENT.md, mention de la licence MIT. Captures d'écran en placeholder (à ajouter après v0.1 fonctionnelle).
- **DEPLOYMENT.md** : déploiement pas à pas sur Ubuntu 24, avec systemd + nginx + HTTPS (certbot). Commandes exactes copiables. Section « En cas de problème » listant les erreurs les plus probables.
- **SPEC.md** : ce document.
- **CONTRIBUTING.md** : comment cloner, installer, lancer les tests, convention de commits. Court, 1 page.
- **LICENSE** : texte MIT standard.
- **.env.example** : documenté.

---

## 14. Phasage d'implémentation

Les phases doivent être exécutées dans l'ordre. **Chaque phase se termine par un commit Git et un message de fin de phase** à l'utilisateur listant ce qui a été fait, comment tester, et ce qui reste.

### Phase 0 — Fondations (1 jour)

- [ ] Création du repo, arborescence complète (dossiers vides avec `.gitkeep` si nécessaire)
- [ ] `pyproject.toml`, `.gitignore`, `.env.example`, `README.md` minimal, `LICENSE`
- [ ] `rogier/config_app.py` avec validation des env vars
- [ ] `rogier/logging_setup.py`
- [ ] `rogier/main.py` avec une route `GET /` qui retourne « Rogier démarre » si authentifié sinon redirect `/login`
- [ ] `rogier/auth.py` avec login/logout et vérification bcrypt
- [ ] Templates `base.html` et `login.html`
- [ ] `scripts/create_admin_password_hash.py`
- [ ] Tests : `test_config_app.py` (démarrage échoue sans env vars), `test_auth.py` (login OK / KO)
- [ ] **Commit** : `init : squelette projet, auth, config`

**Validation de phase 0** : `python -m rogier.main` démarre sur localhost:8000 avec `.env` correctement rempli, `GET /login` affiche le formulaire, login correct redirige vers `/`, login incorrect affiche l'erreur.

### Phase 1 — Stockage et modèle de données (1-2 jours)

- [ ] `rogier/parsing/tree.py` : toutes les dataclasses du §4
- [ ] `rogier/storage/paths.py`, `locks.py`
- [ ] `rogier/storage/documents.py` : CRUD complet
- [ ] `rogier/storage/versions.py` : CRUD complet
- [ ] `rogier/storage/migrations.py` : infrastructure (sans migrations réelles puisque schema_version = 1)
- [ ] Tests : `test_storage_documents.py`, `test_storage_versions.py`, `test_storage_migrations.py`
- [ ] **Commit** : `stockage : modèle de données et persistance JSON`

**Validation** : `pytest tests/test_storage_*` passe. Un Document créé, enregistré, relu, modifié, versionné fonctionne bout en bout.

### Phase 2 — Fetcher Justel (1 jour)

- [ ] `rogier/fetching/rate_limiter.py`
- [ ] `rogier/fetching/cache.py`
- [ ] `rogier/fetching/justel_fetcher.py`
- [ ] Exceptions `JustelFetchError` dans `errors.py`
- [ ] Tests : `test_fetching_rate_limiter.py`, `test_fetching_cache.py`, `test_justel_fetcher.py` (mock httpx)
- [ ] **Commit** : `fetching : client Justel avec cache et rate limit`

**Validation** : les tests passent. Un fetch réel vers une URL Justel fonctionne (test manuel, facultatif, respectueux des limites).

### Phase 3 — Parser HTML Justel (3 jours)

- [ ] `rogier/extraction/justel_html.py` : reprendre le prototype validé, le nettoyer, le documenter
- [ ] Fix du cas des titres tronqués dans les modifications (cas 1 de §7.8)
- [ ] Intégration des warnings dans les nœuds
- [ ] Fixture `tests/fixtures/csa_sample.html` : sous-extrait du CSA (les 3 premiers livres environ)
- [ ] Tests : `test_justel_extraction.py` complet avec toutes les assertions du §7.10
- [ ] Test lent marqué `@pytest.mark.slow` sur le CSA complet
- [ ] **Commit** : `extraction : parser HTML Justel`

**Validation** : le parser produit un arbre complet sur le CSA complet, avec 1278 articles, 18 livres. L'article 1:1 est lisible. Les 3 titres précédemment tronqués (TITRE 6/1, 6/2, 4) ont maintenant leur vrai titre.

### Phase 4 — Interface web étapes 1 et 2 (3 jours)

- [ ] Templates `dashboard.html`, `step_upload.html`, `step_tree.html`
- [ ] Routes `dashboard_routes.py`, `upload_routes.py`, `document_routes.py`
- [ ] CSS `style.css`
- [ ] JS `tree_navigation.js` (collapse/expand)
- [ ] CSRF dans `csrf.py`
- [ ] Gestion d'erreur avec `error.html`
- [ ] Tests : `test_routes_auth.py`, `test_routes_upload.py`
- [ ] **Commit** : `ui : dashboard, upload, affichage arbre`

**Validation** : parcours complet depuis le login jusqu'à l'affichage du CSA en arbre, via upload de fichier et via URL Justel.

### Phase 5 — Édition manuelle et versioning (2 jours)

- [ ] JS `edit_node.js` pour l'édition inline
- [ ] Route POST `/document/{hash}/node/{node_id}/edit`
- [ ] Templates et routes `versions.html`, `version_routes.py`
- [ ] Auto-génération des labels de version
- [ ] Tests : `test_versioning.py`
- [ ] **Commit** : `ui : édition inline et historique`

**Validation** : édition d'un article crée une nouvelle version, l'historique est visible, le rollback fonctionne.

### Phase 6 — Chunker et export (2 jours)

- [ ] `rogier/chunking/breadcrumb.py`
- [ ] `rogier/chunking/strategies.py` : `per_article`, `hybrid`
- [ ] `rogier/chunking/export.py` : Markdown + manifest JSON
- [ ] Template `step_export.html`
- [ ] Route `export_routes.py`
- [ ] Tests : `test_chunking_strategies.py`, `test_chunking_export.py`
- [ ] **Commit** : `chunking : stratégies et export Markdown`

**Validation** : export per_article du CSA produit un fichier .md avec 1278 chunks séparés. Export hybrid fonctionne sur un article long (par exemple Art. 3:6 qui fait 12804 caractères).

### Phase 7 — Validation et QC (1 jour)

- [ ] `rogier/validation/structural.py` avec les invariants S001-S008
- [ ] `rogier/validation/semantic.py`
- [ ] `rogier/validation/report.py`
- [ ] Affichage du rapport dans `step_export.html`
- [ ] Tests : `test_validation_structural.py`, `test_validation_semantic.py`
- [ ] **Commit** : `validation : invariants et rapport de QC`

**Validation** : sur le CSA, tous les invariants niveau 1 passent. Un invariant sémantique `must_contain: ["61 500"]` passe au vert. Un invariant `must_not_contain: ["Table des matières"]` passe au vert (puisque la TOC est exclue par le parser).

### Phase 8 — Finitions (2 jours)

- [ ] DEPLOYMENT.md complet
- [ ] README.md complet avec placeholders de captures
- [ ] CONTRIBUTING.md
- [ ] Audit des secrets avec `scripts/audit_secrets.sh`
- [ ] Tests de bout en bout dans `test_e2e.py` (parcours complet upload → export)
- [ ] Polishing des messages d'erreur en français
- [ ] **Commit** : `docs : README, DEPLOYMENT, finitions`

**Validation** : tous les tests passent. Un non-développeur peut suivre DEPLOYMENT.md pour déployer sur un VPS neuf.

**Total estimé** : 15-20 jours de travail Claude Code, soit environ 3 semaines calendaires à temps partiel.

---

## 15. Tests d'acceptation

Rogier v0.1 est livrable quand **tous** les points suivants sont vérifiés. Claude Code doit lister ces items dans un message final et cocher chaque case.

### Fonctionnel

- [ ] `python -m rogier.main` démarre sans erreur si toutes les env vars requises sont présentes
- [ ] `python -m rogier.main` échoue avec un message français clair si une env var manque
- [ ] `python -m rogier.main` échoue si `ROGIER_SECRET_KEY` vaut `CHANGE_THIS_BEFORE_RUNNING_...`
- [ ] Login avec bon mot de passe → cookie de session + redirect `/`
- [ ] Login avec mauvais mot de passe → erreur affichée, pas de cookie
- [ ] Upload du fichier CSA HTML local → parsing → arbre affiché
- [ ] Import via URL Justel du CSA → fetch → parsing → arbre affiché
- [ ] L'arbre du CSA montre 5 parties, 18 livres, 111 titres, 147 chapitres, 227 sections, 127 sous-sections, 1278 articles
- [ ] Article 1:1 lisible dans l'interface, commence bien par « Une société est constituée »
- [ ] Article 7:2 lisible, contient « 61 500 euros »
- [ ] Article 18:8 ne commence pas par « 18:8. » (bug de forme B corrigé)
- [ ] TITRE 6/1, 6/2 et le TITRE 4 du Livre 3 ont leur vrai titre affiché (pas juste un `[`)
- [ ] Édition manuelle d'un article → nouvelle version créée → visible dans l'historique
- [ ] Rollback depuis l'historique → nouvelle version avec label « Restauration... » → contenu correct après refresh
- [ ] Export per_article du CSA → fichier .md téléchargé avec 1278 chunks
- [ ] Export hybrid → les articles > 2000 caractères sont découpés par paragraphes
- [ ] Invariant `must_contain: ["61 500"]` passe au vert sur le CSA
- [ ] Invariant `must_not_contain: ["Table des matières"]` passe au vert

### Qualité

- [ ] `pytest` : tous les tests passent, aucun warning non trivial
- [ ] `ruff check rogier/ tests/` : aucune erreur
- [ ] `ruff format --check rogier/ tests/` : aucun fichier à reformater
- [ ] Aucun secret dans `git log --all -p | grep -iE "(password|secret|key)\s*=\s*['\"][a-zA-Z0-9]{16,}"` (hors SPEC.md et .env.example qui contiennent des exemples fictifs explicites)
- [ ] Aucune valeur par défaut sensible dans le code (grep manuel)
- [ ] Aucun `print` en dehors de `scripts/`
- [ ] Aucun `except Exception: pass`
- [ ] Tous les fichiers Python ont des type hints sur les signatures publiques
- [ ] Tous les fichiers Python commencent par `from __future__ import annotations`

### Documentation

- [ ] `README.md` présent, complet, mentionne Charles Rogier
- [ ] `DEPLOYMENT.md` présent, permet un déploiement Ubuntu 24 avec nginx + systemd par un non-développeur
- [ ] `.env.example` présent, toutes les variables documentées
- [ ] `SPEC.md` présent à la racine (ce document)
- [ ] `CONTRIBUTING.md` présent
- [ ] `LICENSE` MIT présent
- [ ] `.gitignore` exhaustif (data/, .env, venv, pycache, etc.)

### Sécurité

- [ ] CSRF testé sur une route POST : requête sans token rejetée avec 403
- [ ] Cookie de session : `httponly`, `samesite=Lax`, `secure` en prod
- [ ] Tous les logs côté serveur ne contiennent pas le mot de passe en clair
- [ ] Test de l'upload : fichier non-HTML rejeté avec message clair
- [ ] Test de l'upload : fichier trop gros rejeté avec message clair

---

## 16. Instructions comportementales pour Claude Code

### 16.1 Décisions architecturales

**Ne jamais prendre une décision architecturale silencieuse.** Quand tu as le choix entre plusieurs approches techniques qui ne sont pas explicitement couvertes par ce document :

1. Présenter les options en français clair à l'utilisateur
2. Indiquer ta recommandation avec son justificatif
3. Attendre la réponse avant de coder

Cas typiques où demander :
- Format d'un identifiant interne non spécifié
- Choix d'une dépendance non listée
- Gestion d'un cas de bord non documenté
- Interprétation d'une exigence ambiguë

Cas où décider seul et mentionner en commit message :
- Nommage interne d'une fonction privée
- Découpage d'un fichier en sous-fichiers si > 500 lignes
- Choix de format d'un log
- Structure exacte d'un template Jinja

### 16.2 Commits

- Un commit par unité fonctionnelle cohérente
- Messages en français, format `<zone> : <action>`
- Zones : `init`, `stockage`, `fetching`, `extraction`, `parsing`, `ui`, `chunking`, `validation`, `tests`, `docs`, `security`, `config`, `fix`
- Action concise mais descriptive

Exemples :
- `init : squelette projet, auth, config`
- `extraction : parser HTML Justel avec fix titres tronqués`
- `fix : forme B du dernier article sans lien suivant`
- `docs : DEPLOYMENT.md avec nginx et systemd`

### 16.3 Messages de fin de phase

À la fin de chaque phase du §14, produire un message à l'utilisateur contenant :

1. **Ce qui est fait** : liste des items cochés
2. **Comment tester** : commande exacte à lancer, URL à visiter, résultat attendu
3. **Ce qui reste** : les prochaines phases
4. **Blocages ou questions** : s'il y en a

Ce message est la base pour que l'utilisateur (non-développeur) puisse vérifier l'avancement.

### 16.4 Gestion des erreurs utilisateur

Quand une erreur survient dans le parcours utilisateur :

1. La logguer côté serveur avec tous les détails techniques (trace, contexte)
2. Générer un ID de corrélation court (8 caractères)
3. Afficher à l'utilisateur : un message en français neutre + l'ID de corrélation pour le support
4. Ne jamais afficher de trace Python, de requête SQL, de chemin de fichier absolu, ou d'ID interne non transformé

### 16.5 Quand s'arrêter et demander

Claude Code doit s'arrêter et poser une question quand :

- Une consigne du SPEC semble contradictoire avec une autre
- Une consigne semble dangereuse pour la sécurité ou la qualité
- Une consigne est techniquement impossible avec la stack imposée
- Un test d'acceptation ne peut pas être vérifié parce que des informations manquent
- Le travail d'une phase prend plus de 50% de temps supplémentaire par rapport à l'estimation

### 16.6 Ce qu'il ne faut jamais faire sans demander

- Ajouter une dépendance qui n'est pas dans `pyproject.toml` initial
- Modifier le modèle de données (dataclasses) après Phase 1
- Changer le schéma JSON stocké sans incrémenter `schema_version` et écrire une migration
- Introduire un framework frontend
- Exposer une route publique non listée dans §9.2
- Stocker ou logger un secret en clair

### 16.7 Reprises de session

Ce projet sera développé sur plusieurs sessions. À chaque reprise :

1. Relire `SPEC.md` pour se recaler
2. Consulter le dernier commit et le message de fin de phase correspondant
3. Vérifier quels items sont cochés dans §15
4. Proposer la prochaine action à l'utilisateur avant de commencer

---

## Annexe A — Référence rapide des patterns Justel

Résumé condensé des découvertes de l'inspection du HTML CSA pour référence rapide pendant l'implémentation.

### Zones du HTML

| Zone | Marqueur de début | Marqueur de fin |
|---|---|---|
| 1. Entête | Début du fichier | `<div id="list-title-2">` |
| 2. TOC | `<div id="list-title-2">` | Premier `<a name="LNK0001"` hors TOC |
| 3. Corps | Premier `<a name="LNK0001"` hors TOC | Chaîne `"Articles modifiés"` |
| 4. Modifs | `"Articles modifiés"` | Fin du fichier |

### Distinction ancres TOC / corps

- **TOC** : `<a name="LNKR\d+">` (avec `R`)
- **Corps** : `<a name="LNK\d+">` (sans `R`)
- **Articles** (corps uniquement) : `<a name="Art\.[^"]+">`

### Niveaux hiérarchiques (ordre de profondeur)

```
PARTIE (0) → LIVRE (1) → TITRE (2) → CHAPITRE (3) → Section (4) → Sous-section (5) → [ARTICLE]
```

Seul ARTICLE est obligatoire. Les autres niveaux sont optionnels et dépendent du document.

### Chiffres de référence pour le CSA

- 5 parties, 18 livres, 111 titres, 147 chapitres, 227 sections, 127 sous-sections
- 1 278 articles
- Taille HTML : 2,9 MB
- Longueur article min : 49 chars (Art. 7:2)
- Longueur article max : 12 804 chars (Art. 3:6)
- Médiane : 663 chars

### Cas de bord connus

1. **3 titres dans modifications** : TITRE 6/1, 6/2 du Livre 1 et TITRE 4 du Livre 3 ont leur titre dans un marqueur `[1 ... ]1`. Fix : lecture secondaire dans le marqueur.
2. **Dernière forme d'article** : Art. 18:8 n'a pas de lien « suivant » donc le format d'intro est différent. Fix : `find_article_content_start` gère les deux formes.
3. **Encoding** : Justel sert en `windows-1252`, jamais utiliser `response.text`.

---

## Annexe B — Glossaire

- **Akoma Ntoso (AKN)** : standard XML OASIS pour les documents législatifs. Non implémenté en v0.1, prévu pour v0.2+.
- **Breadcrumb** : chaîne hiérarchique construite depuis la racine jusqu'à un nœud, du type `CSA > Livre 1 > Titre 1 > Art. 1:1`.
- **Chunk** : fragment de texte prêt à être ingéré par un système RAG. En v0.1, un chunk = un article entier ou un paragraphe d'article long.
- **Consolidé** : un texte légal dans sa version à jour, intégrant toutes les modifications successives. Justel publie la version consolidée du CSA.
- **ELI** : European Legislation Identifier, format URI canonique pour référencer un texte législatif. Justel utilise ELI dans certaines de ses URLs.
- **Justel** : base de données officielle de législation consolidée belge, hébergée sur ejustice.just.fgov.be par le SPF Justice.
- **Moniteur belge** : le journal officiel belge où sont publiés les textes législatifs. Source ultime.
- **RAG** : Retrieval-Augmented Generation, technique d'IA consistant à augmenter un LLM avec une recherche dans un corpus. Le chunker Rogier prépare le corpus pour ce type d'usage.
- **Schema version** : entier incrémenté à chaque évolution du modèle de données. Permet la migration automatique des anciens fichiers.

---

**Fin du document SPEC_ROGIER_v0.1.md**
