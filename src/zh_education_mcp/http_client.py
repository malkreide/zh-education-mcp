"""HTTP-Client mit Egress-Guard, Connection-Pooling und Lifespan (SDK-001, SEC-004/021)."""

from __future__ import annotations

import asyncio
import ipaddress
import random
import socket
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import httpx

from . import __version__
from .constants import (
    HTTP_TIMEOUT,
    RETRY_AFTER_JITTER,
    RETRY_AFTER_STATUSES,
    RETRY_ATTEMPTS,
    RETRY_BACKOFF_BASE,
    RETRY_JITTER_SPREAD,
    RETRY_MAX_DELAY,
    RETRY_TOTAL_BUDGET,
)
from .logging_setup import log

# Wer fragt hier an? Ohne eigenen User-Agent geht der httpx-Default
# hinaus und der Betreiber der Datenquelle sieht bloss eine Bibliothek.
# Die Version stammt aus den Paket-Metadaten und kann nicht driften.
USER_AGENT = f"zh-education-mcp/{__version__} (+https://github.com/malkreide/zh-education-mcp)"
# Egress-Allow-List (SEC-004/SEC-021): nur diese Hosts dürfen kontaktiert werden,
# als unveränderliches frozenset im Code (nicht zur Laufzeit mutierbar).
ALLOWED_HOSTS: frozenset[str] = frozenset({"www.bista.zh.ch"})


def _ip_is_blocked(ip: str) -> bool:
    """True, wenn die IP nicht öffentlich routbar ist (private/loopback/
    link-local/metadata/reserved) — gegen SSRF auf interne Ziele (SEC-005)."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return True
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local  # deckt 169.254.169.254 (Cloud-Metadata) ab
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
    )


def _resolve_and_validate(host: str) -> list[str]:
    """Löst ``host`` auf und validiert ALLE resolved IPs gegen die Blocklist.

    Wird vor dem Request aufgerufen (DNS-Pinning-Kern gegen TOCTOU/DNS-Rebinding,
    SEC-005): Auflösung erfolgt einmal hier; eine aufgelöste interne IP führt zum
    harten Abbruch, bevor überhaupt verbunden wird. Gibt die geprüften IPs zurück.
    """
    try:
        infos = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
    except OSError as exc:
        raise PermissionError(f"DNS-Auflösung für {host} fehlgeschlagen: {exc}") from exc

    ips = sorted({info[4][0] for info in infos})
    blocked = [ip for ip in ips if _ip_is_blocked(ip)]
    if blocked:
        log.warning("egress_ip_blocked", host=host, blocked=blocked, resolved=ips)
        raise PermissionError(
            f"Egress blockiert: {host} löst auf interne/nicht-routbare IP(s) auf {blocked}"
        )
    return ips


async def _egress_guard(request: httpx.Request) -> None:
    """Prüft JEDEN ausgehenden Request (inkl. Redirect-Hops, SEC-004):

    1. HTTPS erzwingen, Host gegen Allow-List (SEC-004/021).
    2. Host auflösen und alle resolved IPs gegen die Blocklist prüfen
       (SEC-005): blockt DNS-Rebinding/Metadata-IPs vor dem Verbindungsaufbau.
    """
    if request.url.scheme != "https" or request.url.host not in ALLOWED_HOSTS:
        raise PermissionError(
            f"Egress blockiert: {request.url.scheme}://{request.url.host} "
            f"nicht in Allow-List {sorted(ALLOWED_HOSTS)}"
        )
    _resolve_and_validate(request.url.host)


def _new_client() -> httpx.AsyncClient:
    """Erzeugt einen HTTP-Client mit Egress-Guard und einheitlichem Timeout."""
    return httpx.AsyncClient(
        follow_redirects=True,
        timeout=HTTP_TIMEOUT,
        event_hooks={"request": [_egress_guard]},
        headers={"User-Agent": USER_AGENT},
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


def parse_retry_after(resp: httpx.Response | None) -> float | None:
    """Sekunden laut ``Retry-After`` der Antwort, oder ``None``.

    RFC 9110 §10.2.3 erlaubt zwei Formen: eine Sekundenzahl (``120``) und ein
    HTTP-Datum (``Wed, 21 Oct 2026 07:28:00 GMT``). Beide kommen vor, beide
    werden gelesen. Alles Unlesbare ergibt ``None``, und der Aufrufer fällt auf
    die eigene Kurve zurück — eine kaputte Kopfzeile darf auf dem Fehlerpfad
    nicht zum Absturz werden.
    """
    if resp is None or resp.status_code not in RETRY_AFTER_STATUSES:
        return None
    raw = (resp.headers.get("Retry-After") or "").strip()
    if not raw:
        return None
    if raw.isdigit():
        return float(raw)
    try:
        when = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if when is None:
        return None
    if when.tzinfo is None:  # RFC-9110-Daten sind GMT; naiv heisst UTC
        when = when.replace(tzinfo=UTC)
    # Nie negativ: ein Datum in der Vergangenheit heisst «jetzt».
    return max(0.0, (when - datetime.now(UTC)).total_seconds())


def retry_delay(attempt: int, last_error: Exception | None) -> float:
    """Sekunden Wartezeit vor ``attempt`` (ARCH-014).

    Die Antwort der Quelle schlägt unsere Schätzung: Hat sie auf einem 429 oder
    503 ein ``Retry-After`` gesendet, gewinnt dieser Wert über die
    Exponentialkurve. Alles wird gedeckelt und gestreut — die Begründung je
    Konstante steht in ``constants``.
    """
    hinted = parse_retry_after(getattr(last_error, "response", None))
    if hinted is not None:
        jittered = hinted * (1.0 + random.random() * RETRY_AFTER_JITTER)
    else:
        jittered = RETRY_BACKOFF_BASE**attempt * (
            1.0 - RETRY_JITTER_SPREAD + random.random() * 2 * RETRY_JITTER_SPREAD
        )
    # Deckel *nach* dem Jittern. Die andere Reihenfolge machte RETRY_MAX_DELAY
    # zu gar keiner Schranke: ein auf 20 s gedeckelter Wert wurde anschliessend
    # mit bis zu 1.5 multipliziert und landete bei 30 s.
    return min(jittered, RETRY_MAX_DELAY)


async def _http_get(url: str, params: dict | None = None) -> httpx.Response:
    """HTTP-GET über den gepoolten Client, mit Retry-Politik (ARCH-014).

    Wiederholt werden Netzwerkfehler, Timeouts, 5xx und 429. Ein 4xx ausser 429
    ist eine Aussage über die Anfrage und keine über den Moment — es wird sofort
    durchgereicht, damit ``_handle_error`` es abbilden kann. ``PermissionError``
    aus dem Egress-Guard ist eine Policy-Entscheidung und wird nie wiederholt.
    """
    client = _get_client()
    deadline = time.monotonic() + RETRY_TOTAL_BUDGET
    last_error: Exception | None = None
    for attempt in range(RETRY_ATTEMPTS):
        if attempt > 0:
            delay = retry_delay(attempt, last_error)
            # Eine Wartezeit, die das Budget überdauert, ist eine Wartezeit für
            # niemanden: Der Aufrufer hat aufgegeben, bevor sie endet.
            if delay >= deadline - time.monotonic():
                break
            log.info(
                "http_retry",
                attempt=attempt + 1,
                of=RETRY_ATTEMPTS,
                delay_s=round(delay, 2),
                error_type=type(last_error).__name__,
            )
            await asyncio.sleep(delay)
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            # httpx wendet sein Timeout pro Operation an (connect/read/write/
            # pool), und das Read-Timeout beginnt mit jedem Chunk von vorn — das
            # begrenzt jeden Schritt, nicht den Aufruf. Eine langsam tröpfelnde
            # Antwort könnte das Budget also überdauern, ohne dass ein einzelner
            # Read abliefe. ``asyncio.timeout`` ist die Wanduhr-Deadline, die
            # das Budget tatsächlich verspricht.
            async with asyncio.timeout(remaining):
                resp = await client.get(
                    url, params=params, timeout=min(HTTP_TIMEOUT, remaining)
                )
                resp.raise_for_status()
                return resp
        except TimeoutError as exc:  # Budget aufgebraucht, nicht bloss dieser Versuch
            last_error = exc
            break
        except (httpx.HTTPStatusError, httpx.RequestError) as exc:
            last_error = exc
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status is not None and 400 <= status < 500 and status != 429:
                raise
    if last_error is None:  # Budget weg, bevor ein einziger Request rausging
        raise httpx.ConnectError(
            f"Kein Versuch möglich: {RETRY_TOTAL_BUDGET:g}s Budget bereits aufgebraucht "
            f"(host={urlsplit(url).hostname})"
        )
    raise last_error
