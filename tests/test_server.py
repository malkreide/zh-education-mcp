"""Tests für zh-education-mcp (ohne Live-API-Aufrufe)."""

from __future__ import annotations

import httpx
import pytest
import respx
from fixture_data import csv_fixture, latest_year

# Aufgezeichnete Fixtures statt erfundener Werte. Herkunft, Datum und
# Auswahlregel je Datei stehen in tests/fixtures/PROVENANCE.md; neu aufzeichnen
# mit `python scripts/record_fixtures.py`.
#
# Die Kopfzeilen sind die der Quelle vom Aufzeichnungstag — uneinheitlich
# zwischen den Endpunkten und teils innerhalb einer Zeile. Genau daran ist der
# Server am 3.8.2026 gescheitert; eine vereinheitlichte Fixture haette das
# wieder unsichtbar gemacht.
SAMPLE_SEK1_CSV = csv_fixture("sek1")
SAMPLE_UEBERSICHT_CSV = csv_fixture("uebersicht")
SAMPLE_NAT_CSV = csv_fixture("nat_regional")

BISTA_BASE = "https://www.bista.zh.ch/basicapi/ogd"


@pytest.fixture(autouse=True)
def _clear_cache():
    """Cache vor jedem Test leeren."""
    from zh_education_mcp.server import _cache

    _cache.clear()
    yield
    _cache.clear()


@pytest.fixture(autouse=True)
def _stub_dns(monkeypatch):
    """getaddrinfo deterministisch auf eine öffentliche IP stubben, damit Unit-
    Tests hermetisch bleiben (kein echtes DNS) und der Egress-Guard durchlässt."""
    import socket

    def fake_getaddrinfo(host, port, *a, **k):
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", port))]

    monkeypatch.setattr("zh_education_mcp.http_client.socket.getaddrinfo", fake_getaddrinfo)


@pytest.mark.asyncio
async def test_anker_query_letzi_trend():
    """Anker-Query: Schulkreis Letzi 5-Jahres-Trend."""
    from zh_education_mcp.server import SchulkreisTrendInput, zh_edu_schulkreis_trend

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_lernende_sekundarstufe_i_anforderungstyp").mock(
            return_value=httpx.Response(200, text=SAMPLE_SEK1_CSV)
        )

        params = SchulkreisTrendInput(schulgemeinde="Zürich-Letzi", letzte_n_jahre=5)
        result = await zh_edu_schulkreis_trend(params)

    assert "Letzi" in result
    assert latest_year("sek1") in result
    assert "Sek A" in result or "930" in result
    assert "Trend" in result or "trend" in result.lower()


@pytest.mark.asyncio
async def test_overview_aktuellstes_jahr():
    """Kantonsweite Übersicht gibt aktuellstes Jahr zurück."""
    from zh_education_mcp.server import UebersichtInput, zh_edu_overview

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_uebersicht_alle_lernende").mock(
            return_value=httpx.Response(200, text=SAMPLE_UEBERSICHT_CSV)
        )

        params = UebersichtInput()
        result = await zh_edu_overview(params)

    assert latest_year("uebersicht") in result
    assert "Primarstufe" in result


@pytest.mark.asyncio
async def test_list_schulgemeinden_filter():
    """zh_edu_list_schulgemeinden filtert korrekt nach Suchbegriff."""
    from zh_education_mcp.server import ListSchulgemeindensInput, zh_edu_list_schulgemeinden

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_lernende_sekundarstufe_i_anforderungstyp").mock(
            return_value=httpx.Response(200, text=SAMPLE_SEK1_CSV)
        )

        params = ListSchulgemeindensInput(suchbegriff="Zürich")
        result = await zh_edu_list_schulgemeinden(params)

    assert "Zürich-Letzi" in result


@pytest.mark.asyncio
async def test_sek1_profil_letzi():
    """Sek I Profil für Zürich-Letzi zeigt Anforderungstypen."""
    from zh_education_mcp.server import Sek1ProfilInput, zh_edu_sek1_profil

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_lernende_sekundarstufe_i_anforderungstyp").mock(
            return_value=httpx.Response(200, text=SAMPLE_SEK1_CSV)
        )

        params = Sek1ProfilInput(schulgemeinde="Zürich-Letzi", jahr=2024)
        result = await zh_edu_sek1_profil(params)

    assert "Letzi" in result
    assert "Sek A" in result
    assert "2024" in result


@pytest.mark.asyncio
async def test_staatsangehoerigkeiten_top3():
    """Staatsangehörigkeiten gibt korrekte Top-N-Liste zurück."""
    from zh_education_mcp.server import StaatsangehoerigkeitInput, zh_edu_staatsangehoerigkeiten

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_lernende_regelschule_regional_staatsangehoerigkeit").mock(
            return_value=httpx.Response(200, text=SAMPLE_NAT_CSV)
        )

        params = StaatsangehoerigkeitInput(schulgemeinde="Zürich-Letzi", top_n=3)
        result = await zh_edu_staatsangehoerigkeiten(params)

    assert "Schweiz" in result
    assert "Deutschland" in result


@pytest.mark.asyncio
async def test_not_found_returns_helpful_message():
    """Unbekannte Schulgemeinde gibt hilfreiche Fehlermeldung zurück."""
    from zh_education_mcp.server import SchulkreisTrendInput, zh_edu_schulkreis_trend

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_lernende_sekundarstufe_i_anforderungstyp").mock(
            return_value=httpx.Response(200, text=SAMPLE_SEK1_CSV)
        )

        params = SchulkreisTrendInput(schulgemeinde="Nichtexistent-XYZ")
        result = await zh_edu_schulkreis_trend(params)

    assert "nicht gefunden" in result.lower() or "Nichtexistent" in result
    assert "zh_edu_list_schulgemeinden" in result


@pytest.mark.live
@pytest.mark.asyncio
async def test_live_bista_api_letzi():
    """Live-Test: BISTA-API gibt echte Daten für Letzi zurück."""
    from zh_education_mcp.server import SchulkreisTrendInput, zh_edu_schulkreis_trend

    params = SchulkreisTrendInput(schulgemeinde="Zürich-Letzi", letzte_n_jahre=3)
    result = await zh_edu_schulkreis_trend(params)

    assert "Letzi" in result
    assert "Sek A" in result or "Sek B" in result


# ── Welle 3: Egress-Guard (SEC-004 / SEC-021) ───────────────────────────────────
@pytest.mark.asyncio
async def test_egress_guard_blocks_foreign_host():
    """Ein nicht-allowlisteter Host (z.B. Cloud-Metadata) wird blockiert."""
    from zh_education_mcp.server import _egress_guard

    req = httpx.Request("GET", "https://169.254.169.254/latest/meta-data/")
    with pytest.raises(PermissionError):
        await _egress_guard(req)


@pytest.mark.asyncio
async def test_egress_guard_blocks_non_https():
    """HTTP (ohne TLS) wird auch für den erlaubten Host blockiert."""
    from zh_education_mcp.server import _egress_guard

    req = httpx.Request("GET", "http://www.bista.zh.ch/basicapi/ogd/x")
    with pytest.raises(PermissionError):
        await _egress_guard(req)


@pytest.mark.asyncio
async def test_egress_guard_allows_bista():
    """Der allowlistete BISTA-Host über HTTPS wird durchgelassen."""
    from zh_education_mcp.server import _egress_guard

    req = httpx.Request("GET", "https://www.bista.zh.ch/basicapi/ogd/x")
    assert await _egress_guard(req) is None


# ── Welle 3: strikte Input-Validierung (SEC-018) ────────────────────────────────
def test_strict_rejects_out_of_range():
    """letzte_n_jahre ausserhalb [1,30] wird abgelehnt."""
    import pydantic

    from zh_education_mcp.server import SchulkreisTrendInput

    with pytest.raises(pydantic.ValidationError):
        SchulkreisTrendInput(schulgemeinde="Letzi", letzte_n_jahre=99)


def test_strict_rejects_unknown_field():
    """Unbekannte Felder werden durch extra='forbid' abgelehnt."""
    import pydantic

    from zh_education_mcp.server import UebersichtInput

    with pytest.raises(pydantic.ValidationError):
        UebersichtInput(unbekannt="x")


def test_strict_rejects_too_long_string():
    """Strings über max_length werden abgelehnt."""
    import pydantic

    from zh_education_mcp.server import Sek1ProfilInput

    with pytest.raises(pydantic.ValidationError):
        Sek1ProfilInput(schulgemeinde="x" * 500)


def test_response_format_accepts_string():
    """response_format akzeptiert weiterhin den JSON-String (MCP-Client)."""
    from zh_education_mcp.server import ResponseFormat, UebersichtInput

    assert UebersichtInput(response_format="json").response_format == ResponseFormat.JSON


# ── Welle 3: Fehler-Sanitisierung (OBS-002) ─────────────────────────────────────
def test_handle_error_does_not_leak_internals():
    """Generische Exceptions geben keine str(e)-Internals an den Client."""
    from zh_education_mcp.server import _handle_error

    msg = _handle_error(RuntimeError("geheime DB-Verbindung postgres://secret@host"))
    assert "secret" not in msg
    assert "postgres" not in msg
    assert "RuntimeError" not in msg
    assert msg.startswith("Fehler:")


# ── Welle 4b: Response-Envelope & Provenance (SDK-002, ARCH-007, CH-004) ─────────
def test_envelope_carries_source_and_count():
    """JSON-Envelope enthält source/provenance/license/match_type/count."""
    import json

    from zh_education_mcp.server import SOURCE_LICENSE, _envelope

    payload = json.loads(_envelope([{"x": 1}, {"x": 2}], schulgemeinde="Letzi"))
    assert payload["source"]
    assert payload["provenance"]["license"] == SOURCE_LICENSE
    assert payload["match_type"] == "exact"
    assert payload["count"] == 2
    assert payload["schulgemeinde"] == "Letzi"
    assert payload["results"] == [{"x": 1}, {"x": 2}]


def test_not_found_json_has_match_type_none():
    """Not-Found im JSON-Format liefert match_type='none' + suggestions."""
    import json

    from zh_education_mcp.server import ResponseFormat, _not_found

    out = _not_found(ResponseFormat.JSON, "nicht gefunden", suggestions=["Zürich-Letzi"])
    payload = json.loads(out)
    assert payload["match_type"] == "none"
    assert payload["suggestions"] == ["Zürich-Letzi"]
    assert payload["count"] == 0


@pytest.mark.asyncio
async def test_markdown_output_has_source_footer():
    """Markdown-Tool-Antworten tragen die CC-BY-Quellen-Fusszeile (CH-004)."""
    from zh_education_mcp.server import ListSchulgemeindensInput, zh_edu_list_schulgemeinden

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_lernende_sekundarstufe_i_anforderungstyp").mock(
            return_value=httpx.Response(200, text=SAMPLE_SEK1_CSV)
        )
        result = await zh_edu_list_schulgemeinden(ListSchulgemeindensInput())

    assert "CC BY 4.0" in result
    assert "BISTA" in result


@pytest.mark.asyncio
async def test_json_tool_output_is_enveloped():
    """Ein Tool im JSON-Format liefert den strukturierten Envelope."""
    import json

    from zh_education_mcp.server import ListSchulgemeindensInput, zh_edu_list_schulgemeinden

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_lernende_sekundarstufe_i_anforderungstyp").mock(
            return_value=httpx.Response(200, text=SAMPLE_SEK1_CSV)
        )
        params = ListSchulgemeindensInput(response_format="json")
        result = await zh_edu_list_schulgemeinden(params)

    payload = json.loads(result)
    assert payload["source"]
    assert "Zürich-Letzi" in payload["results"]
    assert payload["count"] >= 1


# ── Welle 4b: Tests für bisher ungetestete Tools (OPS-001) ──────────────────────
SAMPLE_MATURITAET_CSV = csv_fixture("maturitaet")

SAMPLE_WOHNORT_CSV = csv_fixture("wohnort")

SAMPLE_MITTELSCHULEN_CSV = csv_fixture("mittelschulen")


@pytest.mark.asyncio
async def test_maturitaetsquote_filter_bezirk():
    """Maturitätsquote filtert nach Bezirk und zeigt Quote."""
    from zh_education_mcp.server import MaturitaetsquoteInput, zh_edu_maturitaetsquote

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_maturitaetsquote_gemeinden_und_kanton").mock(
            return_value=httpx.Response(200, text=SAMPLE_MATURITAET_CSV)
        )
        result = await zh_edu_maturitaetsquote(MaturitaetsquoteInput(gemeinde="Zürich"))

    assert "Zürich" in result
    assert "22.9%" in result


@pytest.mark.asyncio
async def test_maturitaetsquote_zeigt_die_19_jaehrigen():
    """Die Spalte «19-Jährige» trägt eine Zahl, keinen Gedankenstrich.

    Der Regressionstest zu einem Befund, den kein Test dieser Datei sehen
    konnte: `_normalise_keys` senkt seit dem Fix vom 3.8.2026 jede Kopfzeile
    auf Kleinschreibung, diese eine Aufrufstelle las aber weiter
    `Total_19_Jahre_alt`. `.get()` mit Default wirft nicht und loggt nicht —
    die Spalte stand in jeder Zeile jeder Antwort auf «—», und die beiden
    bestehenden Tests prüfen genau die zwei Spalten, die funktionierten.

    Gefunden hat es `schema_field_probe` aus mcp-continuous-auditor gegen die
    Live-Quelle. Diese Zusicherung ist, was den Befund im Repo hält.
    """
    from zh_education_mcp.server import MaturitaetsquoteInput, zh_edu_maturitaetsquote

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_maturitaetsquote_gemeinden_und_kanton").mock(
            return_value=httpx.Response(200, text=SAMPLE_MATURITAET_CSV)
        )
        result = await zh_edu_maturitaetsquote(MaturitaetsquoteInput(gemeinde="Zürich"))

    zeile = next(z for z in result.splitlines() if z.startswith("| Zürich "))
    spalten = [s.strip() for s in zeile.strip("|").split("|")]
    # Werte aus der aufgezeichneten Fixture (Zürich, jüngster Jahrgang darin).
    # Die Quote steht hier als 22.9 % und nicht als 2290.0 %: Die Quelle
    # publiziert die Spalte bereits in Prozent. Die alte Fixture schrieb eine
    # Bruchzahl hinein, die es in der Quelle nicht gibt, und deckte damit ein
    # `* 100` im Produktivcode zu.
    assert spalten == ["Zürich", "Bezirk Zürich", "2913", "12723", "22.9%"], zeile


@pytest.mark.asyncio
async def test_maturitaetsquote_liest_die_gesenkte_kopfzeile():
    """Auch wenn BISTA die Kopfzeile kleinschreibt, bleibt die Tabelle voll.

    Die Fixture oben trägt die Schreibweise, die BISTA am 7.8.2026 lieferte.
    Sie kann sich ändern — das ist der ganze Grund für `_normalise_keys` — und
    ein Test, der nur die eine Schreibweise kennt, hält den Fix nicht fest.
    """
    from zh_education_mcp.server import MaturitaetsquoteInput, zh_edu_maturitaetsquote

    gesenkt = (
        SAMPLE_MATURITAET_CSV.split("\n")[0].lower()
        + "\n"
        + "\n".join(SAMPLE_MATURITAET_CSV.split("\n")[1:])
    )
    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_maturitaetsquote_gemeinden_und_kanton").mock(
            return_value=httpx.Response(200, text=gesenkt)
        )
        result = await zh_edu_maturitaetsquote(MaturitaetsquoteInput(gemeinde="Zürich"))

    assert "| 12723 |" in result


@pytest.mark.asyncio
async def test_maturitaetsquote_json_envelope():
    """Maturitätsquote im JSON-Format liefert den Envelope."""
    import json

    from zh_education_mcp.server import MaturitaetsquoteInput, zh_edu_maturitaetsquote

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_maturitaetsquote_gemeinden_und_kanton").mock(
            return_value=httpx.Response(200, text=SAMPLE_MATURITAET_CSV)
        )
        result = await zh_edu_maturitaetsquote(MaturitaetsquoteInput(response_format="json"))

    payload = json.loads(result)
    # 24 Zeilen: Zürich und Winterthur über alle Jahrgänge der Quelle. Die Zahl
    # kommt aus der Auswahlregel in scripts/record_fixtures.py, nicht aus einer
    # Annahme über die Quelle.
    assert payload["count"] == 24
    assert payload["source"]


@pytest.mark.asyncio
async def test_wohnort_trend_aggregates_years():
    """Wohnort-Trend aggregiert Lernende über Jahre und zeigt Veränderung."""
    from zh_education_mcp.server import WohnortTrendInput, zh_edu_wohnort_trend

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_lernende_nach_wohngemeinde").mock(
            return_value=httpx.Response(200, text=SAMPLE_WOHNORT_CSV)
        )
        result = await zh_edu_wohnort_trend(
            WohnortTrendInput(gebiet="Winterthur", letzte_n_jahre=5)
        )

    assert "Winterthur" in result
    assert "2024" in result
    assert "Veränderung" in result


@pytest.mark.asyncio
async def test_wohnort_trend_not_found_json():
    """Wohnort-Trend ohne Treffer liefert im JSON match_type='none'."""
    import json

    from zh_education_mcp.server import WohnortTrendInput, zh_edu_wohnort_trend

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_lernende_nach_wohngemeinde").mock(
            return_value=httpx.Response(200, text=SAMPLE_WOHNORT_CSV)
        )
        result = await zh_edu_wohnort_trend(
            WohnortTrendInput(gebiet="Nichtexistent", response_format="json")
        )

    assert json.loads(result)["match_type"] == "none"


@pytest.mark.asyncio
async def test_mittelschulen_groups_by_typ():
    """Mittelschulen gruppiert nach Typ (Gymnasium, FMS, HMS)."""
    from zh_education_mcp.server import MittelschulenInput, zh_edu_mittelschulen

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_lernende_mittelschulen").mock(
            return_value=httpx.Response(200, text=SAMPLE_MITTELSCHULEN_CSV)
        )
        result = await zh_edu_mittelschulen(MittelschulenInput())

    # Die Quelle schreibt die Typen aus. «FMS»/«HMS» waren Abkürzungen der
    # erfundenen Fixture — in den echten Daten stehen «Fachmittelschule» und
    # «Handelsmittelschule».
    assert "Gymnasium" in result
    assert "Fachmittelschule" in result
    assert "Handelsmittelschule" in result


@pytest.mark.asyncio
async def test_mittelschulen_filter_typ_json():
    """Mittelschulen mit Typ-Filter im JSON-Format."""
    import json

    from zh_education_mcp.server import MittelschulenInput, zh_edu_mittelschulen

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_lernende_mittelschulen").mock(
            return_value=httpx.Response(200, text=SAMPLE_MITTELSCHULEN_CSV)
        )
        result = await zh_edu_mittelschulen(
            MittelschulenInput(mittelschultyp="Gymnasium", response_format="json")
        )

    payload = json.loads(result)
    # Zahl und Jahrgang aus der aufgezeichneten Fixture abgeleitet, nicht
    # hingeschrieben — sonst prüft der Test ab dem nächsten Jahrgang etwas
    # anderes, als sein Name sagt.
    assert payload["count"] == 143
    assert payload["jahr"] == int(latest_year("mittelschulen"))


# ── Welle 4b: Resources als zweites MCP-Primitiv (ARCH-008) ─────────────────────
def test_datenquellen_resource_lists_datasets():
    """Die Datenquellen-Resource listet Endpunkte mit Tool-Zuordnung."""
    import json

    from zh_education_mcp.tools import datenquellen_resource

    payload = json.loads(datenquellen_resource())
    assert payload["source"]["license"] == "CC BY 4.0"
    assert len(payload["datasets"]) == 6


def test_lizenz_resource_has_attribution():
    """Die Lizenz-Resource enthält die CC-BY-Attribution."""
    import json

    from zh_education_mcp.tools import lizenz_resource

    payload = json.loads(lizenz_resource())
    assert payload["license"] == "CC BY 4.0"


# ── Folge-Fix: OBS-001 — Execution-Errors als isError:true (ToolError) ───────────
@pytest.mark.asyncio
async def test_execution_error_raises_toolerror():
    """Ein Backend-Fehler wird als ToolError (isError:true) signalisiert, sanitisiert."""
    from mcp.server.mcpserver.exceptions import ToolError

    from zh_education_mcp.server import UebersichtInput, zh_edu_overview

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_uebersicht_alle_lernende").mock(
            return_value=httpx.Response(500, text="internal db error postgres://x")
        )
        with pytest.raises(ToolError) as exc:
            await zh_edu_overview(UebersichtInput())

    msg = str(exc.value)
    assert msg.startswith("Fehler:")
    assert "postgres" not in msg


# ── Folge-Fix: SDK-003 — Context-Injektion (Progress + Logging) ──────────────────
@pytest.mark.asyncio
async def test_ctx_progress_and_logging_on_fetch():
    """Bei nicht-gecachtem Fetch werden ctx.info und ctx.report_progress aufgerufen."""
    from unittest.mock import AsyncMock

    from zh_education_mcp.server import UebersichtInput, zh_edu_overview

    ctx = AsyncMock()
    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_uebersicht_alle_lernende").mock(
            return_value=httpx.Response(200, text=SAMPLE_UEBERSICHT_CSV)
        )
        result = await zh_edu_overview(UebersichtInput(), ctx=ctx)

    assert latest_year("uebersicht") in result
    assert ctx.info.await_count >= 1
    assert ctx.report_progress.await_count >= 1


@pytest.mark.asyncio
async def test_tool_works_without_ctx():
    """Ohne ctx (Direktaufruf) funktioniert das Tool unverändert."""
    from zh_education_mcp.server import UebersichtInput, zh_edu_overview

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_uebersicht_alle_lernende").mock(
            return_value=httpx.Response(200, text=SAMPLE_UEBERSICHT_CSV)
        )
        result = await zh_edu_overview(UebersichtInput())

    assert "Primarstufe" in result


# ── Folge-Fix: OBS-006 — OpenTelemetry-Span pro Tool-Call (opt-in) ───────────────
def test_traced_is_noop_without_otel():
    """Ohne aktivierten Tracer ist @traced ein No-Op (Standard-Pfad)."""
    import zh_education_mcp.telemetry as tel

    assert tel.setup_telemetry() is False or tel._tracer is not None


@pytest.mark.asyncio
async def test_otel_span_created_when_enabled():
    """Bei aktivem Tracer entsteht ein Span pro Tool-Call mit korrekten Attributen."""
    pytest.importorskip("opentelemetry.sdk")
    from opentelemetry import trace
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    import zh_education_mcp.telemetry as tel
    from zh_education_mcp.server import UebersichtInput, zh_edu_overview

    provider = TracerProvider()
    mem = InMemorySpanExporter()
    provider.add_span_processor(SimpleSpanProcessor(mem))
    trace.set_tracer_provider(provider)
    saved = tel._tracer
    tel._tracer = trace.get_tracer("zh_education_mcp")
    try:
        with respx.mock:
            respx.get(f"{BISTA_BASE}/data_uebersicht_alle_lernende").mock(
                return_value=httpx.Response(200, text=SAMPLE_UEBERSICHT_CSV)
            )
            await zh_edu_overview(UebersichtInput())
        spans = mem.get_finished_spans()
        assert any(s.name == "mcp.tool/zh_edu_overview" for s in spans)
        span = next(s for s in spans if s.name == "mcp.tool/zh_edu_overview")
        assert span.attributes["mcp.tool.name"] == "zh_edu_overview"
        assert span.attributes["mcp.tool.result.is_error"] is False
    finally:
        tel._tracer = saved


# ── Folge-Fix: SEC-005 — DNS-Pinning / IP-Blocklist gegen Rebinding ──────────────
@pytest.mark.parametrize(
    "ip,blocked",
    [
        ("169.254.169.254", True),  # Cloud-Metadata
        ("127.0.0.1", True),  # Loopback
        ("10.0.0.5", True),  # privat
        ("192.168.1.1", True),  # privat
        ("::1", True),  # IPv6-Loopback
        ("fe80::1", True),  # IPv6-Link-local
        ("8.8.8.8", False),  # öffentlich
        ("not-an-ip", True),  # ungültig → blockiert
    ],
)
def test_ip_blocklist_classification(ip, blocked):
    from zh_education_mcp.http_client import _ip_is_blocked

    assert _ip_is_blocked(ip) is blocked


def test_resolve_rejects_internal_ip(monkeypatch):
    """Löst der Host auf eine Metadata-IP auf, wird vor dem Request abgebrochen."""
    import socket

    from zh_education_mcp.http_client import _resolve_and_validate

    monkeypatch.setattr(
        "zh_education_mcp.http_client.socket.getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("169.254.169.254", 443))],
    )
    with pytest.raises(PermissionError):
        _resolve_and_validate("www.bista.zh.ch")


def test_resolve_allows_public_ip(monkeypatch):
    import socket

    from zh_education_mcp.http_client import _resolve_and_validate

    monkeypatch.setattr(
        "zh_education_mcp.http_client.socket.getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("8.8.8.8", 443))],
    )
    assert _resolve_and_validate("www.bista.zh.ch") == ["8.8.8.8"]


@pytest.mark.asyncio
async def test_egress_guard_blocks_rebinding_to_metadata(monkeypatch):
    """Allowlisteter Host, der auf eine interne IP zeigt, wird geblockt (Rebinding)."""
    import socket

    from zh_education_mcp.http_client import _egress_guard

    monkeypatch.setattr(
        "zh_education_mcp.http_client.socket.getaddrinfo",
        lambda *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 0, "", ("169.254.169.254", 443))],
    )
    req = httpx.Request("GET", "https://www.bista.zh.ch/basicapi/ogd/x")
    with pytest.raises(PermissionError):
        await _egress_guard(req)
