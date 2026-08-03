"""Gemeinsame Fixtures.

Der Zweck ist ein einziger: Die Retry-Schleife in ``http_client`` wartet
zwischen Versuchen, und eine Testsuite, die diese Wartezeiten absitzt, wird
langsam genug, dass sie niemand mehr laufen lässt. Ein Test, der ein 500
mockt, kostet sonst rund 14 Sekunden statt Millisekunden.
"""

from __future__ import annotations

import asyncio

import pytest

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
