"""Daten-Zugriff: Cache, CSV-Fetch, Filter-/Jahr-Helfer und Fehler-Sanitisierung."""

from __future__ import annotations

import csv
import io
import time

import httpx

from .constants import BISTA_API, CACHE_TTL
from .http_client import UpstreamUnresolvable, _http_get
from .logging_setup import log

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


def _handle_error(e: Exception) -> str:
    """Einheitliche, handlungsorientierte Fehlermeldungen (auf Deutsch).

    Der **originale** Fehler wird strukturiert ins stderr-Log geschrieben
    (OBS-002); an den LLM/Client geht ausschliesslich eine sanitisierte
    Meldung ohne Internals (keine Stacktraces, keine ``str(e)``-Leaks).
    """
    log.error("tool_error", error_type=type(e).__name__, error=str(e))

    if isinstance(e, httpx.HTTPStatusError):
        code = e.response.status_code
        if code == 404:
            return "Fehler: Ressource nicht gefunden. Bitte Parameter prüfen."
        if code == 429:
            return "Fehler: Rate-Limit erreicht. Bitte kurz warten und erneut versuchen."
        if code in (502, 503):
            return "Fehler: Dienst vorübergehend nicht verfügbar. Bitte erneut versuchen."
        return f"Fehler: API-Anfrage fehlgeschlagen (HTTP {code})."
    # ``TimeoutError`` (builtin) kommt aus dem Gesamtbudget der Retry-Schleife,
    # ``httpx.TimeoutException`` aus einer einzelnen Operation. Für den Aufrufer
    # ist beides dasselbe: Es hat zu lange gedauert. Ohne den builtin-Fall fiele
    # ein aufgebrauchtes Budget in den Zweig «unerwarteter interner Fehler».
    if isinstance(e, httpx.TimeoutException | TimeoutError):
        return "Fehler: Zeitüberschreitung. Der Dienst antwortet nicht. Bitte erneut versuchen."
    # Reihenfolge ist hier die Aussage: ``UpstreamUnresolvable`` **ist** ein
    # ``PermissionError`` (gemeinsame Basis, damit bestehende Handler weiter
    # greifen). Stünde der Egress-Zweig zuerst, verschluckte er den
    # Auflöser-Ausfall wieder und schickte Nutzende in die Egress-Konfiguration,
    # wo bei einem DNS-Aussetzer nichts zu finden ist.
    if isinstance(e, UpstreamUnresolvable):
        return (
            "Fehler: Die Adresse der Datenquelle liess sich gerade nicht auflösen (DNS). "
            "Das ist meist vorübergehend — bitte erneut versuchen."
        )
    if isinstance(e, PermissionError):
        return "Fehler: Ausgehende Anfrage durch Egress-Policy blockiert."
    return "Fehler: Unerwarteter interner Fehler. Bitte später erneut versuchen."


def _normalise_keys(row: dict) -> dict:
    """Senkt die Spaltennamen einer CSV-Zeile auf Kleinschreibung.

    BISTA schreibt die Kopfzeile nicht einheitlich, und die Schreibweise hat
    sich bereits geändert: Am 3. August 2026 lieferten vier der sechs genutzten
    Datensätze `schulgemeinde`, zwei `Schulgemeinde` — und zwei mischten sogar
    innerhalb einer Kopfzeile (`gebiet_Bezeichnung`,
    `staatsangehoerigkeit_ISO2_Code`).

    Der Code hatte die Grossschreibung fest verdrahtet und fand danach nichts
    mehr: `r["Schulgemeinde"]` gegen eine Zeile mit `schulgemeinde` ergibt
    keinen Treffer, sondern ein leeres Ergebnis mit der Meldung «nicht
    gefunden» — ein Ausfall, der wie eine Antwort aussieht.

    Hier zu normalisieren ist der einzige Ort, an dem es einmal geschehen muss,
    und macht den Rest des Codes gegen den nächsten Wechsel unempfindlich. Die
    Alternative — auf die neue Schreibweise umstellen — hätte beim nächsten
    Rückwechsel dasselbe Loch gerissen.
    """
    return {(k or "").lower(): v for k, v in row.items()}


async def _fetch_csv(endpoint: str, ctx: object | None = None) -> list[dict]:
    """Holt CSV-Daten von einem BISTA-Endpunkt und gibt eine Liste von Dicts zurück.

    Optionaler ``ctx`` (MCPServer Context) erlaubt Progress-Reports und
    client-seitiges Logging bei nicht-gecachten Fetches (SDK-003).
    """
    cached = _cache_get(endpoint)
    if cached is not None:
        log.debug("cache_hit", endpoint=endpoint, rows=len(cached))
        if ctx is not None:
            await ctx.info(f"Cache-Treffer für {endpoint} ({len(cached)} Zeilen).")
        return cached

    start = time.perf_counter()
    if ctx is not None:
        await ctx.info(f"Lade BISTA-Datensatz {endpoint} …")
        await ctx.report_progress(0.0, 1.0, "Abruf gestartet")
    resp = await _http_get(f"{BISTA_API}/{endpoint}")
    resp.raise_for_status()
    reader = csv.DictReader(io.StringIO(resp.text))
    rows = [_normalise_keys(row) for row in reader]
    _cache_set(endpoint, rows)
    ms = round((time.perf_counter() - start) * 1000)
    log.info("fetch_ok", endpoint=endpoint, rows=len(rows), ms=ms)
    if ctx is not None:
        await ctx.report_progress(1.0, 1.0, f"{len(rows)} Zeilen geladen")
    return rows


def _filter_rows(rows: list[dict], **filters: str | int | None) -> list[dict]:
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


def _parse_count(value: object) -> int | None:
    """Zahl aus einem BISTA-Zählwert, oder ``None``, wenn keine da ist.

    BISTA unterdrückt kleine Fallzahlen aus Datenschutzgründen und schreibt
    statt einer Zahl einen Bereich: ``1 bis 5``. Dazu kommt ``NULL`` und die
    leere Zelle. Am 3. August 2026 waren das 18.6 % der Sek-I-Zeilen und
    18.1 % der Staatsangehörigkeits-Zeilen — kein Randfall.

    ``int("1 bis 5")`` wirft, und der Aufrufer sah davon nur «unerwarteter
    interner Fehler». Sie als 0 zu zählen wäre schlimmer: Die Summe wäre
    plausibel, still zu tief und durch nichts als falsch erkennbar. Deshalb
    ``None`` — der Aufrufer entscheidet, und die Tools weisen die Zahl der
    unterdrückten Zeilen aus, statt sie verschwinden zu lassen (FID-003).
    """
    raw = str(value if value is not None else "").strip()
    return int(raw) if raw.isdigit() else None


def _suppression_note(suppressed: int, total: int) -> str | None:
    """Hinweiszeile auf unterdrückte Werte, oder ``None``, wenn es keine gibt.

    Eine Summe, aus der ein Fünftel der Zeilen stillschweigend fehlt, ist keine
    Summe — sie ist eine Untergrenze, die sich als Summe ausgibt.
    """
    if suppressed <= 0:
        return None
    return (
        f"\n> **Hinweis:** {suppressed} von {total} Zeilen enthalten keinen Zahlenwert "
        f"(BISTA schreibt bei kleinen Fallzahlen «1 bis 5» statt einer Zahl). "
        f"Sie sind in den Summen **nicht** enthalten; die echten Werte liegen "
        f"entsprechend höher."
    )


def _latest_year(rows: list[dict], year_field: str = "jahr") -> int | None:
    """Ermittelt das aktuellste Jahr aus den Daten."""
    years = {int(r[year_field]) for r in rows if r.get(year_field, "").isdigit()}
    return max(years) if years else None
