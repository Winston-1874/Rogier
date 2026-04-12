#!/usr/bin/env bash
# Audit des secrets dans le depot Git et le working tree.
#
# Usage :
#   bash scripts/audit_secrets.sh
#
# Verifie :
# 1. Pas de secrets dans l'historique Git (hors SPEC.md et .env.example)
# 2. Pas de valeurs par defaut sensibles dans le code Python
# 3. Pas de fichiers .env commites

set -euo pipefail

cd "$(dirname "$0")/.."

EXIT_CODE=0

echo "=== Audit des secrets Rogier ==="
echo

# 1. Secrets dans l'historique Git
echo "--- 1. Recherche de secrets dans l'historique Git ---"
HITS=$(git log --all -p -- ':!SPEC.md' ':!.env.example' 2>/dev/null \
    | grep -iE '(password|secret|key)\s*=\s*['\''"][a-zA-Z0-9]{16,}' \
    || true)

if [ -n "$HITS" ]; then
    echo "ECHEC : patterns de secrets trouves dans l'historique :"
    echo "$HITS"
    EXIT_CODE=1
else
    echo "OK : aucun secret detecte dans l'historique Git."
fi
echo

# 2. Valeurs par defaut sensibles dans le code Python
echo "--- 2. Recherche de valeurs par defaut sensibles dans le code ---"
DEFAULTS=$(grep -rn --include="*.py" -iE \
    '(secret_key|password|api_key)\s*=\s*['\''"][a-zA-Z0-9]{8,}' \
    rogier/ \
    | grep -v '_PLACEHOLDER_SECRET' \
    | grep -v '\.pyc' \
    | grep -v 'test' \
    || true)

if [ -n "$DEFAULTS" ]; then
    echo "ECHEC : valeurs par defaut suspectes dans le code :"
    echo "$DEFAULTS"
    EXIT_CODE=1
else
    echo "OK : aucune valeur par defaut sensible dans le code."
fi
echo

# 3. Fichiers .env dans Git
echo "--- 3. Verification que .env n'est pas commite ---"
ENV_FILES=$(git ls-files '*.env' '.env' '.env.local' 2>/dev/null || true)

if [ -n "$ENV_FILES" ]; then
    echo "ECHEC : fichiers .env trouves dans Git :"
    echo "$ENV_FILES"
    EXIT_CODE=1
else
    echo "OK : aucun fichier .env dans Git."
fi
echo

# 4. print() en dehors de scripts/
echo "--- 4. Recherche de print() hors scripts/ ---"
PRINTS=$(grep -rn --include="*.py" '\bprint(' rogier/ || true)

if [ -n "$PRINTS" ]; then
    echo "ECHEC : print() trouve dans le code applicatif :"
    echo "$PRINTS"
    EXIT_CODE=1
else
    echo "OK : aucun print() dans le code applicatif."
fi
echo

# Resume
if [ $EXIT_CODE -eq 0 ]; then
    echo "=== AUDIT OK : aucun probleme detecte ==="
else
    echo "=== AUDIT ECHEC : des problemes ont ete trouves ==="
fi

exit $EXIT_CODE
