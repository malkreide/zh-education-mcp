"""Retry-Politik gegenüber BISTA (ARCH-014).

Vier Fragen, die diese Datei beantwortet: Was wird wiederholt, wie schnell,
wie lange, und hält der Deckel, den die Konstante behauptet.
"""

from __future__ import annotations

import time

import httpx
import pytest
import respx

from zh_education_mcp import http_client as hc
from zh_education_mcp.constants import (
    BISTA_API,
    RETRY_ATTEMPTS,
    RETRY_MAX_DELAY,
    RETRY_TOTAL_BUDGET,
)

URL = f"{BISTA_API}/data_uebersicht_alle_lernende"


@pytest.fixture(autouse=True)
def _stub_dns(monkeypatch):
    """Egress-Guard hermetisch durchlassen (kein echtes DNS)."""
    import socket

    def fake_getaddrinfo(host, port, *a, **k):
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", port))]

    monkeypatch.setattr("zh_education_mcp.http_client.socket.getaddrinfo", fake_getaddrinfo)


def _resp(status: int, retry_after: str | None = None) -> httpx.Response:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    return httpx.Response(status, headers=headers)


def _status_error(status: int, retry_after: str | None = None) -> httpx.HTTPStatusError:
    return httpx.HTTPStatusError("boom", request=None, response=_resp(status, retry_after))


# --- Was wird wiederholt ----------------------------------------------------


@respx.mock
async def test_retries_a_503_and_then_succeeds():
    route = respx.get(URL).mock(side_effect=[httpx.Response(503), httpx.Response(200, text="ok")])
    resp = await hc._http_get(URL)
    assert resp.text == "ok"
    assert route.call_count == 2


@respx.mock
async def test_retries_a_connect_error():
    route = respx.get(URL).mock(
        side_effect=[httpx.ConnectError(""), httpx.Response(200, text="ok")]
    )
    resp = await hc._http_get(URL)
    assert resp.text == "ok"
    assert route.call_count == 2


@respx.mock
async def test_a_404_fails_fast_without_retry():
    """Ein 4xx ist eine Aussage über die Anfrage, nicht über den Moment."""
    route = respx.get(URL).mock(return_value=httpx.Response(404))
    with pytest.raises(httpx.HTTPStatusError):
        await hc._http_get(URL)
    assert route.call_count == 1


@respx.mock
async def test_a_429_is_retried_although_it_is_a_4xx():
    route = respx.get(URL).mock(side_effect=[httpx.Response(429), httpx.Response(200, text="ok")])
    await hc._http_get(URL)
    assert route.call_count == 2


@respx.mock
async def test_attempts_are_bounded():
    route = respx.get(URL).mock(return_value=httpx.Response(503))
    with pytest.raises(httpx.HTTPStatusError):
        await hc._http_get(URL)
    assert route.call_count == RETRY_ATTEMPTS


@respx.mock
async def test_an_egress_violation_is_never_retried(monkeypatch):
    """``PermissionError`` ist eine Policy-Entscheidung, kein Ausfall.

    Wiederholen hiesse, dieselbe verbotene Anfrage viermal zu stellen.
    """
    calls = {"n": 0}

    async def blocking_guard(request):
        calls["n"] += 1
        raise PermissionError("Egress blockiert")

    monkeypatch.setattr(hc, "_egress_guard", blocking_guard)
    monkeypatch.setattr(hc, "_client", None)  # Client mit neuem Hook bauen
    respx.get(URL).mock(return_value=httpx.Response(200))
    with pytest.raises(PermissionError):
        await hc._http_get(URL)
    assert calls["n"] == 1


# --- Wie schnell ------------------------------------------------------------


class TestRetryDelay:
    def test_retry_after_seconds_beats_the_curve(self):
        """Der Header liegt ausserhalb dessen, was die Kurve erreichen kann."""
        exc = _status_error(503, "13")
        # Kurve bei attempt=1: 2 * [0.5, 1.5] = [1, 3]. 13 liegt weit darüber.
        for _ in range(20):
            assert hc.retry_delay(1, exc) >= 13.0

    def test_retry_after_http_date_is_read(self):
        """RFC 9110 erlaubt beide Formen — ein Datum ist keine Ausnahme."""
        from datetime import UTC, datetime, timedelta
        from email.utils import format_datetime

        when = datetime.now(UTC) + timedelta(seconds=12)
        exc = _status_error(503, format_datetime(when, usegmt=True))
        assert 9.0 <= hc.retry_delay(1, exc) <= 16.0

    @pytest.mark.parametrize("bad", ["morgen", "", "-5", "12.5"])
    def test_an_unparseable_retry_after_falls_back_to_the_curve(self, bad):
        """Eine kaputte Kopfzeile darf auf dem Fehlerpfad kein Absturz sein."""
        exc = _status_error(503, bad)
        assert hc.retry_delay(1, exc) <= 3.0  # Kurvenwert, kein Header-Wert

    def test_retry_after_on_a_404_is_ignored(self):
        """Nur 429 und 503 tragen laut RFC 9110 ein sinnvolles Retry-After."""
        exc = _status_error(404, "600")
        assert hc.retry_delay(1, exc) <= 3.0

    def test_the_delay_is_spread(self):
        draws = {hc.retry_delay(1, None) for _ in range(30)}
        assert len(draws) > 1, "Wartezeit ist deterministisch — Jitter fehlt"
        assert all(1.0 <= d <= 3.0 for d in draws)

    def test_retry_after_jitter_never_goes_below_the_hinted_value(self):
        """Früher wiederzukommen wäre die Missachtung der gelesenen Angabe."""
        exc = _status_error(429, "5")
        for _ in range(30):
            assert hc.retry_delay(1, exc) >= 5.0

    def test_the_cap_is_a_real_bound_not_a_midpoint(self):
        """RETRY_MAX_DELAY muss halten, auch wenn der Jitter nach oben ausschlägt.

        Vor dem Jittern zu deckeln liess eine 20-s-Decke auf dem exponentiellen
        Pfad auf 30 s und auf dem ``Retry-After``-Pfad auf 25 s wachsen.
        Gefunden durch ein Codex-Review an ``parlament-mcp#35``.
        """
        exc = _status_error(429, "86400")
        for attempt in range(8):
            for _ in range(20):
                assert hc.retry_delay(attempt, None) <= RETRY_MAX_DELAY
                assert hc.retry_delay(attempt, exc) <= RETRY_MAX_DELAY

    def test_an_absurd_retry_after_lands_exactly_on_the_cap(self):
        exc = _status_error(503, "86400")
        assert hc.retry_delay(0, exc) == RETRY_MAX_DELAY


# --- Wie lange --------------------------------------------------------------


def test_the_budget_stays_under_the_mcp_client_default():
    """Der Anker ist gemessen, nicht geschätzt."""
    from mcp.shared._httpx_utils import MCP_DEFAULT_TIMEOUT

    assert RETRY_TOTAL_BUDGET < MCP_DEFAULT_TIMEOUT


@respx.mock
async def test_a_wait_that_outlasts_the_budget_is_not_taken(monkeypatch):
    """Eine Wartezeit, die das Budget überdauert, ist eine für niemanden."""
    route = respx.get(URL).mock(return_value=_resp(503, "3600"))
    monkeypatch.setattr(hc, "RETRY_MAX_DELAY", 3600.0)  # Deckel als Grund ausschliessen
    with pytest.raises(httpx.HTTPStatusError):
        await hc._http_get(URL)
    assert route.call_count == 1, "nach dem ersten 503 blieb keine Zeit mehr"


@respx.mock
async def test_a_slow_response_is_cut_by_the_wall_clock_deadline(monkeypatch, real_sleep):
    """Das Budget muss binden, auch wenn das httpx-Timeout nie feuert.

    httpx wendet sein Timeout pro Operation an und das Read-Timeout beginnt mit
    jedem Chunk von vorn — eine langsam tröpfelnde Antwort kann das Budget also
    überdauern, ohne dass ein einzelner Read abläuft.

    Bewusst mit der *echten* ``asyncio.sleep``: Eine Zusicherung über echte Zeit
    kann eine Uhr, die nur beim Schlafen vorrückt, nicht widerlegen — genau
    dieser blinde Fleck liess den Fehler in den Geschwister-Servern durch.
    """
    monkeypatch.setattr(hc, "RETRY_TOTAL_BUDGET", 0.05)

    async def _slow(request):
        await real_sleep(1.0)
        return httpx.Response(200, text="zu spät")

    respx.get(URL).mock(side_effect=_slow)
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        await hc._http_get(URL)
    elapsed = time.monotonic() - started
    assert elapsed < 0.5, f"Deadline hat nicht geschnitten: {elapsed:.2f}s"


async def test_an_exhausted_budget_reads_as_a_timeout_not_an_internal_error():
    """OBS-007: Das Gesamtbudget wirft den builtin ``TimeoutError``.

    Ohne den builtin-Zweig in ``_handle_error`` fiele ein aufgebrauchtes Budget
    in «unerwarteter interner Fehler» — eine Meldung, die dem Aufrufer nichts
    sagt und die Ursache verschweigt.
    """
    from zh_education_mcp.data import _handle_error

    assert "Zeitüberschreitung" in _handle_error(TimeoutError())
