"""Cache local du fetcher Justel.

Stocke chaque réponse fetchée dans `data/fetch_cache/{sha256_url}.html`
avec un sidecar JSON `{sha256_url}.json` contenant les métadonnées
(ETag, fetched_at ISO, content_hash, url d'origine).

TTL : 24 heures (§6.2.4 du SPEC). Au-delà, l'entrée est considérée
expirée et `get` renvoie None — le fetcher déclenchera une nouvelle
requête.

Le HTML est stocké en UTF-8 côté disque, **après** décodage windows-1252
par le fetcher. Cela permet de relire le cache sans connaître l'encoding
d'origine et garantit que le contenu en mémoire est toujours du texte
Unicode propre.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from rogier.storage import paths
from rogier.storage.locks import read_json, write_json

logger = logging.getLogger(__name__)

# Durée de vie du cache (§6.2.4).
CACHE_TTL = timedelta(hours=24)


@dataclass(frozen=True)
class CachedEntry:
    """Entrée valide du cache fetcher."""

    url: str
    html: str
    etag: str
    fetched_at: str  # ISO 8601 UTC
    content_hash: str  # sha256 du HTML décodé


def url_key(url: str) -> str:
    """Calculer la clé de cache (sha256 hex de l'URL UTF-8)."""
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def _entry_paths(data_dir: Path, url: str) -> tuple[Path, Path]:
    """Renvoyer (chemin HTML, chemin sidecar JSON) pour une URL donnée."""
    base = paths.fetch_cache_dir(data_dir) / url_key(url)
    return base.with_suffix(".html"), base.with_suffix(".json")


def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _now_iso() -> str:
    return _now_utc().strftime("%Y-%m-%dT%H:%M:%SZ")


def get(data_dir: Path, url: str, *, now: datetime | None = None) -> CachedEntry | None:
    """Lire une entrée du cache si elle existe ET n'est pas expirée.

    Renvoie None si :
    - l'entrée n'existe pas
    - le sidecar JSON est manquant ou corrompu
    - l'entrée est plus vieille que CACHE_TTL

    Le paramètre `now` est exposé pour permettre aux tests d'injecter
    une heure simulée sans monkey-patcher le module.
    """
    html_path, sidecar_path = _entry_paths(data_dir, url)
    if not html_path.exists() or not sidecar_path.exists():
        return None

    try:
        meta = read_json(sidecar_path)
    except ValueError:
        logger.warning("Sidecar de cache corrompu, ignoré : %s", sidecar_path)
        return None

    fetched_at_str = meta.get("fetched_at", "")
    fetched_at = _parse_iso(fetched_at_str)
    if fetched_at is None:
        logger.warning("Date de fetch illisible dans %s, entrée ignorée", sidecar_path)
        return None

    current = now or _now_utc()
    if current - fetched_at > CACHE_TTL:
        return None

    try:
        html = html_path.read_text(encoding="utf-8")
    except OSError as e:
        logger.warning("HTML de cache illisible (%s) : %s", html_path, e)
        return None

    return CachedEntry(
        url=meta.get("url", url),
        html=html,
        etag=meta.get("etag", ""),
        fetched_at=fetched_at_str,
        content_hash=meta.get("content_hash", ""),
    )


def put(
    data_dir: Path,
    url: str,
    html: str,
    etag: str = "",
) -> CachedEntry:
    """Écrire une entrée dans le cache. Écrase l'entrée précédente si elle existe.

    Le `content_hash` est calculé sur le HTML décodé (UTF-8) — c'est la
    clé qui sera ensuite utilisée par `storage.documents` pour stocker
    le Document. Cette dualité est délibérée : le cache est indexé par
    URL pour la rapidité, le storage par contenu pour la déduplication.
    """
    paths.fetch_cache_dir(data_dir).mkdir(parents=True, exist_ok=True)
    html_path, sidecar_path = _entry_paths(data_dir, url)

    fetched_at = _now_iso()
    content_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()

    # Écrire d'abord le HTML (le plus gros), puis le sidecar.
    # En cas d'interruption entre les deux, `get` détectera le sidecar
    # manquant et renverra None — pas de corruption silencieuse.
    html_path.write_text(html, encoding="utf-8")
    write_json(
        sidecar_path,
        {
            "url": url,
            "etag": etag,
            "fetched_at": fetched_at,
            "content_hash": content_hash,
        },
    )

    return CachedEntry(
        url=url,
        html=html,
        etag=etag,
        fetched_at=fetched_at,
        content_hash=content_hash,
    )


def clear(data_dir: Path) -> int:
    """Vider entièrement le cache. Renvoie le nombre d'entrées supprimées.

    Une « entrée » = une paire HTML + sidecar JSON. Les lockfiles laissés
    par `locks.locked_write` (préfixés par un point) sont supprimés mais
    pas comptés.
    """
    cache_dir = paths.fetch_cache_dir(data_dir)
    if not cache_dir.exists():
        return 0
    entries = 0
    for f in cache_dir.iterdir():
        if not f.is_file():
            continue
        if f.suffix == ".html":
            entries += 1
        f.unlink()
    return entries
