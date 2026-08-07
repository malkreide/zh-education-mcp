"""Die gelesenen Feldnamen werden bestätigt — auch gegen die echte Antwort.

`_normalise_keys` nimmt die **Schreibweise** aus dem Spiel. Das war die Lehre
vom 3. August 2026, als BISTA `Schulgemeinde` auf `schulgemeinde` wechselte und
der Server nichts mehr fand.

Es nimmt die **Identität** nicht aus dem Spiel. Wechselt die Quelle einen
Feldnamen — `anzahl` zu `wert`, `schulgemeinde` zu `gemeinde` —, hilft keine
Normalisierung, und der Ausfall sähe genauso aus: ein leeres Ergebnis mit der
Meldung «nicht gefunden». Ein Ausfall, der wie eine Antwort aussieht.

Diese Datei schliesst beide Hälften von `FID-006` ab:

* `_confirm_shape` bestätigt die gelesenen Felder auf dem ersten Eintrag und
  wirft sonst `UpstreamSchemaError` mit den tatsächlich vorhandenen Spalten.
* `test_live_*` hält dieselbe Erklärung gegen die **echte** Antwort aller sechs
  Endpunkte. Ein Fixture kann diese Klasse nicht widerlegen: Es trägt die
  angenommene Kopfzeile und bestätigt sie dauerhaft.

Der Live-Test läuft nicht in der CI (`-m "not live"`), sondern im wöchentlichen
Live-Workflow — `DRIFT-005` ist der Check, der dafür sorgt, dass er auch
wirklich läuft.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path

import httpx
import pytest
import respx

from zh_education_mcp.constants import (
    BISTA_API,
    EP_MATURITAET,
    EP_MITTELSCHULEN,
    EP_NAT_REGIONAL,
    EP_SEK1,
    EP_UEBERSICHT,
    EP_WOHNORT,
)
from zh_education_mcp.data import (
    _READ_FIELDS,
    UpstreamSchemaError,
    _confirm_shape,
    _fetch_csv,
    _normalise_keys,
)

FIXTURES = Path(__file__).parent / "fixtures"

# Welche aufgezeichnete Datei zu welchem Endpunkt gehoert.
FIXTURE_FOR = {
    EP_SEK1: "sek1.csv",
    EP_UEBERSICHT: "uebersicht.csv",
    EP_NAT_REGIONAL: "nat_regional.csv",
    EP_MATURITAET: "maturitaet.csv",
    EP_WOHNORT: "wohnort.csv",
    EP_MITTELSCHULEN: "mittelschulen.csv",
}


def _recorded_rows(endpoint: str) -> list[dict]:
    text = (FIXTURES / FIXTURE_FOR[endpoint]).read_text(encoding="utf-8")
    return [_normalise_keys(r) for r in csv.DictReader(io.StringIO(text))]


# --- Die Erklaerung selbst ---------------------------------------------------


def test_every_endpoint_declares_what_it_reads():
    """Ein Endpunkt ohne Erklaerung wird stillschweigend nicht geprueft.

    `_confirm_shape` kehrt bei einem unbekannten Endpunkt wortlos zurueck —
    richtig, damit ein neuer Endpunkt nicht sofort rot wird, aber eben auch
    ungeprueft. Dieser Test ist der Grund, warum das auffaellt.
    """
    assert set(_READ_FIELDS) == set(FIXTURE_FOR), (
        "jeder genutzte BISTA-Endpunkt braucht eine Feldliste in `_READ_FIELDS`"
    )


@pytest.mark.parametrize("endpoint", sorted(FIXTURE_FOR))
def test_every_declared_field_exists_in_its_fixture(endpoint):
    """Die Bruecke zwischen Erklaerung und aufgezeichneter Wirklichkeit.

    Die Feldlisten sind aus dem Quelltext erhoben. Ohne diesen Test koennte ein
    Tippfehler darin unbemerkt bleiben: `_confirm_shape` wuerde dann bei **jeder**
    Antwort werfen, und zwar auf dem Fehlerpfad, wo es niemand erwartet.
    """
    rows = _recorded_rows(endpoint)
    assert rows, f"{FIXTURE_FOR[endpoint]} enthaelt keine Zeilen"
    missing = sorted(_READ_FIELDS[endpoint] - set(rows[0]))
    assert not missing, f"{endpoint}: {missing} steht in `_READ_FIELDS`, aber nicht in der Aufnahme"


@pytest.mark.parametrize("endpoint", sorted(FIXTURE_FOR))
def test_the_recorded_shape_passes_the_confirmation(endpoint):
    """Die Gegenrichtung: die echte Kopfzeile von 2026-08-07 geht durch."""
    _confirm_shape(endpoint, _recorded_rows(endpoint))


# --- Was die Bestaetigung faengt ---------------------------------------------


def test_a_renamed_field_is_rejected():
    """Der Fall, den die Normalisierung NICHT abdeckt.

    `anzahl` zu `wert` umbenannt: jede Schreibweise waere weiterhin korrekt
    gesenkt, und der Server faende trotzdem nichts.
    """
    rows = [
        {"jahr": "2025", "schulgemeinde": "Zürich-Letzi", "anforderungstyp": "Sek A", "wert": "7"}
    ]
    with pytest.raises(UpstreamSchemaError) as excinfo:
        _confirm_shape(EP_SEK1, rows)
    assert "anzahl" in str(excinfo.value)


def test_the_message_names_the_columns_that_are_actually_there():
    """Ohne die vorhandenen Spalten ist der naechste Schritt Raten."""
    rows = [{"jahr": "2025", "gemeinde": "Zürich", "wert": "7"}]
    with pytest.raises(UpstreamSchemaError) as excinfo:
        _confirm_shape(EP_SEK1, rows)
    message = str(excinfo.value)
    assert "'gemeinde'" in message and "'wert'" in message, message
    assert "keine Leermenge" in message
    assert EP_SEK1 in message


def test_an_empty_file_is_not_a_shape_finding():
    """Eine Datei ohne Zeilen sagt nichts ueber die Form.

    Sie kann eine Aussage der Quelle sein; `FID-003` behandelt sie an der
    richtigen Stelle. Ein Waechter, der sie mitfaengt, wird abgeschaltet.
    """
    _confirm_shape(EP_SEK1, [])


def test_extra_columns_are_not_a_finding():
    """Keine Schema-Validierung.

    Eine neue Spalte upstream ist harmlos. Ein Waechter, der dabei rot wird,
    ist nach dem zweiten Fehlalarm aus, und dann bewacht er gar nichts.
    """
    rows = [dict(_recorded_rows(EP_SEK1)[0], neue_spalte_von_bista="x")]
    _confirm_shape(EP_SEK1, rows)


# --- Am Abrufpfad, nicht nur am Helfer ---------------------------------------


@respx.mock
@pytest.mark.asyncio
async def test_the_fetch_path_confirms_the_shape(monkeypatch):
    """Der Helfer muss am Abruf haengen, sonst ist er Dekoration."""
    import socket

    monkeypatch.setattr(
        "zh_education_mcp.http_client.socket.getaddrinfo",
        lambda *a, **k: [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", 443))
        ],
    )
    from zh_education_mcp import data as data_mod

    data_mod._cache.clear()
    respx.get(f"{BISTA_API}/{EP_SEK1}").mock(
        return_value=httpx.Response(200, text="jahr,schulgemeinde,wert\n2025,Letzi,7\n")
    )
    with pytest.raises(UpstreamSchemaError):
        await _fetch_csv(EP_SEK1)


# --- Gegen die ECHTE Antwort -------------------------------------------------


@pytest.mark.live
@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", sorted(FIXTURE_FOR))
async def test_live_the_fields_we_read_are_the_fields_that_arrive(endpoint):
    """Contract-Canary auf der Ebene der Feldnamen — pro Endpunkt.

    Das ist der Test, den ein Fixture prinzipiell nicht ersetzen kann: Der Mock
    traegt die angenommene Kopfzeile und bestaetigt sie dauerhaft. Nur dieser
    Lauf kann widerlegen, dass die Erklaerung noch stimmt.
    """
    from zh_education_mcp import data as data_mod

    data_mod._cache.clear()
    rows = await _fetch_csv(endpoint)  # wirft UpstreamSchemaError bei Abweichung
    assert rows, f"{endpoint}: leer — hier waere schon das der Befund"
    assert _READ_FIELDS[endpoint] <= set(rows[0]), sorted(rows[0])


@pytest.mark.live
@pytest.mark.asyncio
@pytest.mark.parametrize("endpoint", sorted(FIXTURE_FOR))
async def test_live_the_recording_still_matches_the_source(endpoint):
    """Und ob die Aufnahme noch die Wirklichkeit trifft.

    Verglichen werden die **Spaltennamen**, nicht die Werte: Die Zahlen aendern
    sich bei jeder Erhebung, die Kopfzeile soll es nicht. Laeuft dieser Test
    rot, ist nicht der Server kaputt — dann ist die Fixture alt, und `OPS-009`
    sagt, was zu tun ist: neu aufzeichnen, mit Datum.
    """
    from zh_education_mcp import data as data_mod

    data_mod._cache.clear()
    live = await _fetch_csv(endpoint)
    recorded = _recorded_rows(endpoint)
    assert set(recorded[0]) == set(live[0]), (
        f"{endpoint}: Aufnahme vom PROVENANCE-Datum und Quelle unterscheiden sich. "
        f"Nur in der Aufnahme: {sorted(set(recorded[0]) - set(live[0]))}; "
        f"nur live: {sorted(set(live[0]) - set(recorded[0]))}"
    )
