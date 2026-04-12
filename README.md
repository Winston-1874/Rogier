# Rogier

Rogier est un outil de chunking de textes legislatifs belges publies sur [Justel](https://www.ejustice.just.fgov.be/). Il prend en entree un texte legislatif au format HTML Justel, le parse en arbre hierarchique, permet l'edition manuelle et la validation, et produit des chunks Markdown prets a etre ingeres dans un systeme RAG (Retrieval-Augmented Generation).

Le projet est nomme d'apres **Charles Rogier** (1800-1885), membre du gouvernement provisoire belge de 1830, redacteur de dispositions de la Constitution belge et signataire de l'acte d'independance.

<!-- screenshot: page de connexion -->

## Fonctionnalites (v0.1)

- **Import** d'un texte legislatif depuis un fichier HTML Justel ou une URL directe
- **Parsing** en arbre hierarchique : Partie, Livre, Titre, Chapitre, Section, Sous-section, Article
- **Navigation** dans l'arbre avec fil d'Ariane, compteurs, navigation par type de noeud
- **Gestion des avertissements** de parsing avec possibilite de les ignorer/restaurer par type
- **Edition manuelle** des articles et titres avec versioning automatique (overlay, pas mutation)
- **Historique des versions** avec restauration non destructive
- **Export Markdown** chunke : un chunk par article ou chunking hybride (decoupe par paragraphes)
- **Validation** par invariants structurels (8 regles) et semantiques (must_contain / must_not_contain)
- **Securite** : authentification par mot de passe, cookies de session signes, protection CSRF

<!-- screenshot: arbre du CSA avec panneau de contenu -->

## Installation rapide

```bash
# Cloner le depot
git clone <url-du-depot>
cd rogier

# Creer un environnement virtuel
python3 -m venv .venv
source .venv/bin/activate

# Installer les dependances
pip install -e ".[dev]"

# Configurer les variables d'environnement
cp .env.example .env
# Editer .env et remplir les valeurs (voir les commentaires dans le fichier)

# Generer le hash du mot de passe administrateur
python scripts/create_admin_password_hash.py

# Lancer en mode developpement
bash scripts/run_dev.sh
```

L'application est accessible a `http://127.0.0.1:8000`.

## Configuration

Toutes les variables d'environnement sont documentees dans `.env.example`.

Variables obligatoires :

| Variable | Description |
|---|---|
| `ROGIER_SECRET_KEY` | Cle secrete pour les cookies de session (generer avec `openssl rand -hex 32`) |
| `ROGIER_ADMIN_PASSWORD_HASH` | Hash bcrypt du mot de passe admin (generer avec `python scripts/create_admin_password_hash.py`) |
| `ROGIER_DATA_DIR` | Repertoire de stockage des donnees |

Variables optionnelles : `ROGIER_MAX_UPLOAD_MB`, `ROGIER_CONTACT_URL`, `ROGIER_CONTACT_EMAIL`, `ROGIER_SESSION_MAX_AGE_DAYS`, `ROGIER_LOG_LEVEL`.

## Parcours utilisateur

1. **Connexion** : mot de passe unique administrateur
2. **Dashboard** : liste des documents importes
3. **Upload** : fichier HTML local ou URL Justel
4. **Arbre** : navigation hierarchique, lecture des articles, gestion des avertissements
5. **Edition** : modification inline des articles et titres, creation automatique de versions
6. **Export** : choix de la strategie de chunking, validation par invariants, telechargement du fichier `.md`

<!-- screenshot: page d'export avec validation -->

## Tests

```bash
# Tests rapides (< 10s)
pytest -m "not slow"

# Tests complets (incluant le parsing CSA et le parcours e2e)
pytest

# Lint
ruff check rogier/ tests/
ruff format --check rogier/ tests/
```

## Architecture

```
rogier/
  main.py              Point d'entree FastAPI
  auth.py              Authentification bcrypt + cookies signes
  csrf.py              Protection CSRF synchronizer token
  config_app.py        Lecture et validation des variables d'environnement
  overlay.py           Helper partage overlay manual_edits
  routes/              Routes HTTP (auth, dashboard, upload, document, version, export)
  fetching/            Client Justel avec cache et rate limiting
  extraction/          Parser HTML Justel
  parsing/             Dataclasses de l'arbre hierarchique
  storage/             Persistance JSON versionnee avec locks atomiques
  chunking/            Strategies de chunking et export Markdown
  validation/          Invariants structurels et semantiques
  templates/           Templates Jinja2
  static/              CSS et JavaScript
```

## Deploiement

Pour deployer sur un serveur Ubuntu 24 avec nginx et systemd, suivre le guide [DEPLOYMENT.md](DEPLOYMENT.md).

## Contribuer

Voir [CONTRIBUTING.md](CONTRIBUTING.md) pour les conventions de code, de commit et le processus de contribution.

## Licence

Ce projet est distribue sous licence MIT. Voir le fichier [LICENSE](LICENSE).

Copyright (c) 2026 Renaud Brion.
