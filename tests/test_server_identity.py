"""Woher die Server-Identitaet kommt — und woher nicht.

`tests/test_modern_protocol.py` prueft, dass die Identitaet auf dem Draht
ankommt. Diese Datei prueft die andere Haelfte: dass ihre Werte aus
`pyproject.toml` stammen und nicht aus Literalen, die neben der Wahrheit
altern.

Das ist im Portfolio kein hypothetischer Schaden. `scripts/check_version_sync.py`
existiert, weil mehrere Server einen User-Agent mit einer Version sendeten, die
es seit Releases nicht mehr gab; `bag-epl-mcp` meldete Aufrufern eine
Protokoll-Revision, die es nicht sprach. Beides waren Literale, die einmal
richtig waren.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as distribution_version

import pytest
from mcp import Client

from zh_education_mcp import identity
from zh_education_mcp.identity import (
    SERVER_DESCRIPTION,
    SERVER_INSTRUCTIONS,
    SERVER_NAME,
    SERVER_TITLE,
    SERVER_VERSION,
    SERVER_WEBSITE_URL,
)


def test_die_version_ist_die_der_installierten_distribution() -> None:
    """Nicht «irgendeine Version», sondern die ausgelieferte.

    `scripts/check_version_sync.py` verbietet ein Literal in `src/` und haelt
    `pyproject.toml` gegen `server.json` und die README-Badges. Es prueft aber
    nicht, dass der Server die Nummer auch BENUTZT — ein `version=`, das nie
    gesetzt wird, ist dort unauffaellig. Genau diese Luecke schliesst die Zeile.
    """
    assert SERVER_VERSION == distribution_version("zh-education-mcp")


def test_beschreibung_und_website_stammen_aus_den_paket_metadaten() -> None:
    """Zwei Felder, zwei Quellen in `pyproject.toml` — keine Abschrift.

    Faellt der Test, hat jemand ein Literal eingesetzt, oder `pyproject.toml`
    wurde geaendert, ohne dass die Installation nachgezogen wurde. Beides ist
    einen Blick wert.
    """
    from importlib.metadata import metadata

    meta = metadata("zh-education-mcp")
    assert SERVER_DESCRIPTION == meta.get("Summary")
    urls = dict(
        (label.strip(), url.strip())
        for label, _, url in (str(e).partition(",") for e in meta.get_all("Project-URL") or [])
    )
    assert SERVER_WEBSITE_URL == urls["Homepage"]


def test_ohne_installation_wird_nichts_erfunden(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der blanke Klon: lieber keine Auskunft als eine geratene.

    Beschreibung und Website sind in der Spec optional und fallen mit `None`
    aus dem Stempel heraus (`exclude_none=True`). Ein plausibel aussehender
    Platzhalter waere dagegen eine Behauptung — dieselbe Entscheidung, die
    `__init__.py` beim Versions-Fallback `0.0.0+source` trifft.

    Gemessen an den Funktionen, nicht an den Modulkonstanten: die stehen seit
    dem Import fest und liessen sich nur durch ein Neuladen des Moduls
    bewegen, was den Zustand fuer jeden folgenden Test veraendert.
    """

    def _boom(_name: str) -> object:
        raise PackageNotFoundError("zh-education-mcp")

    monkeypatch.setattr(identity, "_distribution_metadata", _boom)
    assert identity._distribution_field("Summary") is None
    assert identity._homepage() is None


def test_die_homepage_wird_am_label_gesucht_nicht_an_der_position() -> None:
    """`[project.urls]` fuehrt drei URLs; die Reihenfolge gehoert dem Backend.

    Die Gegenprobe zur naheliegenden Abkuerzung «nimm die erste»: hier steht
    `Homepage` an letzter Stelle, und trotzdem muss sie herauskommen.
    """

    class _Meta:
        @staticmethod
        def get_all(_key: str) -> list[str]:
            return [
                "Issues, https://example.invalid/issues",
                "Repository, https://example.invalid/repo",
                "Homepage, https://example.invalid/home",
            ]

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(identity, "_distribution_metadata", lambda _name: _Meta())
        assert identity._homepage() == "https://example.invalid/home"


def test_der_programmatische_name_bleibt_wie_er_ist() -> None:
    """Er steht in jeder Client-Konfiguration, die diesen Server eingetragen
    hat. Ein «schoenerer» Name waere ein stiller Bruch; dafuer gibt es `title`,
    und den gibt es jetzt."""
    assert SERVER_NAME == "zh_education_mcp"
    assert SERVER_TITLE != SERVER_NAME


async def test_die_instructions_wiederholen_keine_tool_beschreibung() -> None:
    """Die Bedingung, die die Spec an das Feld knuepft, als Messung.

    «should not duplicate information already in tool descriptions» — geprueft
    an den drei Tatsachen, die die `instructions` tragen. Steht eine davon
    eines Tages auch in einer Tool-Beschreibung, gehoert sie aus den
    `instructions` heraus (oder umgekehrt), und dieser Test sagt es.

    Er misst damit zugleich die Gegenrichtung: waeren die `instructions` bloss
    eine Zusammenfassung der Werkzeugliste, traefe mindestens eine dieser
    Zeichenketten zu.
    """
    async with Client(mcp_server()) as client:
        tools = (await client.list_tools()).tools

    for fakt in ("15. September", "1 bis 5", "CC BY 4.0"):
        assert fakt in SERVER_INSTRUCTIONS, f"{fakt!r} fehlt in den instructions"
        doppelt = [t.name for t in tools if fakt in (t.description or "")]
        assert not doppelt, f"{fakt!r} steht auch in der Beschreibung von {doppelt}"


def mcp_server():
    """Spaeter Import: `tools` zieht die ganze Tool-Schicht nach, und diese
    Datei soll ihre uebrigen Zusicherungen auch dann machen koennen, wenn dort
    etwas bricht."""
    from zh_education_mcp.tools import mcp

    return mcp
