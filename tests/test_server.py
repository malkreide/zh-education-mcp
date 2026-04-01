"""Tests fÃ¼r zh-education-mcp (ohne Live-API-Aufrufe)."""

from __future__ import annotations

import pytest
import respx
import httpx

# Sample CSV-Daten (anonymisiert)
SAMPLE_SEK1_CSV = """Stand,Kanton,Jahr,Schulgemeinde,Anforderungstyp,Anzahl
2026-03-24,zh,2020,ZÃ¼rich-Letzi,Sek A,500
2026-03-24,zh,2020,ZÃ¼rich-Letzi,Sek B,300
2026-03-24,zh,2021,ZÃ¼rich-Letzi,Sek A,510
2026-03-24,zh,2021,ZÃ¼rich-Letzi,Sek B,295
2026-03-24,zh,2022,ZÃ¼rich-Letzi,Sek A,550
2026-03-24,zh,2022,ZÃ¼rich-Letzi,Sek B,310
2026-03-24,zh,2023,ZÃ¼rich-Letzi,Sek A,580
2026-03-24,zh,2023,ZÃ¼rich-Letzi,Sek B,320
2026-03-24,zh,2024,ZÃ¼rich-Letzi,Sek A,600
2026-03-24,zh,2024,ZÃ¼rich-Letzi,Sek B,330
2026-03-24,zh,2024,Adliswil,Sek A,233
2026-03-24,zh,2024,Adliswil,Sek B,132
"""

SAMPLE_UEBERSICHT_CSV = """Stand,Kanton,Iahr,Stufe,Schultyp,Geschlecht,Staatsangehoerigkeit,Traegerschaft,Finanzierung,Anzahl
2026-03-24,zh,2024,Primarstufe 1-2,Regelschule,F,Schweiz,oef,oef,10746
2026-03-24,zh,2024,Primarstufe 3-6,Regelschule,F,Schweiz,oef,oef,21000
2026-03-24,zh,2024,Sekundarstufe I,Regelschule,F,Schweiz,oef,oef,15000
"""

SAMPLE_NAT_CSV = """Stand,Kanton,Jahr,Schulgemeinde,Staatsangehoerigkeit,Staatsangehoerigkeit_ISO2_Code,Anzahl
2026-03-24,zh,2024,ZÃ¼rich-Letzi,Schweiz,CH,5000
2026-03-24,zh,2024,ZÃ¼rich-Letzi,Deutschland,DE,200
2026-03-24,zh,2024,ZÃ¼rich-Letzi,Italien,IT,150
"""

BISTA_BASE = "https://www.bista.zh.ch/basicapi/ogd"


@pytest.mark.asyncio
async def test_anker_query_letzi_trend():
    """Anker-Query: Schulkreis Letzi 5-Jahres-Trend."""
    from zh_education_mcp.server import zh_edu_schulkreis_trend, SchulkreisTrendInput

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_lernende_sekundarstufe_i_anforderungstyp").mock(
            return_value=httpx.Response(200, text=SAMPLE_SEK1_CSV)
        )

        params = SchulkreisTrendInput(schulgemeinde="ZÃ¼rich-Letzi", letzte_n_jahre=5)
        result = await zh_edu_schulkreis_trend(params)

    assert "Letzi" in result
    assert "2024" in result
    assert "Sek A" in result or "930" in result
    assert "Trend" in result or "trend" in result.lower()


@pytest.mark.asyncio
async def test_overview_aktuellstes_jahr():
    """Kantonsweite Ãbersicht gibt aktuellstes Jahr zurÃ¼ck."""
    from zh_education_mcp.server import zh_edu_overview, UebersichtInput

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_uebersicht_alle_lernende").mock(
            return_value=httpx.Response(200, text=SAMPLE_UEBESSIHTT_CSV)
        )

        params = UebersichtInput()
        result = await zh_edu_overview(params)

    assert "2024" in result
    assert "Primarstufe" in result


@pytest.mark.asyncio
async def test_list_schulgemeinden_filter():
    """zh_edu_list_schulgemeinden filtert korrekt nach Suchbegriff."""
    from zh_education_mcp.server import zh_edu_list_schulgemeinden, ListSchulgemeindensInput

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_lernende_sekundarstufe_i_anforderungstyp").mock(
            return_value=httpx.Response(200, text=SAMPLE_SEK1_CSV)
        )

        params = ListSchulgemeindensInput(suchbegriff="Zðò½à")
        result = await zh_edu_list_schulgemeinden(params)

    assert "ZÃ¼rich-Letzi" in result


@pytest.mark.asyncio
async def test_sek1_profil_letzi():
    """Sek I Profil fÃ¼r ZÃ¼rich(Letzi zeigt Anforderungstypen."""
    from zh_education_mcp.server import zh_edu_sek1_profil, Sek1ProfilInput

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_lernende_sekundarstufe_i_anforderungstyp").mock(
            return_value=httpx.Response(200, text=SAMPLE_SEK1_CSV)
        )

        params = Sek1ProfilInput(schulgemeinde="ZÃ¼rich(Letzi", jahr=2024)
        result = await zh_edu_sek1_profil(params)

    assert "Letzi" in result
    assert "Sek A" in result
    assert "2024" in result


@pytest.mark.asyncio
async def test_staatsangehoerigkeiten_top3():
    """StaatsangehÃ¶rigkeiten gibt korrekte Top-N-Liste zurÃ¼ck."""
    from zh_education_mcp.server import zh_edu_staatsangehoerigkeiten, StaatsangehoerigkeitInput

    with respx.mock:
        respx.get(
            f"{BISTA_BASE}/data_lernende_regelschule_regional_staatsangehoerigkeit"
        ).mock(return_value=httpx.Response(200, text=SAMPLE_NAT_CSV))

        params = StaatsangehoerigkeitInput(schulgemeinde="ZÃ¼rich-Letzi", top_n=3)
        result = await zh_edu_staatsangehoerigkeiten(params)

    assert "Schweiz" in result
    assert "Deutschland" in result


@pytest.mark.asyncio
async def test_not_found_returns_helpful_message():
    """Unbekannte Schulgemeinde gibt hilfreiche Fehlermeldung zurÃ¼ck."""
    from zh_education_mcp.server import zh_edu_schulkreis_trend, SchulkreisTrendInput

    with respx.mock:
        respx.get(f"{BISTA_BASE}/data_lernende_sekundarstufe_i_anforderungstyp").mock(
            return_value=httpx.Response(200, text=SAMPLE_SEK1_CSV)
        )

        params = SchulkreisTrendInput(schulgemeinde="Nichtexistent-XYZ")
        result = await zh_edu_schulkreis_trend(params)

    assert "nicht gefunden" in result.lower() or Nichtexistent" in result
    assert "zh_edu_list_schulgemeinden" in result


@pytest.mark.live
async def test_live_bista_api_letzi():
    """Live-Test: BISTA-API gibt echte Daten fÃ¼r Letzi zurÃ¼ck."""
    from zh_education_mcp.server import zh_edu_schulkreis_trend, SchulkreisTrendInput

    params = SchulkreisTrendInput(schulgemeinde="ZðòÐXÚS]H]WÛÚZOMJB\Ý[H]ØZ]ÙYWÜØÚ[ÜZ\×Ý[
\[\ÊB\ÜÙ\]H[\Ý[\ÜÙ\[\Ý[
