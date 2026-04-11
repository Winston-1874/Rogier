"""Verrouillage et écriture atomique des fichiers JSON.

Chaque écriture passe par :
1. Un verrou exclusif (`fcntl.LOCK_EX`) sur un fichier de lock dédié
   (`<dir>/.<name>.lock`). Ce lock sérialise les écritures concurrentes
   qui ciblent le même fichier, même si Rogier est mono-utilisateur
   (un double clic rapide peut créer la course).
2. Un fichier temporaire unique créé via `tempfile.mkstemp`, qu'on
   flush + `os.fsync` pour garantir la persistance sur disque.
3. Un `rename` atomique final vers le chemin cible.

Le lockfile est laissé sur disque après écriture (il ne grossit pas ;
il est réutilisé à chaque appel). C'est la convention la plus simple
pour un lock POSIX persistant.

Note technique : le SPEC §8.2 mentionne `f.fdatasync()` qui n'existe
pas sur les objets fichier Python. On utilise `os.fsync` qui est
portable et plus conservateur.
"""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, TextIO


def _lock_path_for(path: Path) -> Path:
    return path.parent / f".{path.name}.lock"


@contextmanager
def locked_write(path: Path) -> Iterator[TextIO]:
    """Ouvrir un fichier pour écriture atomique sous lock exclusif.

    Usage::

        with locked_write(path) as f:
            f.write("...")

    Le contenu est écrit dans un fichier temporaire unique sous lock,
    puis renommé atomiquement sur le chemin cible à la sortie du bloc.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = _lock_path_for(path)

    lock_fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        tmp_fd, tmp_name = tempfile.mkstemp(
            prefix=f".{path.name}.",
            suffix=".tmp",
            dir=str(path.parent),
        )
        tmp_path = Path(tmp_name)
        f = os.fdopen(tmp_fd, "w", encoding="utf-8")
        try:
            yield f
            f.flush()
            os.fsync(f.fileno())
        finally:
            f.close()

        tmp_path.replace(path)
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def write_json(path: Path, data: dict[str, Any]) -> None:
    """Écrire un dict en JSON sous lock + rename atomique."""
    with locked_write(path) as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def read_json(path: Path) -> dict[str, Any]:
    """Lire un fichier JSON sous lock partagé.

    Lève FileNotFoundError si absent, json.JSONDecodeError si corrompu.
    Le lock partagé empêche une lecture pendant qu'une écriture est
    en cours sur le même descripteur.
    """
    with path.open("r", encoding="utf-8") as f:
        fcntl.flock(f.fileno(), fcntl.LOCK_SH)
        data: dict[str, Any] = json.load(f)
    return data
