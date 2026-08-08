"""Schema- und Werte-Drift bei BISTA (DRIFT).

Beide Befunde stammen aus einem Live-Lauf am 3. August 2026 und waren für die
Unit-Tests unsichtbar: Die Fixtures pinnten die alte Kopfzeile und die alten
Zellwerte, also blieben sie grün, während der Server gegen die echte Quelle
nichts mehr fand.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from zh_education_mcp.constants import BISTA_API, EP_SEK1
from zh_education_mcp.data import _normalise_keys, _parse_count, _suppression_note

URL = f"{BISTA_API}/{EP_SEK1}"


@pytest.fixture(autouse=True)
def _stub_dns(request, monkeypatch):
    # Dieselbe Ausnahme wie in `test_server.py`, aus demselben Grund — hier
    # allerdings vorsorglich: Diese Datei hat heute keinen Live-Test. Der Stub
    # lenkt auf `8.8.8.8` um und wirkt prozessweit; ein Live-Test, der später
    # hier dazukäme, spräche mit Google statt mit BISTA und bekäme einen
    # Zertifikatsfehler, der wie ein Befund über die Quelle aussieht. Genau das
    # ist am 8.8.2026 in `test_server.py` passiert und hat drei Runden gekostet.
    if "live" in request.keywords:
        return

    import socket

    def fake_getaddrinfo(host, port, *a, **k):
        return [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("8.8.8.8", port))]

    monkeypatch.setattr("zh_education_mcp.http_client.socket.getaddrinfo", fake_getaddrinfo)


@pytest.fixture(autouse=True)
def _clear_cache():
    from zh_education_mcp.server import _cache

    _cache.clear()
    yield
    _cache.clear()


# --- Schema-Drift: die Kopfzeile wechselt die Schreibweise -------------------


class TestHeaderCase:
    def test_keys_are_lowercased(self):
        assert _normalise_keys({"Schulgemeinde": "x", "Jahr": "2025"}) == {
            "schulgemeinde": "x",
            "jahr": "2025",
        }

    def test_mixed_case_within_one_header_is_handled(self):
        """BISTA mischt innerhalb einer Kopfzeile: ``gebiet_Bezeichnung``."""
        got = _normalise_keys(
            {"gebiet_Bezeichnung": "Zürich", "staatsangehoerigkeit_ISO2_Code": "CH"}
        )
        assert got == {"gebiet_bezeichnung": "Zürich", "staatsangehoerigkeit_iso2_code": "CH"}

    def test_a_none_key_does_not_crash(self):
        """``csv.DictReader`` legt überzählige Felder unter ``None`` ab."""
        assert _normalise_keys({None: ["extra"], "Jahr": "2025"}) == {"": ["extra"], "jahr": "2025"}


LOWER_CSV = """stand,kanton,jahr,schulgemeinde,anforderungstyp,anzahl
2026-08-03,zh,2025,Zürich-Letzi,Sek A,500
2026-08-03,zh,2025,Zürich-Letzi,Sek B,300
"""

UPPER_CSV = """Stand,Kanton,Jahr,Schulgemeinde,Anforderungstyp,Anzahl
2026-08-03,zh,2025,Zürich-Letzi,Sek A,500
2026-08-03,zh,2025,Zürich-Letzi,Sek B,300
"""


@pytest.mark.parametrize("csv_text", [LOWER_CSV, UPPER_CSV], ids=["klein", "gross"])
@respx.mock
async def test_the_tool_works_under_either_header_case(csv_text):
    """Der eigentliche Ausfall: ``r["Schulgemeinde"]`` gegen ``schulgemeinde``.

    Der Zugriff ergab keinen Treffer, sondern ein leeres Ergebnis mit der
    Meldung «nicht gefunden» — ein Ausfall, der wie eine Antwort aussieht. Am
    3. August 2026 lieferten vier der sechs genutzten Datensätze Klein-, zwei
    Grossschreibung; beide müssen tragen.
    """
    from zh_education_mcp.server import Sek1ProfilInput, zh_edu_sek1_profil

    respx.get(URL).mock(return_value=httpx.Response(200, text=csv_text))
    result = await zh_edu_sek1_profil(Sek1ProfilInput(schulgemeinde="Zürich-Letzi"))
    assert "nicht gefunden" not in result
    assert "Sek A" in result


# --- Werte-Drift: unterdrückte Kleinstwerte ---------------------------------


class TestParseCount:
    @pytest.mark.parametrize("raw", ["1 bis 5", "NULL", "", "  ", "k. A.", None])
    def test_non_numeric_values_yield_none(self, raw):
        """``int("1 bis 5")`` wirft — und der Aufrufer sah nur «interner Fehler»."""
        assert _parse_count(raw) is None

    @pytest.mark.parametrize("raw,want", [("0", 0), ("42", 42), (" 7 ", 7), (13, 13)])
    def test_numeric_values_are_parsed(self, raw, want):
        assert _parse_count(raw) == want

    def test_a_suppressed_value_is_not_zero(self):
        """Der entscheidende Unterschied.

        Als 0 zu zählen wäre schlimmer als ein Absturz: Die Summe bliebe
        plausibel, wäre still zu tief und durch nichts als falsch erkennbar.
        """
        assert _parse_count("1 bis 5") is None
        assert _parse_count("0") == 0, "eine echte Null ist etwas anderes als keine Angabe"


SUPPRESSED_CSV = """stand,kanton,jahr,schulgemeinde,anforderungstyp,anzahl
2026-08-03,zh,2025,Winterthur,Sek A,500
2026-08-03,zh,2025,Winterthur,Sek B,1 bis 5
2026-08-03,zh,2025,Winterthur,Heim-/Sonderschulung,1 bis 5
"""


class TestSuppressionNote:
    def test_no_note_when_nothing_is_suppressed(self):
        assert _suppression_note(0, 100) is None

    def test_the_note_names_both_numbers(self):
        note = _suppression_note(3, 10)
        assert note is not None
        assert "3" in note and "10" in note

    @respx.mock
    async def test_a_suppressed_row_is_flagged_not_silently_dropped(self):
        """Eine Summe, aus der ein Fünftel der Zeilen fehlt, ist keine Summe.

        Sie ist eine Untergrenze, die sich als Summe ausgibt — genau die
        Datentreue-Verletzung, gegen die FID-003 steht. 18.6 % der Sek-I-Zeilen
        waren am 3. August 2026 betroffen.
        """
        from zh_education_mcp.server import Sek1ProfilInput, zh_edu_sek1_profil

        respx.get(URL).mock(return_value=httpx.Response(200, text=SUPPRESSED_CSV))
        result = await zh_edu_sek1_profil(Sek1ProfilInput(schulgemeinde="Winterthur"))

        assert "Hinweis:" in result, "unterdrückte Zeilen verschwinden lautlos"
        assert "2 von 3" in result
        assert "1 bis 5" in result, "der unterdrückte Wert wird als solcher gezeigt"

    @respx.mock
    async def test_a_suppressed_row_does_not_crash_the_tool(self):
        """Vor dem Fix: ValueError -> «Fehler: Unerwarteter interner Fehler»."""
        from zh_education_mcp.server import Sek1ProfilInput, zh_edu_sek1_profil

        respx.get(URL).mock(return_value=httpx.Response(200, text=SUPPRESSED_CSV))
        result = await zh_edu_sek1_profil(Sek1ProfilInput(schulgemeinde="Winterthur"))
        assert not result.startswith("Fehler")


# ── Die Maturitätsquote ist bereits eine Prozentzahl (FID-007-Nachbarschaft) ──


def test_die_maturitaetsquote_wird_nicht_ein_zweites_mal_mal_hundert_genommen():
    """Regression: `* 100` auf einer Spalte, die schon in Prozent steht.

    Gefunden beim Aufzeichnen der Fixtures, nicht beim Lesen des Codes. Die
    alte, erfundene Fixture schrieb `0.15` in `Maturitaetsquote_gymnasial` —
    eine Bruchzahl, die es in der Quelle nicht gibt. Mit `* 100` ergab das die
    plausiblen «15.0 %», und weil Produktivcode und Fixture denselben Irrtum
    trugen, konnte kein Test ihn widerlegen. Gegen die echte Quelle meldete
    das Tool «2290.0 %».

    Diese Zusicherung hält die Einheit fest, nicht die Zahl: Sie prüft, dass
    die ausgegebene Quote zu `Abschlüsse / 19-Jährige` passt — und das ist
    genau die Rechnung, welche die Quelle in dieser Spalte publiziert.
    """
    import csv
    import io

    from fixture_data import csv_fixture

    rows = list(csv.DictReader(io.StringIO(csv_fixture("maturitaet"))))
    assert rows, "Fixture leer — siehe tests/fixtures/PROVENANCE.md"

    for row in rows:
        lowered = {(k or "").lower(): v for k, v in row.items()}
        quote = float(lowered["maturitaetsquote_gymnasial"])
        abschluesse = float(lowered["total_abschluss_gymnasial"])
        neunzehnjaehrige = float(lowered["total_19_jahre_alt"])
        erwartet = abschluesse / neunzehnjaehrige * 100
        assert abs(quote - erwartet) < 0.05, (
            f"{lowered['gemeinde']}: Spalte sagt {quote}, "
            f"{abschluesse}/{neunzehnjaehrige} ergibt {erwartet:.2f} — "
            "die Spalte ist keine Prozentzahl mehr, Einheit upstream geändert"
        )
        assert quote <= 100.0, f"Quote über 100 %: {quote}"
