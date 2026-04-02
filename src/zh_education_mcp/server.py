#!/usr/bin/env python3
"""
zh-education-mcp — Bildungsstatistik Kanton & Stadt Zürich (BISTA) — v0.1.0

AI-nativer Zugang zu den Bildungsstatistiken des Kantons Zürich:
  · Lernende nach Schulgemeinde, Schulkreis, Stufe und Anforderungstyp
  · Maturitätsquoten nach Gemeinde, Bezirk und Kanton
  · Staatsangehörigkeiten der Lernenden
  · Mittelschulstatistiken (Gymnasium, FMS, HMS)

Datenquelle: BISTA Public API (bista.zh.ch/basicapi/ogd/)
Kein API-Schlüssel erforderlich. Stichtag: 15. September (jährlich).
"""

from __future__ import annotations

import csv
import io
import json
import sys
import time
from enum import StrEnum

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field, field_validator

# ─────────────────────────── Server ────────────────────────────────────────────
mcp = FastMCP("zh_education_mcp")

# ─────────────────────────── Konstanten ────────────────────────────────────────
BISTA_API    = "https://www.bista.zh.ch/basicapi/ogd"
HTTP_TIMEOUT = 30.0
CACHE_TTL    = 86_400  # 24 Stunden — passend zum jährlichen Stichtag

# Endpunkte
EP_SEK1          = "data_lernende_sekundarstufe_i_anforderungstyp"
EP_UEBERSICHT    = "data_uebersicht_alle_lernende"
EP_NAT_REGIONAL  = "data_lernende_regelschule_regional_staatsangehoerigkeit"
EP_MATURITAET    = "data_maturitaetsquote_gemeinden_und_kanton"
EP_WOHNORT       = "data_lernende_nach_wohngemeinde"
EP_MITTELSCHULEN = "data_lernende_mittelschulen"


# ─────────────────────────── Enum ──────────────────────────────────────────────
class ResponseFormat(StrEnum):
    """Ausgabeformat für Tool-Antworten."""
    MARKDOWN = "markdown"
    JSON     = "json"


# ─────────────────────────── Cache ─────────────────────────────────────────────
_cache: dict[str, tuple[float, list[dict]]] = {}


def _cache_get(key: str) -> list[dict] | None:
    """Gibt gecachte Daten zurück, falls TTL nicht abgelaufen."""
    entry = _cache.get(key)
    if entry and (time.time() - entry[0]) < CACHE_TTL:
        return entry[1]
    return None


def _cache_set(key: str, data: list[dict]) -> None:
    """Speichert Daten im Cache mit aktuellem Zeitstempel."""
    _cache[key] = (time.time(), data)


# ─────────────────────────── Shared Utilities ──────────────────────────────────
async def _http_get(url: str, params: dict | None = None) -> httpx.Response:
    """Wiederverwendbare HTTP-GET-Funktion mit einheitlichem Timeout."""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        return await client.get(url, params=params, timeout=HTTP_TIMEOUT)


def _handle_error(e: Exception) -> str:
    """Einheitliche, handlungsorientierte Fehlermeldungen (auf Deutsch)."""
    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        if code == 404:
            return "Fehler: Ressource nicht gefunden. Bitte Parameter prüfen."
        if code == 429:
            return "Fehler: Rate-Limit erreicht. Bitte kurz warten und erneut versuchen."
        if code in (502, 503):
            return "Fehler: Dienst vorübergehend nicht verfügbar. Bitte erneut versuchen."
        return f"Fehler: API-Anfrage fehlgeschlagen (HTTP {code})."
    if isinstance(e, httpx.TimeoutException):
        return "Fehler: Zeitüberschreitung. Der Dienst antwortet nicht. Bitte erneut versuchen."
    return f"Fehler: Unerwarteter Fehler ({type(e).__name__}): {e}"


async def _fetch_csv(endpoint: str) -> list[dict]:
    """Holt CSV-Daten von einem BISTA-Endpunkt und gibt eine Liste von Dicts zurück."""
    cached = _cache_get(endpoint)
    if cached is not None:
        return cached

    resp = await _http_get(f"{BISTA_API}/{endpoint}")
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    rows = list(reader)
    _cache_set(endpoint, rows)
    return rows


def _filter_rows(
    rows: list[dict],
    **filters: str | int | None,
) -> list[dict]:
    """Filtert Zeilen anhand beliebiger Feld=Wert-Paare (case-insensitive für Strings)."""
    result = rows
    for key, val in filters.items():
        if val is None:
            continue
        if isinstance(val, int):
            result = [r for r in result if r.get(key) == str(val)]
        else:
            val_lower = str(val).lower()
            result = [r for r in result if val_lower in r.get(key, "").lower()]
    return result


def _latest_year(rows: list[dict], year_field: str = "Jahr") -> int | None:
    """Ermittelt das aktuellste Jahr aus den Daten."""
    years = {int(r[year_field]) for r in rows if r.get(year_field, "").isdigit()}
    return max(years) if years else None


# ══════════════════════════════════════════════════════════════════════════════
#  INPUT-MODELLE (Pydantic v2)
# ══════════════════════════════════════════════════════════════════════════════

class ListSchulgemeindensInput(BaseModel):
    """Input für die Auflistung aller Schulgemeinden."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    suchbegriff: str | None = Field(
        default=None, max_length=200,
        description="Optionaler Suchbegriff zum Filtern (z. B. 'Zürich', 'Letzi', 'Adliswil')"
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class SchulkreisTrendInput(BaseModel):
    """Input für Schulkreis-Trend-Abfrage."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    schulgemeinde: str = Field(
        ..., min_length=1, max_length=200,
        description="Schulgemeinde / Schulkreis (z. B. 'Zürich-Letzi', 'Adliswil', 'Winterthur')"
    )
    letzte_n_jahre: int = Field(
        default=5, ge=1, le=30,
        description="Anzahl der letzten Jahre (Standard: 5)"
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)

    @field_validator("schulgemeinde")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Schulgemeinde darf nicht leer sein.")
        return v


class UebersichtInput(BaseModel):
    """Input für die kantonsweite Übersicht."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    jahr: int | None = Field(
        default=None,
        description="Bestimmtes Jahr (leer = aktuellstes verfügbares Jahr)"
    )
    stufe: str | None = Field(
        default=None, max_length=100,
        description="Schulstufe filtern (z. B. 'Primarstufe', 'Sekundarstufe I')"
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class Sek1ProfilInput(BaseModel):
    """Input für das Sek-I-Profil einer Schulgemeinde."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    schulgemeinde: str = Field(
        ..., min_length=1, max_length=200,
        description="Schulgemeinde (z. B. 'Zürich-Letzi', 'Winterthur')"
    )
    jahr: int | None = Field(
        default=None,
        description="Bestimmtes Jahr (leer = aktuellstes)"
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)

    @field_validator("schulgemeinde")
    @classmethod
    def not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Schulgemeinde darf nicht leer sein.")
        return v


class StaatsangehoerigkeitInput(BaseModel):
    """Input für Staatsangehörigkeitsabfrage."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    schulgemeinde: str = Field(
        ..., min_length=1, max_length=200,
        description="Schulgemeinde (z. B. 'Zürich-Letzi')"
    )
    top_n: int = Field(
        default=10, ge=1, le=100,
        description="Anzahl der häufigsten Staatsangehörigkeiten (Standard: 10)"
    )
    jahr: int | None = Field(
        default=None,
        description="Bestimmtes Jahr (leer = aktuellstes)"
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class MaturitaetsquoteInput(BaseModel):
    """Input für Maturitätsquoten-Abfrage."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    gemeinde: str | None = Field(
        default=None, max_length=200,
        description="Gemeindename filtern (z. B. 'Zürich', 'Winterthur'). Leer = alle."
    )
    bezirk: str | None = Field(
        default=None, max_length=200,
        description="Bezirk filtern (z. B. 'Zürich', 'Dietikon')"
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class WohnortTrendInput(BaseModel):
    """Input für wohnortbasierte Lernenden-Trends."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    gebiet: str | None = Field(
        default=None, max_length=200,
        description="Gebietsbezeichnung filtern (z. B. 'Zürich', 'Bezirk Winterthur')"
    )
    stufe: str | None = Field(
        default=None, max_length=100,
        description="Schulstufe filtern (z. B. 'Primarstufe', 'Sekundarstufe I')"
    )
    letzte_n_jahre: int = Field(
        default=5, ge=1, le=30,
        description="Anzahl der letzten Jahre (Standard: 5)"
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


class MittelschulenInput(BaseModel):
    """Input für Mittelschulstatistiken."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    mittelschultyp: str | None = Field(
        default=None, max_length=100,
        description="Schultyp filtern (z. B. 'Gymnasium', 'FMS', 'HMS')"
    )
    jahr: int | None = Field(
        default=None,
        description="Bestimmtes Jahr (leer = aktuellstes)"
    )
    response_format: ResponseFormat = Field(default=ResponseFormat.MARKDOWN)


# ══════════════════════════════════════════════════════════════════════════════
#  TOOL 1 — Schulgemeinden auflisten
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool(
    name="zh_edu_list_schulgemeinden",
    annotations={
        "title": "Schulgemeinden auflisten",
        "readOnlyHint":    True,
        "destructiveHint": False,
        "idempotentHint":  True,
        "openWorldHint":   True,
    },
)
async def zh_edu_list_schulgemeinden(params: ListSchulgemeindensInput) -> str:
    """Listet alle Schulgemeinden und Schulkreise im Kanton Zürich auf.

    Extrahiert die eindeutigen Schulgemeinden aus den Sekundarstufe-I-Daten.
    Nützlich als Einstieg, um gültige Namen für andere Tools zu finden.

    Args:
        params (ListSchulgemeindensInput):
            - suchbegriff (str | None): Filter nach Teilstring (z. B. 'Zürich')
            - response_format: 'markdown' oder 'json'

    Returns:
        str: Alphabetische Liste aller Schulgemeinden.
    """
    try:
        rows = await _fetch_csv(EP_SEK1)
        gemeinden = sorted({r["Schulgemeinde"] for r in rows if r.get("Schulgemeinde")})

        if params.suchbegriff:
            needle = params.suchbegriff.lower()
            gemeinden = [g for g in gemeinden if needle in g.lower()]

        if not gemeinden:
            return "Keine Schulgemeinden gefunden für den angegebenen Suchbegriff."

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"total": len(gemeinden), "schulgemeinden": gemeinden},
                              ensure_ascii=False, indent=2)

        lines = ["# Schulgemeinden Kanton Zürich\n"]
        if params.suchbegriff:
            lines.append(f"**Filter:** *{params.suchbegriff}*\n")
        lines.append(f"Gefunden: **{len(gemeinden)}** Schulgemeinden\n")
        for g in gemeinden:
            lines.append(f"- {g}")
        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


# ══════════════════════════════════════════════════════════════════════════════
#  TOOL 2 — Schulkreis-Trend
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool(
    name="zh_edu_schulkreis_trend",
    annotations={
        "title": "Lernenden-Trend nach Schulkreis",
        "readOnlyHint":    True,
        "destructiveHint": False,
        "idempotentHint":  True,
        "openWorldHint":   True,
    },
)
async def zh_edu_schulkreis_trend(params: SchulkreisTrendInput) -> str:
    """Zeigt den Lernenden-Trend für eine Schulgemeinde / einen Schulkreis.

    Liefert die Entwicklung der Lernendenzahlen (Sek I) über die letzten N Jahre,
    aufgeschlüsselt nach Anforderungstyp (Sek A, Sek B, Sek C etc.).

    Args:
        params (SchulkreisTrendInput):
            - schulgemeinde (str): Name der Schulgemeinde (z. B. 'Zürich-Letzi')
            - letzte_n_jahre (int): Anzahl Jahre rückwärts (Standard: 5)
            - response_format: 'markdown' oder 'json'

    Returns:
        str: Trend-Übersicht mit Jahresvergleich und Gesamtentwicklung.
    """
    try:
        rows = await _fetch_csv(EP_SEK1)
        matched = _filter_rows(rows, Schulgemeinde=params.schulgemeinde)

        if not matched:
            gemeinden = sorted({r["Schulgemeinde"] for r in rows if r.get("Schulgemeinde")})
            suggestions = [g for g in gemeinden if params.schulgemeinde.lower()[:4] in g.lower()]
            hint = f" Meinten Sie: {', '.join(suggestions[:5])}?" if suggestions else ""
            return (
                f"Schulgemeinde '{params.schulgemeinde}' nicht gefunden.{hint}\n\n"
                f"Tipp: Verwende `zh_edu_list_schulgemeinden`, um gültige Namen zu sehen."
            )

        latest = _latest_year(matched)
        if latest is None:
            return "Keine Jahresdaten verfügbar."

        cutoff = latest - params.letzte_n_jahre + 1
        filtered = [r for r in matched if r.get("Jahr", "").isdigit() and int(r["Jahr"]) >= cutoff]
        filtered.sort(key=lambda r: (int(r.get("Jahr", 0)), r.get("Anforderungstyp", "")))

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"schulgemeinde": params.schulgemeinde, "daten": filtered},
                              ensure_ascii=False, indent=2)

        lines = [f"# Trend {params.schulgemeinde} ({cutoff}–{latest})\n"]

        by_year: dict[int, dict[str, int]] = {}
        for r in filtered:
            yr = int(r["Jahr"])
            typ = r.get("Anforderungstyp", "Unbekannt")
            anzahl = int(r.get("Anzahl", 0))
            by_year.setdefault(yr, {})[typ] = anzahl

        typen = sorted({r.get("Anforderungstyp", "") for r in filtered} - {""})
        header = "| Jahr | " + " | ".join(typen) + " | Total |"
        sep = "|------|" + "|".join(["------:"] * len(typen)) + "|------:|"
        lines.extend([header, sep])

        for yr in sorted(by_year):
            vals = by_year[yr]
            total = sum(vals.values())
            cells = [str(vals.get(t, 0)) for t in typen]
            lines.append(f"| {yr} | " + " | ".join(cells) + f" | **{total}** |")

        years_list = sorted(by_year.keys())
        if len(years_list) >= 2:
            first_total = sum(by_year[years_list[0]].values())
            last_total = sum(by_year[years_list[-1]].values())
            diff = last_total - first_total
            sign = "+" if diff >= 0 else ""
            lines.append(f"\n**Veränderung {years_list[0]}→{years_list[-1]}:** {sign}{diff} Lernende")

        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


# ══════════════════════════════════════════════════════════════════════════════
#  TOOL 3 — Kantonsweite Übersicht
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool(
    name="zh_edu_overview",
    annotations={
        "title": "Kantonsweite Lernenden-Übersicht",
        "readOnlyHint":    True,
        "destructiveHint": False,
        "idempotentHint":  True,
        "openWorldHint":   True,
    },
)
async def zh_edu_overview(params: UebersichtInput) -> str:
    """Gibt eine kantonsweite Übersicht aller Lernenden nach Stufe, Typ und Geschlecht.

    Datenquelle: BISTA-Übersicht aller Lernenden im Kanton Zürich.
    Umfasst Primarstufe, Sekundarstufe I, Sekundarstufe II und Tertiärstufe.

    Args:
        params (UebersichtInput):
            - jahr (int | None): Bestimmtes Jahr (leer = aktuellstes)
            - stufe (str | None): Filter nach Schulstufe
            - response_format: 'markdown' oder 'json'

    Returns:
        str: Übersichtstabelle mit Lernenden nach Stufe und Schultyp.
    """
    try:
        rows = await _fetch_csv(EP_UEBERSICHT)

        jahr = params.jahr or _latest_year(rows)
        if jahr is None:
            return "Keine Jahresdaten verfügbar."

        filtered = [r for r in rows if r.get("Jahr") == str(jahr)]
        if params.stufe:
            filtered = _filter_rows(filtered, Stufe=params.stufe)

        if not filtered:
            return f"Keine Daten für Jahr {jahr} gefunden."

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"jahr": jahr, "daten": filtered}, ensure_ascii=False, indent=2)

        lines = [f"# Übersicht Lernende Kanton Zürich — {jahr}\n"]

        by_stufe: dict[str, int] = {}
        for r in filtered:
            stufe = r.get("Stufe", "Unbekannt")
            anzahl = int(r.get("Anzahl", 0))
            by_stufe[stufe] = by_stufe.get(stufe, 0) + anzahl

        lines.append("| Stufe | Lernende |")
        lines.append("|-------|--------:|")
        total = 0
        for stufe in sorted(by_stufe):
            lines.append(f"| {stufe} | {by_stufe[stufe]:,} |")
            total += by_stufe[stufe]
        lines.append(f"| **Total** | **{total:,}** |")

        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


# ══════════════════════════════════════════════════════════════════════════════
#  TOOL 4 — Sek-I-Profil
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool(
    name="zh_edu_sek1_profil",
    annotations={
        "title": "Sekundarstufe I Profil",
        "readOnlyHint":    True,
        "destructiveHint": False,
        "idempotentHint":  True,
        "openWorldHint":   True,
    },
)
async def zh_edu_sek1_profil(params: Sek1ProfilInput) -> str:
    """Zeigt das Sek-I-Profil einer Schulgemeinde (Anforderungstypen A/B/C).

    Schlüsselt die Lernenden der Sekundarstufe I nach Anforderungstyp auf:
    Sek A (höchste Anforderungen), Sek B, Sek C, Mittelschule, Sonderklassen.

    Args:
        params (Sek1ProfilInput):
            - schulgemeinde (str): Schulgemeinde (z. B. 'Zürich-Letzi')
            - jahr (int | None): Bestimmtes Jahr (leer = aktuellstes)
            - response_format: 'markdown' oder 'json'

    Returns:
        str: Profil mit Anzahl und Anteil pro Anforderungstyp.
    """
    try:
        rows = await _fetch_csv(EP_SEK1)
        matched = _filter_rows(rows, Schulgemeinde=params.schulgemeinde)

        if not matched:
            return (
                f"Schulgemeinde '{params.schulgemeinde}' nicht gefunden.\n\n"
                f"Tipp: Verwende `zh_edu_list_schulgemeinden`, um gültige Namen zu sehen."
            )

        jahr = params.jahr or _latest_year(matched)
        if jahr is None:
            return "Keine Jahresdaten verfügbar."

        year_data = [r for r in matched if r.get("Jahr") == str(jahr)]
        if not year_data:
            return f"Keine Daten für {params.schulgemeinde} im Jahr {jahr}."

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"schulgemeinde": params.schulgemeinde, "jahr": jahr,
                              "profil": year_data}, ensure_ascii=False, indent=2)

        lines = [f"# Sek-I-Profil {params.schulgemeinde} — {jahr}\n"]
        lines.append("| Anforderungstyp | Lernende | Anteil |")
        lines.append("|-----------------|--------:|-------:|")

        total = sum(int(r.get("Anzahl", 0)) for r in year_data)
        for r in sorted(year_data, key=lambda x: int(x.get("Anzahl", 0)), reverse=True):
            typ = r.get("Anforderungstyp", "Unbekannt")
            anzahl = int(r.get("Anzahl", 0))
            pct = f"{anzahl / total * 100:.1f}%" if total > 0 else "—"
            lines.append(f"| {typ} | {anzahl:,} | {pct} |")
        lines.append(f"| **Total** | **{total:,}** | **100%** |")

        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


# ══════════════════════════════════════════════════════════════════════════════
#  TOOL 5 — Staatsangehörigkeiten
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool(
    name="zh_edu_staatsangehoerigkeiten",
    annotations={
        "title": "Staatsangehörigkeiten der Lernenden",
        "readOnlyHint":    True,
        "destructiveHint": False,
        "idempotentHint":  True,
        "openWorldHint":   True,
    },
)
async def zh_edu_staatsangehoerigkeiten(params: StaatsangehoerigkeitInput) -> str:
    """Zeigt die Staatsangehörigkeitsstruktur der Lernenden einer Schulgemeinde.

    Liefert die häufigsten Nationalitäten der Schüler·innen in einer
    Schulgemeinde, inkl. ISO2-Ländercode und Anteil.

    Args:
        params (StaatsangehoerigkeitInput):
            - schulgemeinde (str): Schulgemeinde (z. B. 'Zürich-Letzi')
            - top_n (int): Anzahl Top-Nationalitäten (Standard: 10)
            - jahr (int | None): Bestimmtes Jahr (leer = aktuellstes)
            - response_format: 'markdown' oder 'json'

    Returns:
        str: Rangliste der häufigsten Nationalitäten mit Anteil.
    """
    try:
        rows = await _fetch_csv(EP_NAT_REGIONAL)
        matched = _filter_rows(rows, Schulgemeinde=params.schulgemeinde)

        if not matched:
            return (
                f"Schulgemeinde '{params.schulgemeinde}' nicht gefunden.\n\n"
                f"Tipp: Verwende `zh_edu_list_schulgemeinden`, um gültige Namen zu sehen."
            )

        jahr = params.jahr or _latest_year(matched)
        if jahr is None:
            return "Keine Jahresdaten verfügbar."

        year_data = [r for r in matched if r.get("Jahr") == str(jahr)]
        year_data.sort(key=lambda r: int(r.get("Anzahl", 0)), reverse=True)
        top = year_data[: params.top_n]

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"schulgemeinde": params.schulgemeinde, "jahr": jahr,
                              "top_n": params.top_n, "nationalitaeten": top},
                              ensure_ascii=False, indent=2)

        total = sum(int(r.get("Anzahl", 0)) for r in year_data)
        lines = [f"# Staatsangehörigkeiten {params.schulgemeinde} — {jahr}\n"]
        lines.append(f"Top {params.top_n} von {len(year_data)} Nationalitäten "
                     f"(Total: {total:,} Lernende)\n")
        lines.append("| # | Staatsangehörigkeit | ISO2 | Lernende | Anteil |")
        lines.append("|---|---------------------|------|--------:|-------:|")

        for i, r in enumerate(top, 1):
            nat = r.get("Staatsangehoerigkeit", "Unbekannt")
            iso2 = r.get("Staatsangehoerigkeit_ISO2_Code", "—")
            anzahl = int(r.get("Anzahl", 0))
            pct = f"{anzahl / total * 100:.1f}%" if total > 0 else "—"
            lines.append(f"| {i} | {nat} | {iso2} | {anzahl:,} | {pct} |")

        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


# ══════════════════════════════════════════════════════════════════════════════
#  TOOL 6 — Maturitätsquote
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool(
    name="zh_edu_maturitaetsquote",
    annotations={
        "title": "Gymnasiale Maturitätsquote",
        "readOnlyHint":    True,
        "destructiveHint": False,
        "idempotentHint":  True,
        "openWorldHint":   True,
    },
)
async def zh_edu_maturitaetsquote(params: MaturitaetsquoteInput) -> str:
    """Zeigt die gymnasiale Maturitätsquote nach Gemeinde, Bezirk und Kanton.

    Die Maturitätsquote berechnet sich als Anteil der gymnasialen Abschlüsse
    an der 19-jährigen Wohnbevölkerung einer Gemeinde.

    Args:
        params (MaturitaetsquoteInput):
            - gemeinde (str | None): Gemeindename filtern
            - bezirk (str | None): Bezirk filtern
            - response_format: 'markdown' oder 'json'

    Returns:
        str: Maturitätsquoten-Tabelle mit Abschlüssen und Quote pro Gemeinde.
    """
    try:
        rows = await _fetch_csv(EP_MATURITAET)

        filtered = rows
        if params.gemeinde:
            filtered = _filter_rows(filtered, Gemeinde=params.gemeinde)
        if params.bezirk:
            filtered = _filter_rows(filtered, Bezirk=params.bezirk)

        if not filtered:
            return "Keine Daten für die angegebenen Filter gefunden."

        filtered.sort(key=lambda r: float(r.get("Maturitaetsquote_gymnasial", 0)), reverse=True)

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"daten": filtered}, ensure_ascii=False, indent=2)

        lines = ["# Gymnasiale Maturitätsquote Kanton Zürich\n"]
        if params.gemeinde:
            lines.append(f"**Filter Gemeinde:** *{params.gemeinde}*")
        if params.bezirk:
            lines.append(f"**Filter Bezirk:** *{params.bezirk}*")
        lines.append(f"\nGefunden: **{len(filtered)}** Gemeinden\n")

        lines.append("| Gemeinde | Bezirk | Abschlüsse | 19-Jährige | Quote |")
        lines.append("|----------|--------|----------:|-----------:|------:|")

        for r in filtered[:50]:
            gem = r.get("Gemeinde", "—")
            bez = r.get("Bezirk", "—")
            abschl = r.get("Total_Abschluss_gymnasial", "—")
            pop = r.get("Total_19_Jahre_alt", "—")
            quote = r.get("Maturitaetsquote_gymnasial", "—")
            try:
                quote_str = f"{float(quote) * 100:.1f}%" if quote != "—" else "—"
            except (ValueError, TypeError):
                quote_str = f"{quote}%"
            lines.append(f"| {gem} | {bez} | {abschl} | {pop} | {quote_str} |")

        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


# ══════════════════════════════════════════════════════════════════════════════
#  TOOL 7 — Wohnort-Trend
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool(
    name="zh_edu_wohnort_trend",
    annotations={
        "title": "Lernenden-Trend nach Wohnort",
        "readOnlyHint":    True,
        "destructiveHint": False,
        "idempotentHint":  True,
        "openWorldHint":   True,
    },
)
async def zh_edu_wohnort_trend(params: WohnortTrendInput) -> str:
    """Zeigt die Entwicklung der Lernendenzahlen nach Wohnort (Bezirk/Gemeinde).

    Basiert auf dem Wohnort der Lernenden, nicht dem Schulort.
    Aufschlüsselung nach Gebietstyp (Kanton, Bezirk, Gemeinde) und Schulstufe.

    Args:
        params (WohnortTrendInput):
            - gebiet (str | None): Gebietsbezeichnung filtern
            - stufe (str | None): Schulstufe filtern
            - letzte_n_jahre (int): Anzahl Jahre (Standard: 5)
            - response_format: 'markdown' oder 'json'

    Returns:
        str: Trend-Tabelle der Lernenden nach Wohnort und Stufe.
    """
    try:
        rows = await _fetch_csv(EP_WOHNORT)

        filtered = rows
        if params.gebiet:
            filtered = _filter_rows(filtered, Gebiet_Bezeichnung=params.gebiet)
        if params.stufe:
            filtered = _filter_rows(filtered, Stufe=params.stufe)

        if not filtered:
            return "Keine Daten für die angegebenen Filter gefunden."

        latest = _latest_year(filtered)
        if latest is None:
            return "Keine Jahresdaten verfügbar."

        cutoff = latest - params.letzte_n_jahre + 1
        filtered = [r for r in filtered if r.get("Jahr", "").isdigit() and int(r["Jahr"]) >= cutoff]

        if not filtered:
            return f"Keine Daten im Zeitraum {cutoff}–{latest} gefunden."

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"daten": filtered}, ensure_ascii=False, indent=2)

        lines = [f"# Lernende nach Wohnort ({cutoff}–{latest})\n"]
        if params.gebiet:
            lines.append(f"**Filter Gebiet:** *{params.gebiet}*")
        if params.stufe:
            lines.append(f"**Filter Stufe:** *{params.stufe}*")

        by_year: dict[int, int] = {}
        for r in filtered:
            yr = int(r["Jahr"])
            by_year[yr] = by_year.get(yr, 0) + int(r.get("Anzahl", 0))

        lines.append("\n| Jahr | Lernende |")
        lines.append("|------|--------:|")
        for yr in sorted(by_year):
            lines.append(f"| {yr} | {by_year[yr]:,} |")

        years_list = sorted(by_year.keys())
        if len(years_list) >= 2:
            diff = by_year[years_list[-1]] - by_year[years_list[0]]
            sign = "+" if diff >= 0 else ""
            lines.append(
                f"\n**Veränderung {years_list[0]}→{years_list[-1]}:** {sign}{diff} Lernende"
            )

        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


# ══════════════════════════════════════════════════════════════════════════════
#  TOOL 8 — Mittelschulen
# ══════════════════════════════════════════════════════════════════════════════

@mcp.tool(
    name="zh_edu_mittelschulen",
    annotations={
        "title": "Mittelschulstatistiken",
        "readOnlyHint":    True,
        "destructiveHint": False,
        "idempotentHint":  True,
        "openWorldHint":   True,
    },
)
async def zh_edu_mittelschulen(params: MittelschulenInput) -> str:
    """Zeigt Statistiken zu Mittelschulen (Gymnasium, FMS, HMS) im Kanton Zürich.

    Umfasst Lernendenzahlen nach Mittelschultyp, Bildungsart, Geschlecht
    und Staatsangehörigkeit.

    Args:
        params (MittelschulenInput):
            - mittelschultyp (str | None): Schultyp filtern (z. B. 'Gymnasium')
            - jahr (int | None): Bestimmtes Jahr (leer = aktuellstes)
            - response_format: 'markdown' oder 'json'

    Returns:
        str: Mittelschulstatistiken nach Typ und Bildungsart.
    """
    try:
        rows = await _fetch_csv(EP_MITTELSCHULEN)

        jahr = params.jahr or _latest_year(rows)
        if jahr is None:
            return "Keine Jahresdaten verfügbar."

        filtered = [r for r in rows if r.get("Jahr") == str(jahr)]
        if params.mittelschultyp:
            filtered = _filter_rows(filtered, Mittelschultyp=params.mittelschultyp)

        if not filtered:
            return f"Keine Mittelschuldaten für Jahr {jahr} gefunden."

        if params.response_format == ResponseFormat.JSON:
            return json.dumps({"jahr": jahr, "daten": filtered}, ensure_ascii=False, indent=2)

        lines = [f"# Mittelschulen Kanton Zürich — {jahr}\n"]
        if params.mittelschultyp:
            lines.append(f"**Filter:** *{params.mittelschultyp}*\n")

        by_typ: dict[str, int] = {}
        for r in filtered:
            typ = r.get("Mittelschultyp", "Unbekannt")
            by_typ[typ] = by_typ.get(typ, 0) + int(r.get("Anzahl", 0))

        lines.append("| Mittelschultyp | Lernende |")
        lines.append("|----------------|--------:|")
        total = 0
        for typ in sorted(by_typ):
            lines.append(f"| {typ} | {by_typ[typ]:,} |")
            total += by_typ[typ]
        lines.append(f"| **Total** | **{total:,}** |")

        return "\n".join(lines)

    except Exception as e:
        return _handle_error(e)


# ─────────────────────────── Einstiegspunkt ────────────────────────────────────
if __name__ == "__main__":
    transport = "stdio"
    port = 8000

    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--http":
            transport = "streamable-http"
        elif arg == "--port" and i < len(sys.argv) - 1:
            port = int(sys.argv[i + 1])

    if transport == "streamable-http":
        mcp.run(transport=transport, port=port)
    else:
        mcp.run(transport=transport)
