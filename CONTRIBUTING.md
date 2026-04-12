# Contribuer a Rogier

Merci de votre interet pour Rogier ! Voici les conventions a respecter pour contribuer.

## Processus

1. Forker le depot
2. Creer une branche depuis `main` : `git checkout -b ma-feature`
3. Developper et tester
4. Soumettre une pull request

## Installation pour le developpement

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Conventions de code

- **Python 3.11+** requis
- Chaque fichier Python commence par `from __future__ import annotations`
- Type hints sur toutes les signatures publiques
- Lint : `ruff check rogier/ tests/` doit passer sans erreur
- Format : `ruff format rogier/ tests/` doit ne rien modifier
- Pas de `print()` dans le code applicatif (uniquement dans `scripts/`)
- Pas de `except Exception: pass`
- Messages d'erreur en francais

## Tests

```bash
# Tests rapides (< 10s)
pytest -m "not slow"

# Tests complets (incluant le parsing du CSA)
pytest

# Lint
ruff check rogier/ tests/
ruff format --check rogier/ tests/
```

Les tests lents sont marques `@pytest.mark.slow`. Les lancer avant chaque commit touchant au parsing ou au stockage.

## Commits

Format : `<zone> : <description en francais>`

Zones : `init`, `stockage`, `fetching`, `extraction`, `parsing`, `ui`, `chunking`, `validation`, `tests`, `docs`, `security`, `config`, `fix`.

Exemples :
- `extraction : parser HTML Justel avec fix titres tronques`
- `fix : forme B du dernier article sans lien suivant`
- `docs : DEPLOYMENT.md avec nginx et systemd`

## Securite

- Ne jamais commiter `.env` ou des secrets
- Ne jamais logger de mot de passe en clair
- Les erreurs affichees a l'utilisateur ne doivent contenir ni trace Python, ni chemin absolu, ni identifiant interne
- Chaque erreur affichee comporte un ID de correlation pour le support

## Architecture

Consulter `CLAUDE.md` pour la carte des modules et les conventions techniques. Consulter `SPEC.md` pour la specification detaillee.
