"""Rate limiter par domaine pour les requêtes sortantes.

Maintient un timestamp de dernière requête par domaine et bloque si
nécessaire avant d'autoriser la requête suivante. Conforme au §6.2.1
du SPEC : au moins 5 secondes entre deux requêtes vers
`ejustice.just.fgov.be`.

L'instance partagée du module (`_default_limiter`) sérialise tous les
appels du processus, ce qui suffit pour Rogier mono-utilisateur. Une
instance dédiée peut être créée dans les tests pour isoler l'état.
"""

from __future__ import annotations

import asyncio
import time
from urllib.parse import urlparse

# Délai minimum (en secondes) entre deux requêtes vers le même domaine.
# Spécifique à Justel par contrat (§6.2.1) ; on l'applique uniformément
# à tous les domaines pour rester courtois par défaut.
MIN_DELAY_SECONDS = 5.0


class DomainRateLimiter:
    """Rate limiter à fenêtre minimale par domaine.

    Thread-safe via un `asyncio.Lock` partagé. L'attente est asynchrone
    (`asyncio.sleep`) pour ne pas bloquer la boucle d'événement.
    """

    def __init__(self, min_delay_seconds: float = MIN_DELAY_SECONDS) -> None:
        self.min_delay = min_delay_seconds
        self._last_request: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def wait_for(self, domain: str) -> float:
        """Bloquer si nécessaire avant d'autoriser une requête vers `domain`.

        Retourne le nombre de secondes effectivement attendues (0.0 si pas
        d'attente). Met à jour le timestamp à la sortie.
        """
        async with self._lock:
            now = time.monotonic()
            previous = self._last_request.get(domain)
            wait_seconds = 0.0
            if previous is not None:
                elapsed = now - previous
                if elapsed < self.min_delay:
                    wait_seconds = self.min_delay - elapsed

            if wait_seconds > 0:
                await asyncio.sleep(wait_seconds)

            self._last_request[domain] = time.monotonic()
            return wait_seconds

    def reset(self) -> None:
        """Vider l'état. Utilisé par les tests."""
        self._last_request.clear()


def domain_of(url: str) -> str:
    """Extraire le `netloc` (domaine) d'une URL pour servir de clé."""
    parsed = urlparse(url)
    return parsed.netloc.lower()


# Instance partagée du processus, utilisée par défaut par le fetcher.
_default_limiter = DomainRateLimiter()


def get_default_limiter() -> DomainRateLimiter:
    """Renvoyer le rate limiter par défaut du processus."""
    return _default_limiter
