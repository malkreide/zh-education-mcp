"""Retry-Politik gegenüber BISTA (ARCH-014).

Fünf Fragen, die diese Datei beantwortet: Was wird wiederholt, wie schnell,
wie lange, hält der Deckel, den die Konstante behauptet — und welche der
beiden Lagen hinter ``PermissionError`` liegt eigentlich vor.
"""

from __future__ import annotations

import socket
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

# Den echten Auflöser festhalten, bevor irgendeine Fixture ihn ersetzt — sonst
# griffe der Live-Test unten die bereits gepatchte Fassung und liefe still
# gegen 8.8.8.8 statt gegen echtes DNS. Dieselbe Falle wie bei ``_REAL_SLEEP``
# in ``conftest``, wo genau das in ``termdat-mcp`` einen Test entwertet hat.
_REAL_GETADDRINFO = socket.getaddrinfo


@pytest.fixture(autouse=True)
def _stub_dns(request, monkeypatch):
    """Egress-Guard hermetisch durchlassen (kein echtes DNS).

    Ausser in Live-Tests: Dort ist die echte Auflösung Teil dessen, was geprüft
    wird — ein «Live»-Test gegen einen gestubbten Auflöser prüfte das Gegenteil
    seines Namens. Dieselbe Ausnahme wie bei ``_no_sleep`` in ``conftest``.
    """
    if "live" in request.keywords:
        return

    def fake_getaddrinfo(host, port, *a, **k):
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", port))]

    monkeypatch.setattr("zh_education_mcp.http_client.socket.getaddrinfo", fake_getaddrinfo)


def _resp(status: int, retry_after: str | None = None) -> httpx.Response:
    headers = {"Retry-After": retry_after} if retry_after is not None else {}
    return httpx.Response(status, headers=headers)


def _status_error(status: int, retry_after: str | None = None) -> httpx.HTTPStatusError:
    return httpx.HTTPStatusError("boom", request=None, response=_resp(status, retry_after))


def _addrinfo(ip: str, port: int = 443) -> list:
    """Eine ``getaddrinfo``-Antwort, die auf ``ip`` zeigt."""
    return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port))]


def _patch_resolver(monkeypatch, fn) -> None:
    monkeypatch.setattr("zh_education_mcp.http_client.socket.getaddrinfo", fn)


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


# --- Politik oder Ausfall ---------------------------------------------------
#
# ``_resolve_and_validate`` scheitert auf zwei grundverschiedene Weisen. Bis
# beide denselben ``PermissionError`` warfen, wurde ein Auflöser-Ausfall wie
# ein Policy-Verstoss behandelt: nie wiederholt, und dem Aufrufer als
# «Egress-Policy blockiert» gemeldet. Am 3.8.2026 scheiterten drei
# Tool-Aufrufe hintereinander genau daran; der vierte ging durch.


def test_the_two_lagen_are_distinct_types_on_the_old_base():
    """Getrennte Typen, aber ``PermissionError`` bleibt die gemeinsame Basis.

    Die Basis ist kein Schmuck: Jedes bestehende ``except PermissionError``
    (und jeder Test, der darauf zeigt) sollte weiter greifen, statt still ins
    Leere zu laufen und den Fehler als «unerwarteter interner Fehler»
    durchzureichen.
    """
    assert issubclass(hc.EgressBlocked, PermissionError)
    assert issubclass(hc.UpstreamUnresolvable, PermissionError)
    # ... und trotzdem auseinanderhaltbar, in beide Richtungen.
    assert not issubclass(hc.UpstreamUnresolvable, hc.EgressBlocked)
    assert not issubclass(hc.EgressBlocked, hc.UpstreamUnresolvable)


def test_a_resolver_outage_is_typed_as_unresolvable(monkeypatch):
    """Der Auflöser antwortet nicht — das ist keine Aussage über die Politik."""

    def failing(host, port, *a, **k):
        raise socket.gaierror(socket.EAI_AGAIN, "Temporary failure in name resolution")

    _patch_resolver(monkeypatch, failing)
    with pytest.raises(hc.UpstreamUnresolvable):
        hc._resolve_and_validate("www.bista.zh.ch")


def test_an_internal_answer_is_typed_as_egress_blocked(monkeypatch):
    """Der Auflöser antwortet, und die Antwort ist verboten (SEC-005)."""
    _patch_resolver(monkeypatch, lambda *a, **k: _addrinfo("169.254.169.254"))
    with pytest.raises(hc.EgressBlocked):
        hc._resolve_and_validate("www.bista.zh.ch")


@respx.mock
async def test_a_dns_outage_is_retried_and_then_succeeds(monkeypatch):
    """Ein Zucken des Auflösers darf den Tool-Aufruf nicht beenden.

    Derselbe transiente Ausfall wie ein ``ConnectError``, nur einen Schritt
    früher — und genau der Fall, für den die Schleife gebaut ist.
    """
    calls = {"n": 0}

    def flaky(host, port, *a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise socket.gaierror(socket.EAI_AGAIN, "Temporary failure in name resolution")
        return _addrinfo("8.8.8.8", port)

    _patch_resolver(monkeypatch, flaky)
    route = respx.get(URL).mock(return_value=httpx.Response(200, text="ok"))
    resp = await hc._http_get(URL)
    assert resp.text == "ok"
    assert calls["n"] == 2, "der zweite Versuch hat gar nicht erst aufgelöst"
    assert route.call_count == 1


@respx.mock
async def test_a_dead_resolver_stays_under_the_shared_attempt_cap(monkeypatch):
    """Wiederholt wird unter demselben Budget wie alles andere, nicht daneben.

    Ein eigener Zähler für DNS wäre eine zweite Obergrenze, die niemand
    zusammenrechnet: Vier Auflösungsversuche *plus* vier Requests ist nicht
    das, was ``RETRY_ATTEMPTS`` verspricht.
    """
    calls = {"n": 0}

    def always_failing(host, port, *a, **k):
        calls["n"] += 1
        raise socket.gaierror(socket.EAI_AGAIN, "Temporary failure in name resolution")

    _patch_resolver(monkeypatch, always_failing)
    route = respx.get(URL).mock(return_value=httpx.Response(200, text="nie erreicht"))
    with pytest.raises(hc.UpstreamUnresolvable):
        await hc._http_get(URL)
    assert calls["n"] == RETRY_ATTEMPTS
    assert route.call_count == 0, "eine unauflösbare Adresse darf nie kontaktiert werden"


@respx.mock
async def test_a_rebinding_answer_is_still_never_retried(monkeypatch):
    """Die Politik-Seite bleibt, was sie war — trotz gemeinsamer Basis.

    Der Nachbartest oben patcht den ganzen Guard; dieser geht durch den echten
    Pfad (Host löst auf eine Metadata-IP auf) und hält fest, dass die neue
    Klasse nicht versehentlich in den wiederholten Zweig gerutscht ist.
    """
    calls = {"n": 0}

    def internal(host, port, *a, **k):
        calls["n"] += 1
        return _addrinfo("169.254.169.254", port)

    _patch_resolver(monkeypatch, internal)
    route = respx.get(URL).mock(return_value=httpx.Response(200))
    with pytest.raises(hc.EgressBlocked):
        await hc._http_get(URL)
    assert calls["n"] == 1
    assert route.call_count == 0


@respx.mock
async def test_a_hanging_resolver_is_cut_by_the_wall_clock_deadline(monkeypatch):
    """«Unter demselben Budget» muss auch für den Auflöser gelten.

    ``getaddrinfo`` ist synchron. Liefe es im Event-Loop, könnte die Deadline
    es nicht schneiden — der Timer feuert erst, wenn der Loop wieder drankommt,
    und aus vier Versuchen würden vier Blockaden über das Budget hinaus.
    Deshalb löst der Guard im Thread-Pool auf; dieser Test misst echte Zeit,
    denn eine Uhr, die nur beim Schlafen vorrückt, kann eine Blockade nicht
    bemerken.
    """
    monkeypatch.setattr(hc, "RETRY_TOTAL_BUDGET", 0.05)

    def hanging(host, port, *a, **k):
        time.sleep(0.6)  # echt blockierend, wie ein toter Resolver
        return _addrinfo("8.8.8.8", port)

    _patch_resolver(monkeypatch, hanging)
    respx.get(URL).mock(return_value=httpx.Response(200, text="zu spät"))
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        await hc._http_get(URL)
    elapsed = time.monotonic() - started
    assert elapsed < 0.4, f"der Auflöser hat den Event-Loop blockiert: {elapsed:.2f}s"


# --- Wie liest der Aufrufer das ---------------------------------------------


def test_a_resolver_outage_does_not_read_as_an_egress_violation():
    """Eine falsche Diagnose schickt Nutzende dorthin, wo nichts zu finden ist.

    «Durch Egress-Policy blockiert» heisst: Sieh in der Konfiguration nach. Bei
    einem DNS-Aussetzer ist die Konfiguration in Ordnung und die richtige
    Handlung ist, es noch einmal zu versuchen.
    """
    from zh_education_mcp.data import _handle_error

    msg = _handle_error(
        hc.UpstreamUnresolvable(
            "DNS-Auflösung für www.bista.zh.ch fehlgeschlagen: "
            "[Errno -3] Temporary failure in name resolution"
        )
    )
    assert "Egress" not in msg
    assert "DNS" in msg
    assert "erneut versuchen" in msg
    # OBS-002: der originale Fehler geht ins Log, nicht an den Client.
    assert "Errno" not in msg and "www.bista.zh.ch" not in msg
    assert msg.startswith("Fehler:")


def test_an_egress_violation_still_names_the_policy():
    """Die Politik-Meldung bleibt unverändert — sie war für ihren Fall richtig."""
    from zh_education_mcp.data import _handle_error

    msg = _handle_error(
        hc.EgressBlocked(
            "Egress blockiert: www.bista.zh.ch löst auf interne/nicht-routbare "
            "IP(s) auf ['169.254.169.254']"
        )
    )
    assert "Egress-Policy" in msg
    assert "169.254" not in msg
    assert msg.startswith("Fehler:")


def test_a_bare_permissionerror_keeps_the_old_message():
    """Was vor der Trennung ``PermissionError`` warf, liest sich weiter gleich."""
    from zh_education_mcp.data import _handle_error

    assert "Egress-Policy" in _handle_error(PermissionError("Egress blockiert"))


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


async def test_the_no_sleep_fixture_leaves_the_global_asyncio_sleep_alone():
    """Die Fixture darf nur die Backoff-Wartezeit abschalten, nicht mehr.

    ``monkeypatch.setattr(http_client.asyncio, "sleep", ...)`` sähe lokal aus,
    trifft aber das *Modul* ``asyncio`` und damit jeden Import im Prozess. Ein
    Test, der ``asyncio.sleep(0)`` benutzt, um dem Event-Loop das Wort zu geben,
    prüft danach still nichts mehr — er läuft weiter und misst nichts. Genau so
    ist in ``srgssr-mcp`` eine Parallelitäts-Prüfung eingebrochen.

    Deshalb geht der Backoff über ``http_client._sleep``, und dieser Test hält
    fest, dass ``asyncio.sleep`` intakt bleibt.
    """
    import asyncio

    inflight = 0
    peak = 0

    async def _worker():
        nonlocal inflight, peak
        inflight += 1
        peak = max(peak, inflight)
        await asyncio.sleep(0)  # muss echt ans Event-Loop abgeben
        inflight -= 1

    await asyncio.gather(_worker(), _worker())
    assert peak == 2, "asyncio.sleep gibt nicht mehr ab — die Fixture greift zu weit"


# --- Gegen die echte Quelle -------------------------------------------------


@pytest.mark.live
async def test_live_a_dns_hiccup_costs_an_attempt_not_the_call(monkeypatch):
    """Der Beleg gegen BISTA selbst: Ein Auflöser-Zucken kostet einen Versuch.

    Die Unit-Tests oben mocken beide Seiten — Auflöser *und* Antwort. Sie
    zeigen damit, dass die Schleife tut, was sie soll, aber nicht, dass der
    Aufruf am Ende echte Daten bringt. Genau diese Lücke hat den Fehler
    ueberhaupt erst durchgelassen: Gemeldet hat ihn am 3.8.2026 ein Live-Lauf,
    nicht die Suite.

    Hier ist deshalb nur der *erste* Auflösungsversuch gefälscht. Alles danach
    ist echt: echtes DNS beim zweiten Versuch, echte TLS-Verbindung, echte
    BISTA-Antwort — und echte Backoff-Wartezeit, weil ``_no_sleep`` für
    Live-Tests absichtlich nicht greift.
    """
    calls = {"n": 0}

    def flaky(host, port, *a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise socket.gaierror(socket.EAI_AGAIN, "Temporary failure in name resolution")
        return _REAL_GETADDRINFO(host, port, *a, **k)

    monkeypatch.setattr("zh_education_mcp.http_client.socket.getaddrinfo", flaky)

    # Nicht die Gesamtdauer messen: Die enthält den Netzabruf und wäre auch
    # ohne jede Wartezeit lang genug, um eine Untergrenze zu bestehen. Gemessen
    # wird, was der Backoff wirklich abgesessen hat.
    waited: list[float] = []
    inner_sleep = hc._sleep

    async def recording_sleep(seconds):
        started = time.monotonic()
        await inner_sleep(seconds)
        waited.append(time.monotonic() - started)

    monkeypatch.setattr(hc, "_sleep", recording_sleep)

    resp = await hc._http_get(URL)

    assert calls["n"] == 2, "der zweite Versuch hat nicht neu aufgelöst"
    assert resp.status_code == 200
    # Kein Feldname wird hier gepinnt: BISTA hat die Schreibweise der Kopfzeile
    # schon gewechselt (siehe ``_normalise_keys``). Geprüft wird, dass eine
    # CSV-Kopfzeile mit Datenzeilen dahinter ankam — nicht welche.
    lines = resp.text.splitlines()
    assert "," in lines[0] and len(lines) > 1, "keine CSV-Antwort erhalten"
    # Die echte Wartezeit ist Teil der Zusage: Gegenüber der Quelle ist sie die
    # Höflichkeit, die ``_no_sleep`` für Live-Tests absichtlich stehen lässt.
    # Der Backoff liegt beim ersten Retry in [1s, 3s].
    assert len(waited) == 1, f"unerwartet viele Wartezeiten: {waited}"
    assert 1.0 <= waited[0] <= 4.0, f"Backoff nicht abgesessen: {waited[0]:.2f}s"


@pytest.mark.live
def test_live_the_real_host_resolves_past_the_egress_guard():
    """SEC-005 gegen die Wirklichkeit statt gegen einen Stub.

    Die Unit-Tests prüfen die Blocklist an erfundenen Antworten. Ob der echte
    BISTA-Host heute auf etwas auflöst, das der Guard durchlässt, sagt nur
    dieser Test — und er hält zugleich fest, dass die Stub-Fixture für
    Live-Tests wirklich aussetzt: Käme hier ``8.8.8.8`` heraus, liefe der
    «Live»-Test gegen den Stub.
    """
    host = "www.bista.zh.ch"
    real = sorted({i[4][0] for i in _REAL_GETADDRINFO(host, 443, proto=socket.IPPROTO_TCP)})
    assert hc._resolve_and_validate(host) == real
    assert all(not hc._ip_is_blocked(ip) for ip in real)
