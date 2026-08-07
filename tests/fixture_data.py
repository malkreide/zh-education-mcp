"""Zugriff auf die aufgezeichneten Fixtures unter ``tests/fixtures/``.

Die Dateien dort sind **aufgezeichnet, nicht ausgedacht**: Herkunft, Datum,
Auswahlregel und SHA-256 stehen in ``tests/fixtures/PROVENANCE.md``, erzeugt
von ``scripts/record_fixtures.py``. Vorher standen hier CSV-Literale mit
runden Phantasiezahlen — die haben am 3.8.2026 dafuer gesorgt, dass die Suite
gruen blieb, waehrend der Server gegen die echte Quelle nichts mehr fand.

Ein fehlender Name ist ein Fehler und keine leere Zeichenkette. Der
Rueckfallwert eines Lookups ist sonst die ganze Ursache: Ein Test gegen eine
leere Fixture prueft nichts und meldet Erfolg.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def csv_fixture(name: str) -> str:
    """Der aufgezeichnete CSV-Text zu ``name``, unveraendert."""
    path = FIXTURES / f"{name}.csv"
    if not path.is_file():
        available = sorted(p.stem for p in FIXTURES.glob("*.csv"))
        raise FileNotFoundError(
            f"Keine Fixture {name!r} unter {FIXTURES}. Vorhanden: {available}. "
            "Neu aufzeichnen mit `python scripts/record_fixtures.py`."
        )
    return path.read_text(encoding="utf-8")


def latest_year(name: str) -> str:
    """Der juengste Jahrgang **in der Fixture**, abgeleitet statt hingeschrieben.

    Ein Test, der «2024» hartcodiert und dabei behauptet, das aktuellste Jahr
    zu pruefen, prueft ab dem naechsten Jahrgang etwas anderes als sein Name
    sagt — und faellt dann aus einem Grund um, der mit dem Pruefgegenstand
    nichts zu tun hat. Beim Aufzeichnen ist genau das passiert: Die Quelle
    stand auf 2025, die Zusicherung auf 2024.

    Die Spalte wird schreibweise-unabhaengig gesucht: Von den sechs Endpunkten
    schreibt die eine Haelfte `jahr`, die andere `Jahr`.
    """
    reader = csv.DictReader(io.StringIO(csv_fixture(name)))
    years = set()
    for row in reader:
        lowered = {(k or "").lower(): v for k, v in row.items()}
        value = str(lowered.get("jahr", "") or "").strip()
        if value.isdigit():
            years.add(value)
    if not years:
        raise AssertionError(
            f"Fixture {name!r} fuehrt keine Jahresspalte — Auswahlregel oder "
            "Quelle geaendert, siehe tests/fixtures/PROVENANCE.md"
        )
    return max(years)
