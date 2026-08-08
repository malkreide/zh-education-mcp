"""Gemeinsame Fixtures.

Der Zweck ist ein einziger: Die Retry-Schleife in ``http_client`` wartet
zwischen Versuchen, und eine Testsuite, die diese Wartezeiten absitzt, wird
langsam genug, dass sie niemand mehr laufen lässt. Ein Test, der ein 500
mockt, kostet sonst rund 14 Sekunden statt Millisekunden.
"""

from __future__ import annotations

import asyncio

import pytest
from _resolver_guard import resolver_is_stubbed

from zh_education_mcp import http_client

# Gepatcht wird das Modul-Attribut ``http_client._sleep``, nicht
# ``asyncio.sleep``: Letzteres träfe jeden Import im Prozess und entschärfte
# still jeden Test, der ``asyncio.sleep(0)`` benutzt, um dem Event-Loop das Wort
# zu geben. In ``srgssr-mcp`` ist genau das passiert.
#
# Vor jeder Fixture festhalten. Wer die echte Wartezeit erst *innerhalb* eines
# Tests greift, greift die bereits gepatchte — genau so ist der Deadline-Test
# in ``termdat-mcp`` still durchgelaufen, obwohl er nichts geprüft hat.
_REAL_SLEEP = asyncio.sleep

# Dasselbe für den Namensauflöser, und aus einem teuer bezahlten Grund.
#
# Am 8.8.2026 scheiterte ``test_live_bista_api_letzi`` in fünf Läufen mit
#
#     certificate is not valid for 'www.bista.zh.ch'
#
# Das sah drei Runden lang wie ein Befund über die Quelle aus: erst wie ein
# falsches Zertifikat, dann wie ein flatternder Knoten, dann wie eine
# Reihenfolge-Abhängigkeit. Es war keins davon. ``tests/test_server.py`` trug
# eine ``autouse``-Fixture, die ``getaddrinfo`` auf ``8.8.8.8`` stubbt, damit
# die Unit-Tests hermetisch bleiben — und sie nahm Live-Tests nicht aus. Der
# einzige Live-Test jener Datei verband sich also nach ``8.8.8.8:443`` und
# sandte SNI ``www.bista.zh.ch``. Google antwortet mit einem Zertifikat für
# ``dns.google``, und fertig ist der «Zertifikatsfehler der Quelle».
#
# Verschärfend: ``http_client`` macht ``import socket``, also IST
# ``http_client.socket`` das Modulobjekt. Wer dessen ``getaddrinfo`` ersetzt,
# ersetzt es prozessweit — auch für anyio, über das httpx verbindet. Der Stub
# sieht lokal aus und ist global.
#
# Ein Live-Test gegen einen gestubbten Auflöser prüft nichts und behauptet
# alles. Deshalb steht hier ein Wächter und nicht nur eine Korrektur: Die
# Korrektur behebt den einen Fall, der Wächter den nächsten.
# Festgehalten wird er in `_resolver_guard.py` — siehe dort, warum eigene
# Datei und warum vor jeder Fixture.


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    """Bricht einen Live-Test ab, dessen Auflöser gestubbt ist.

    Als Hook und nicht als Fixture, weil die Reihenfolge zählt: Eine Fixture
    aus ``conftest.py`` wird **vor** den Fixtures des Testmoduls aufgebaut und
    **nach** ihnen abgebaut. Sie sähe den Stub in keinem der beiden Momente —
    beim Aufbau ist er noch nicht da, beim Abbau hat ``monkeypatch`` ihn schon
    zurückgenommen. ``pytest_runtest_call`` läuft dazwischen: nachdem alle
    Fixtures stehen, bevor der Testkörper beginnt. Das ist der einzige
    Moment, in dem die Frage überhaupt beantwortbar ist.
    """
    if "live" in item.keywords and resolver_is_stubbed():
        pytest.fail(
            "Dieser Live-Test läuft gegen einen gestubbten Namensauflöser und "
            "prüft damit nicht die echte Quelle, sondern irgendeine Adresse. "
            "Irgendeine `autouse`-Fixture patcht `getaddrinfo`, ohne Live-Tests "
            "auszunehmen — sie braucht `if 'live' in request.keywords: return`.",
            pytrace=False,
        )
    return (yield)


@pytest.fixture(autouse=True)
def _no_sleep(request, monkeypatch):
    """Retry-Wartezeiten überspringen — ausser in Live-Tests.

    Live-Tests sprechen mit der echten BISTA-API; dort ist die Wartezeit die
    Höflichkeit gegenüber der Quelle und genau das, was nicht wegfallen darf.
    """
    if "live" in request.keywords:
        return

    async def _instant(_seconds):
        return None

    monkeypatch.setattr(http_client, "_sleep", _instant)


@pytest.fixture
def real_sleep():
    """Die ungepatchte ``asyncio.sleep`` für Tests über echte Zeit."""
    return _REAL_SLEEP


async def _close_pooled_client() -> None:
    """Schliesst den gepoolten Client und gibt das Modul-Attribut frei."""
    client = http_client._client
    http_client._client = None
    if client is not None and not client.is_closed:
        await client.aclose()


@pytest.fixture(autouse=True)
async def _fresh_pooled_client(request):
    """Live-Tests bekommen einen eigenen Client — vorher und nachher.

    Der gepoolte Client (SDK-001) ist ein Modul-Global, seine offenen
    Verbindungen gehören aber dem Event-Loop, in dem sie entstanden sind.
    pytest-asyncio gibt jedem Test einen frischen Loop; der zweite Live-Test
    erbte damit einen Client, dessen Verbindungen an einem geschlossenen Loop
    hängen, und scheiterte mit «Event loop is closed» — an einem Fehler des
    Testaufbaus, der wie ein Ausfall der Quelle aussieht.

    Unit-Tests merken davon nichts, weil respx die Transport-Schicht ersetzt
    und gar keine Verbindung aufgebaut wird. Deshalb blieb das latent, bis ein
    zweiter Live-Test dazukam.
    """
    live = "live" in request.keywords
    if live:
        await _close_pooled_client()
    yield
    if live:
        await _close_pooled_client()
