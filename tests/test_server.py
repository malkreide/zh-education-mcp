"""Tests für zh-education-mcp (ohne Live-API-Aufrufe)."""

from __future__ import annotations

import httpx
import pytest
import respx

# Sample CSV-Daten (anonymisiert)
SAMPLE_SEK1_CSV = """Stand,Kanton,Jahr,Schulgemeinde,Anforderungstyp,Anzahl
2026-03-24,zh,2020,Zürich-Letzi,Sek A,500
2026-03-24,zh,2020,Zürich-Letzi,Sek B,300
2026-03-24,zh,2021,Zürich-Letzi,Sek A,510
2026-03-24,zh,2021,Zürich-Letzi,Sek B,295
2026-03-24,zh,2022,Zürich-Letzi,Sek A,550
2026-03-24,zh,2022,Zürich-Letzi,Sek B,310
2026-03-24,zh,2023,Zürich-Letzi,Sek A,580
2026-03-24,zh,2023,Zürich-Letzi,Sek B,320
2026-03-24,zh,2024,Zürich-Letzi,Sek A,600
2026-03-24,zh,2024,Zürich-Letzi,Sek B,330
2026-03-24,zh,2024,Adliswil,Sek A,233
2026-03-24,zh,2024,Adliswil,Sek B,132
"""

SAMPLE_UEBERSICHT_CSV = """Stand,Kanton,Jahr,Stufe,Schultyp,Geschlecht,Staatsangehoerigkeit,Traegerschaft,Finanzierung,Anzahl
2026-03-24,zh,2024,Primarstufe 1-2,Regelschule,F,Schweiz,oef,oef,10746
2026-03-24,zh,2024,Primarstufe 3-6,Regelschule,F,Schweiz,oef,oef,21000
2026-03-24,zh,2024,Sekundarstufe I,Regelschule,F,Schweiz,oef,oef,15000
"""

SAMPLE_NAT_CSV = """Stand,Kanton,Jahr,Schulgemeinde,Staatsangehoerigkeit,Staatsangehoerigkeit_ISO2_Code,Anzahl
2026-03-24,zh,2024,Zürich-Letzi,Schweiz,CH,5000
2026-03-24,zh,2024,Zürich-Letzi,Deutschland,DE,200
2026-03-24,zh,2024,Zürich-Letzi,Italien,IT,150
"""

BISTA_BASE = "https://www.bista.zh.ch/basicapi/ogd"


@pytest.fixture(autouse=True)
def _clear_cache():
    """Cache vor jedem Test leeren."""
    from zh_education_mcp.server import _cache
    _cache.clear()
    yield
    _cache.clear()


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
    assert "2024" in result
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

    assert "2024" in result
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
        respx.get(
            f"{BISTA_BASE}/data_lernende_regelschule_regional_staatsangehoerigkeit"
        ).mock(return_value=httpx.Response(200, text=SAMPLE_NAT_CSV))

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
