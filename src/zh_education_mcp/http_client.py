"""HTTP-Client mit Egress-Guard, Connection-Pooling und Lifespan (SDK-001, SEC-004/021)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx

from .constants import HTTP_TIMEOUT

# Egress-Allow-List (SEC-004/SEC-021): nur diese Hosts dürfen kontaktiert werden,
# als unveränderliches frozenset im Code (nicht zur Laufzeit mutierbar).
ALLOWED_HOSTS: frozenset[str] = frozenset({"www.bista.zh.ch"})


async def _egress_guard(request: httpx.Request) -> None:
    """Prüft JEDEN ausgehenden Request (inkl. Redirect-Hops) gegen die
    Allow-List und erzwingt HTTPS. Blockt Redirect-basierte SSRF, da der Hook
    auch bei umgeleiteten Requests feuert (SEC-004)."""
    if request.url.scheme != "https" or request.url.host not in ALLOWED_HOSTS:
        raise PermissionError(
            f"Egress blockiert: {request.url.scheme}://{request.url.host} "
            f"nicht in Allow-List {sorted(ALLOWED_HOSTS)}"
        )


def _new_client() -> httpx.AsyncClient:
    """Erzeugt einen HTTP-Client mit Egress-Guard und einheitlichem Timeout."""
    return httpx.AsyncClient(
        follow_redirects=True,
        timeout=HTTP_TIMEOUT,
        event_hooks={"request": [_egress_guard]},
    )


@dataclass
class AppContext:
    """Geteilte Ressourcen über die Server-Laufzeit (via lifespan injiziert)."""

    client: httpx.AsyncClient


# Lifespan-verwalteter, wiederverwendeter HTTP-Client (Connection-Pooling).
# Kein httpx.AsyncClient pro Tool-Call mehr (siehe Audit SDK-001).
_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Gibt den gepoolten HTTP-Client zurück.

    Im Server-Betrieb wird der Client einmalig im :func:`lifespan` erzeugt.
    Für direkte/Unit-Test-Aufrufe ausserhalb der Lifespan wird er lazy
    erzeugt — in beiden Fällen genau **ein** Client statt einer pro Request.
    """
    global _client
    if _client is None or _client.is_closed:
        _client = _new_client()
    return _client


@asynccontextmanager
async def lifespan(_server: object) -> AsyncIterator[AppContext]:
    """Erzeugt den geteilten HTTP-Client beim Start, schliesst ihn beim Stop."""
    global _client
    _client = _new_client()
    try:
        yield AppContext(client=_client)
    finally:
        await _client.aclose()
        _client = None


async def _http_get(url: str, params: dict | None = None) -> httpx.Response:
    """HTTP-GET über den gepoolten, lifespan-verwalteten Client."""
    client = _get_client()
    return await client.get(url, params=params, timeout=HTTP_TIMEOUT)
