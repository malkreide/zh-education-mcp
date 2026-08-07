#!/usr/bin/env python3
"""Zeichnet die Unit-Test-Fixtures von der echten BISTA-Quelle auf.

    python scripts/record_fixtures.py

WARUM ES DIESES SKRIPT GIBT. Ein handgeschriebener Mock kodiert die Annahme
seines Autors und kann sie deshalb prinzipiell nicht widerlegen: Produktivcode
und Fixture stammen aus demselben Kopf, zur selben Stunde, aus derselben
Lektuere der Dokumentation. Wo beide irren, irren beide gleich, und die Suite
bleibt dauerhaft gruen.

Genau das ist hier passiert. Am 3. August 2026 hat BISTA die Schreibweise der
Kopfzeile gewechselt und liefert bei kleinen Fallzahlen «1 bis 5» statt einer
Zahl — die Fixtures pinnten die alte Kopfzeile und die alten Zellwerte, blieben
gruen, und der Server fand gegen die echte Quelle nichts mehr. Kein Test war
falsch geschrieben. Die Fixture war alt, und das war ihr nicht anzusehen.

Deshalb liegt der Abruf als Skript daneben und nicht als Handgriff im
Gedaechtnis: So kostet das naechste Aufzeichnungsdatum einen Lauf statt einer
Rekonstruktion. Erzeugt werden `tests/fixtures/*.csv` und die
`tests/fixtures/PROVENANCE.md`, die Endpunkt, Datum, Auswahlregel, Zeilenzahl
und SHA-256 je Datei festhaelt.

Der Auswahlfilter liest die Spaltennamen **schreibweise-unabhaengig** — er muss
es, denn die sechs Endpunkte schreiben ihre Kopfzeilen uneinheitlich und zwei
mischen die Schreibweise innerhalb einer Zeile (`gebiet_Bezeichnung`,
`staatsangehoerigkeit_ISO2_Code`). Eine Schreibweise fest zu verdrahten haette
hier beim naechsten Wechsel dasselbe Loch gerissen.
"""

from __future__ import annotations

import csv
import hashlib
import io
import sys
from datetime import UTC, datetime
from pathlib import Path

import httpx

BISTA_API = "https://www.bista.zh.ch/basicapi/ogd"
FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def _get(row: dict, key: str) -> str:
    """Ein Feld, unabhaengig davon, wie die Quelle es heute schreibt."""
    lowered = {(k or "").lower(): v for k, v in row.items()}
    return str(lowered.get(key.lower(), "") or "")


def _latest_year(rows: list[dict]) -> str:
    years = {_get(r, "jahr") for r in rows}
    return max(y for y in years if y.isdigit())


# Jede Auswahlregel ist klein, deterministisch und in PROVENANCE.md nachlesbar.
# Klein, weil eine Fixture gelesen werden koennen muss; deterministisch, weil
# ein Diff sonst bei jedem Lauf rauscht und niemand mehr hinsieht.
RECIPES = [
    (
        "sek1",
        "data_lernende_sekundarstufe_i_anforderungstyp",
        "alle Zeilen zu den Schulgemeinden Zuerich-Letzi und Adliswil",
        lambda rows: [r for r in rows if _get(r, "schulgemeinde") in {"Zürich-Letzi", "Adliswil"}],
    ),
    (
        "uebersicht",
        "data_uebersicht_alle_lernende",
        "alle Zeilen des juengsten Jahrgangs",
        lambda rows: [r for r in rows if _get(r, "jahr") == _latest_year(rows)],
    ),
    (
        "nat_regional",
        "data_lernende_regelschule_regional_staatsangehoerigkeit",
        "Schulgemeinde Zuerich-Letzi, juengster Jahrgang",
        lambda rows: [
            r
            for r in rows
            if _get(r, "schulgemeinde") == "Zürich-Letzi" and _get(r, "jahr") == _latest_year(rows)
        ],
    ),
    (
        "maturitaet",
        "data_maturitaetsquote_gemeinden_und_kanton",
        "Gemeinden Zuerich und Winterthur",
        lambda rows: [r for r in rows if _get(r, "gemeinde") in {"Zürich", "Winterthur"}],
    ),
    (
        "wohnort",
        "data_lernende_nach_wohngemeinde",
        "Gebiet «Bezirk Winterthur», alle Jahre",
        lambda rows: [r for r in rows if _get(r, "gebiet_Bezeichnung") == "Bezirk Winterthur"],
    ),
    (
        "mittelschulen",
        "data_lernende_mittelschulen",
        "alle Zeilen des juengsten Jahrgangs",
        lambda rows: [r for r in rows if _get(r, "jahr") == _latest_year(rows)],
    ),
]


def record() -> int:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    recorded_at = datetime.now(UTC).strftime("%Y-%m-%d")
    entries = []

    with httpx.Client(timeout=90.0, follow_redirects=True) as client:
        for name, endpoint, rule, select in RECIPES:
            url = f"{BISTA_API}/{endpoint}"
            resp = client.get(url)
            resp.raise_for_status()

            reader = csv.DictReader(io.StringIO(resp.text))
            header = reader.fieldnames or []
            if not header:
                print(f"FEHLER {name}: Antwort ohne Kopfzeile", file=sys.stderr)
                return 1
            all_rows = list(reader)
            rows = select(all_rows)
            if not rows:
                # Laut scheitern statt eine leere Fixture zu schreiben: Eine
                # Auswahlregel, die nichts mehr trifft, ist selbst der Befund.
                print(
                    f"FEHLER {name}: Auswahl «{rule}» trifft 0 von "
                    f"{len(all_rows)} Zeilen — Regel oder Quelle geaendert",
                    file=sys.stderr,
                )
                return 1

            buffer = io.StringIO(newline="")
            writer = csv.DictWriter(buffer, fieldnames=header, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
            text = buffer.getvalue()

            path = FIXTURES / f"{name}.csv"
            path.write_text(text, encoding="utf-8")

            digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
            entries.append(
                {
                    "name": name,
                    "url": url,
                    "rule": rule,
                    "rows": len(rows),
                    "of": len(all_rows),
                    "header": ",".join(header),
                    "sha256": digest,
                }
            )
            print(f"ok  {name:<14} {len(rows):>5} von {len(all_rows):>6} Zeilen")

    _write_provenance(recorded_at, entries)
    print(f"\nPROVENANCE.md geschrieben, Aufzeichnungsdatum {recorded_at}")
    return 0


def _write_provenance(recorded_at: str, entries: list[dict]) -> None:
    lines = [
        "# Herkunft der Fixtures",
        "",
        "**Erzeugt von `scripts/record_fixtures.py`. Nicht von Hand pflegen.**",
        "",
        f"Aufgezeichnet am **{recorded_at}** von der Live-Quelle "
        f"`{BISTA_API}`, unveraendert bis auf die dokumentierte Zeilenauswahl.",
        "",
        "Ohne Datum ist «aufgezeichnet» nach zwei Jahren von «ausgedacht» nicht",
        "mehr zu unterscheiden — die Datei sieht gleich aus, und niemand weiss,",
        "ob sie den Stand von gestern zeigt oder den von vor drei",
        "Schema-Wechseln. Das Datum macht diesen Abstand zu einer lesbaren Zahl.",
        "",
        "Die Kopfzeilen stehen absichtlich **so, wie die Quelle sie an diesem",
        "Tag geschrieben hat**, inklusive der uneinheitlichen Schreibweise",
        "zwischen den Endpunkten und innerhalb einzelner Zeilen. Sie zu",
        "vereinheitlichen wuerde genau die Eigenschaft wegputzen, an der der",
        "Server am 3.8.2026 gescheitert ist.",
        "",
    ]
    for e in entries:
        lines += [
            f"## `{e['name']}.csv`",
            "",
            f"- **Endpunkt:** `{e['url']}`",
            f"- **Aufgezeichnet:** {recorded_at}",
            f"- **Auswahl:** {e['rule']} — {e['rows']} von {e['of']} Zeilen",
            f"- **Kopfzeile:** `{e['header']}`",
            f"- **SHA-256:** `{e['sha256']}`",
            "",
        ]
    (FIXTURES / "PROVENANCE.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(record())
