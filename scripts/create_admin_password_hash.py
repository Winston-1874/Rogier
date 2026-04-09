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
