"""Client de fetch unique pour les pages Justel.

Ce module est la **seule** porte d'entrée pour récupérer du HTML depuis
`ejustice.just.fgov.be` (§6.1 du SPEC). Toute autre partie du code qui
voudrait faire une requête HTTP vers ce domaine doit passer par
`fetch_justel_url`.

Contraintes appliquées (§6.2) :
- Rate limit ≥ 5s entre requêtes vers Justel (via `rate_limiter`)
- User-Agent identifiable construit depuis ROGIER_CONTACT_URL/EMAIL
- Décodage explicite en `windows-1252` (jamais `response.text`)
- Cache local 24h (via `cache`)
- Timeout 30s, codes 4xx/5xx → `JustelFetchError` avec message français
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import httpx

from rogier.errors import JustelFetchError
from rogier.fetching import cache as fetch_cache
from rogier.fetching.rate_limiter import (
    DomainRateLimiter,
    domain_of,
    get_default_limiter,
)

logger = logging.getLogger(__name__)

JUSTEL_HOST = "www.ejustice.just.fgov.be"
REQUEST_TIMEOUT_SECONDS = 30.0
SOURCE_ENCODING = "windows-1252"

# Préfixes d'URL acceptés (§6.4)
_ALLOWED_PATH_PREFIXES = (
    "/cgi_loi/",
    "/eli/",
)


@dataclass(frozen=True)
class JustelFetchResult:
    """Résultat d'un fetch Justel — voir §6.3 du SPEC."""

    url: str
    html: str  # contenu décodé en windows-1252
    cache_hit: bool
    fetched_at: str  # ISO datetime
    content_hash: str  # sha256 du HTML décodé


def validate_justel_url(url: str) -> None:
    """Vérifier qu'une URL est bien une page Justel acceptée (§6.4).

    Lève `JustelFetchError` avec un message français en cas de rejet.
    """
    try:
        parsed = urlparse(url)
    except ValueError as e:
        raise JustelFetchError(
            "Cette URL n'est pas reconnue comme une page Justel valide. "
            "Rogier accepte uniquement les textes publiés sur ejustice.just.fgov.be."
        ) from e

    if parsed.scheme not in ("http", "https"):
        raise JustelFetchError(
            "Cette URL n'est pas reconnue comme une page Justel valide. "
            "Rogier accepte uniquement les textes publiés sur ejustice.just.fgov.be."
        )

    if parsed.netloc.lower() != JUSTEL_HOST:
        raise JustelFetchError(
            "Cette URL n'est pas reconnue comme une page Justel valide. "
            "Rogier accepte uniquement les textes publiés sur ejustice.just.fgov.be."
        )

    if not any(parsed.path.startswith(prefix) for prefix in _ALLOWED_PATH_PREFIXES):
        raise JustelFetchError(
            "Cette URL n'est pas reconnue comme une page Justel valide. "
            "Rogier accepte uniquement les textes publiés sur ejustice.just.fgov.be."
        )


def build_user_agent(contact_url: str, contact_email: str) -> str:
    """Construire le User-Agent identifiable (§6.2.2)."""
    return f"Rogier/0.1 (+{contact_url}; {contact_email})"


async def fetch_justel_url(
    url: str,
    *,
    data_dir: Path,
    contact_url: str,
    contact_email: str,
    force_refresh: bool = False,
    client: httpx.AsyncClient | None = None,
    limiter: DomainRateLimiter | None = None,
) -> JustelFetchResult:
    """Fetcher une page Justel avec cache et rate limiting.

    Paramètres :
        url : URL Justel à récupérer (validée avant tout réseau)
        data_dir : répertoire de données (pour le cache)
        contact_url, contact_email : identité du User-Agent
        force_refresh : ignorer le cache et toujours refetcher
        client : client httpx pré-existant (pour les tests, MockTransport)
        limiter : rate limiter spécifique (par défaut : instance partagée)

    Lève `JustelFetchError` avec un message français en cas d'échec.
    """
    validate_justel_url(url)

    if not force_refresh:
        cached = fetch_cache.get(data_dir, url)
        if cached is not None:
            logger.debug("Cache hit pour %s", url)
            return JustelFetchResult(
                url=cached.url,
                html=cached.html,
                cache_hit=True,
                fetched_at=cached.fetched_at,
                content_hash=cached.content_hash,
            )

    rate_limiter = limiter or get_default_limiter()
    await rate_limiter.wait_for(domain_of(url))

    user_agent = build_user_agent(contact_url, contact_email)
    headers = {"User-Agent": user_agent, "Accept": "text/html, */*;q=0.5"}

    owns_client = client is None
    if client is None:
        client = httpx.AsyncClient(timeout=REQUEST_TIMEOUT_SECONDS, headers=headers)

    try:
        try:
            response = await client.get(url, headers=headers)
        except httpx.TimeoutException as e:
            raise JustelFetchError(
                "Le serveur Justel n'a pas répondu dans les temps. "
                "Réessayez dans quelques minutes."
            ) from e
        except httpx.HTTPError as e:
            raise JustelFetchError(
                "Impossible de contacter le serveur Justel. "
                "Vérifiez votre connexion réseau et réessayez."
            ) from e

        if response.status_code >= 500:
            raise JustelFetchError(
                f"Le serveur Justel a renvoyé une erreur ({response.status_code}). "
                "Réessayez dans quelques minutes."
            )
        if response.status_code >= 400:
            raise JustelFetchError(
                f"La page demandée est introuvable sur Justel ({response.status_code}). "
                "Vérifiez l'URL et réessayez."
            )

        # Décodage explicite (§6.2.3) — jamais response.text.
        try:
            html = response.content.decode(SOURCE_ENCODING)
        except UnicodeDecodeError as e:
            raise JustelFetchError(
                "Le contenu reçu de Justel n'est pas dans l'encoding attendu. "
                "Cette page n'est probablement pas un texte légal Justel."
            ) from e

        etag = response.headers.get("ETag", "")
    finally:
        if owns_client:
            await client.aclose()

    entry = fetch_cache.put(data_dir, url, html, etag=etag)
    logger.info("Fetch Justel : %s (%d octets)", url, len(html))

    return JustelFetchResult(
        url=url,
        html=entry.html,
        cache_hit=False,
        fetched_at=entry.fetched_at,
        content_hash=entry.content_hash,
    )
