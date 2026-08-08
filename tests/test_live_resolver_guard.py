"""Der Wächter, der verhindert, dass ein Live-Test gegen einen Stub läuft.

Am 8.8.2026 hat eine `autouse`-Fixture in `test_server.py` `getaddrinfo` auf
`8.8.8.8` gestubbt, ohne Live-Tests auszunehmen. Der einzige Live-Test jener
Datei verband sich damit nach `8.8.8.8:443` mit SNI `www.bista.zh.ch` und
bekam ein Zertifikat für `dns.google`:

    certificate is not valid for 'www.bista.zh.ch'

Fünf Läufe lang sah das aus wie ein Befund über die Quelle. Es war unser
eigener Stub. Ein Live-Test, der gegen einen gestubbten Auflöser läuft,
prüft nichts und behauptet alles — dieselbe Form wie ein leeres
Suchergebnis, das wie eine Antwort aussieht, nur eine Ebene tiefer.

Diese Datei prüft den Wächter, nicht die Fixture. Die Fixture ist korrigiert;
korrigiert bleibt sie nur, wenn ein Rückfall auffällt — und zwar auch dann,
wenn er in einer ganz anderen Datei passiert.
"""

from __future__ import annotations

import socket
from types import SimpleNamespace

import pytest

from tests.conftest import pytest_runtest_call, resolver_is_stubbed


def _run_guard(keywords: dict[str, bool]) -> None:
    """Führt den Hook bis zu seinem `yield` aus — dort sitzt die Prüfung.

    Der Hook ist ein Wrapper: Alles vor dem `yield` läuft, nachdem die
    Fixtures stehen und bevor der Testkörper beginnt. Genau dieses Stück wird
    hier ausgeführt, ohne eine ganze pytest-Sitzung dafür zu starten.
    """
    generator = pytest_runtest_call(SimpleNamespace(keywords=keywords))
    next(generator)


def test_the_guard_fires_for_a_live_test_with_a_stubbed_resolver(monkeypatch):
    """Der Fall vom 8.8.2026, nachgestellt."""
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [])

    with pytest.raises(pytest.fail.Exception) as excinfo:
        _run_guard({"live": True})

    message = str(excinfo.value)
    assert "gestubbten Namensauflöser" in message
    # Ohne den Hinweis auf die Behebung ist die Meldung eine Sackgasse: Wer
    # sie liest, sucht sonst zuerst bei der Quelle — so wie wir drei Runden lang.
    assert "request.keywords" in message


def test_the_guard_stays_out_of_the_way_of_unit_tests(monkeypatch):
    """Die Umkehrprobe. Ein Wächter, der Unit-Tests fällt, wird abgeschaltet.

    Der Stub ist für sie richtig und ausdrücklich erwünscht: Sie sollen kein
    echtes DNS befragen.
    """
    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [])

    _run_guard({})  # keine `live`-Marke — muss wortlos durchgehen


def test_the_guard_stays_out_of_the_way_of_an_honest_live_test():
    """Und ein Live-Test mit echtem Auflöser läuft ungehindert.

    Ohne diesen Test wäre ein Wächter, der **jeden** Live-Test fällt, von
    einem funktionierenden nicht zu unterscheiden — und die wöchentliche
    Live-Suite wäre dauerhaft rot, ohne dass es an der Quelle läge.
    """
    assert not resolver_is_stubbed(), "Vorbedingung: hier ist nichts gestubbt"

    _run_guard({"live": True})


def test_the_real_resolver_is_captured_before_anything_can_patch_it():
    """`_REAL_GETADDRINFO` muss die echte Funktion sein, nicht schon ein Stub.

    Wird sie erst innerhalb eines Tests festgehalten, hält sie die bereits
    gepatchte — und der Wächter vergleicht einen Stub mit sich selbst und
    schweigt für immer. Genau diese Falle steht im Kopf von `conftest.py` für
    `asyncio.sleep` beschrieben; sie gilt hier genauso.
    """
    from tests import conftest

    assert conftest._REAL_GETADDRINFO is socket.getaddrinfo
