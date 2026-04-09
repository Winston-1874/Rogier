#!/usr/bin/env bash
# Démarrage de Rogier en mode développement.
#
# Usage :
#   bash scripts/run_dev.sh
#
# Prérequis :
#   - Un fichier .env correctement rempli à la racine du projet
#   - Les dépendances installées : pip install -e ".[dev]"

set -euo pipefail

cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
    echo "Erreur : fichier .env introuvable." >&2
    echo "Copiez .env.example vers .env et remplissez les valeurs." >&2
    exit 1
fi

export ROGIER_DEV_MODE=1

python -m rogier.main
