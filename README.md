# Rogier

Rogier est un outil de chunking de textes legislatifs belges publies sur [Justel](https://www.ejustice.just.fgov.be/). Il prend en entree un texte legislatif au format HTML Justel, le parse en arbre hierarchique, et produit des chunks Markdown prets a etre ingeres dans un systeme RAG (Retrieval-Augmented Generation).

Le projet est nomme d'apres **Charles Rogier** (1800-1885), membre du gouvernement provisoire belge de 1830, redacteur de dispositions de la Constitution belge et signataire de l'acte d'independance.

## Fonctionnalites (v0.1)

- Import d'un texte legislatif depuis un fichier HTML Justel ou une URL directe
- Parsing en arbre hierarchique : Partie, Livre, Titre, Chapitre, Section, Sous-section, Article
- Affichage navigable de l'arbre dans une interface web
- Edition manuelle des noeuds avec versioning automatique
- Export en Markdown chunke (un chunk par article ou chunking hybride)
- Validation par invariants structurels et semantiques

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

## Licence

Ce projet est distribue sous licence MIT. Voir le fichier [LICENSE](LICENSE).
