"""Die Server-Identitaet, die Spec 2026-07-28 auf jede Antwort stempelt.

Bis `2025-11-25` war die Identitaet eine Einmal-Auskunft: sie stand im
`initialize`-Ergebnis, und wer den Handshake nicht las, sah sie nie. Seit
`2026-07-28` ist sie zweierlei geworden:

* **Ein Stempel auf jedem Ergebnis.** Der Runner setzt
  `_meta["io.modelcontextprotocol/serverInfo"]` auf *jede* Antwort der modernen
  Aera (Spec #3002, `mcp/server/runner.py::_stamp_server_info`).
* **Der Inhalt von `server/discover`.** Diese Methode muss ein Server der
  Revision anbieten («Servers **MUST** implement `server/discover`»), und sie
  ist der Ort, an dem ein Client erfaehrt, was dieser Server ist — ohne
  Handshake, ohne eine einzige Tool-Beschreibung zu lesen.

Gemessen, nicht geschlossen: Vor dieser Datei trug jede moderne Antwort
`{"name": "zh_education_mcp", "version": ""}`, und `server/discover` antwortete
mit `instructions: null`. Das SDK sagt selbst, dass es nichts einsetzt — «An
unversioned server reports an empty `version`; the SDK never substitutes its
own» (`mcp/server/lowlevel/server.py`). Die leere Version war also keine
Voreinstellung des SDK, sondern unsere Auslassung, und `Implementation.version`
ist im Typ der Revision ein Pflichtfeld.

**Woher die Werte kommen, und warum nicht von hier.** Version, Beschreibung und
Website stehen in `pyproject.toml` und werden ueber die
Distributions-Metadaten gelesen — dieselbe Quelle, aus der `__version__` seit je
kommt und die `scripts/check_version_sync.py` als einzige zulaesst. Ein Literal
hier waere eine zweite Wahrheit; im Portfolio ist genau so der falsche
User-Agent entstanden.

Titel und `instructions` haben in den Metadaten keine Entsprechung und stehen
deshalb als Text hier. Sie duerfen das: sie wiederholen keine Zahl, die
anderswo gepflegt wird.

**Fehlt die Distribution** (blanker Klon ohne Installation), bleiben
Beschreibung und Website `None` statt geraten. Beide Felder sind in der Spec
optional und fallen aus dem Stempel heraus (`exclude_none=True`) — eine
weggelassene Auskunft ist richtig, eine erfundene nicht. Dieselbe Entscheidung
wie beim Versions-Fallback `0.0.0+source` eine Ebene hoeher.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import metadata as _distribution_metadata

from . import __version__

#: Der programmatische Name. Er steht in jeder Client-Konfiguration, die diesen
#: Server eingetragen hat — er ist ein Bezeichner, kein Anzeigename, und wird
#: nicht «schoener» gemacht. Dafuer gibt es seit `2025-06-18` `title`.
SERVER_NAME = "zh_education_mcp"

#: Der Anzeigename. `Implementation.title` ist ausdruecklich fuer Oberflaechen
#: gedacht — «optimized to be human-readable […] even by those unfamiliar with
#: domain-specific terminology». `zh_education_mcp` ist das nicht.
SERVER_TITLE = "Bildungsstatistik Kanton & Stadt Zürich (BISTA)"

#: Beschreibt den Server fuer Menschen und Modelle gleichermassen
#: (`server/discover` → `instructions`). Die Spec nennt den Zweck genau: «help
#: the model use the server effectively and should not duplicate information
#: already in tool descriptions».
#:
#: Was hier steht, steht deshalb in *keiner* Tool-Beschreibung: der Stichtag,
#: die Unterdrueckung kleiner Fallzahlen, die Lizenzpflicht und die
#: Lese-Beschraenkung. Das sind die vier Dinge, an denen eine Antwort falsch
#: wird, ohne dass ein einzelner Tool-Aufruf es zeigen koennte.
SERVER_INSTRUCTIONS = """\
Bildungsstatistik des Kantons Zürich (BISTA) — Lernende, Maturitätsquoten, \
Staatsangehörigkeiten und Mittelschulen, nach Schulgemeinde, Schulkreis, \
Bezirk und Kanton.

Vier Dinge gelten für jede Antwort dieses Servers und stehen in keiner \
einzelnen Tool-Beschreibung:

1. **Stichtag ist der 15. September.** Die Daten sind eine Jahresaufnahme, \
keine Zeitreihe mit unterjährigen Werten. «Aktuell» heisst hier: das zuletzt \
erhobene Schuljahr, nicht heute.
2. **Kleine Fallzahlen sind unterdrückt.** BISTA schreibt «1 bis 5» statt \
einer Zahl. Solche Zeilen fliessen nicht in Summen ein; eine Summe mit \
Unterdrückungshinweis ist eine Untergrenze, keine Summe. Den Hinweis in der \
Antwort mitgeben, statt ihn wegzukürzen.
3. **Die Quelle ist zu nennen.** Die Daten stehen unter CC BY 4.0. Jede \
Antwort trägt Quelle, Lizenz und Modifikationshinweis mit; beim Weitergeben \
gehören sie dazu.
4. **Der Server ist ausschliesslich lesend.** Er verändert nichts und kann \
nichts anlegen. Alle Werkzeuge sind `readOnlyHint: true`.

Schulkreise gibt es nur in der Stadt Zürich (Uto, Limmattal, Waidberg, \
Glattal, Schwamendingen, Zürichberg, Letzi); der übrige Kanton ist nach \
Schulgemeinden gegliedert. Bei unbekanntem Ort zuerst \
`zh_edu_list_schulgemeinden` aufrufen, statt einen Namen zu raten.\
"""


def _distribution_field(name: str) -> str | None:
    """Ein Feld aus den Distributions-Metadaten, oder ``None``.

    ``None`` sowohl bei fehlender Installation als auch bei fehlendem Feld —
    fuer den Aufrufer ist beides derselbe Fall: es gibt nichts zu melden.
    """
    try:
        return _distribution_metadata("zh-education-mcp").get(name)
    except PackageNotFoundError:
        return None


def _homepage() -> str | None:
    """Die Homepage aus ``[project.urls]``.

    Die Metadaten fuehren jede URL als ``"Homepage, https://…"`` in einem
    wiederholbaren ``Project-URL``-Feld; ``Home-page`` ist bei hatchling leer.
    Gesucht wird deshalb nach dem Label, nicht nach der ersten URL: die
    Reihenfolge der Eintraege gehoert dem Build-Backend, nicht uns.
    """
    try:
        entries = _distribution_metadata("zh-education-mcp").get_all("Project-URL") or []
    except PackageNotFoundError:
        return None
    for entry in entries:
        label, _, url = str(entry).partition(",")
        if label.strip().lower() == "homepage" and url.strip():
            return url.strip()
    return None


#: Aus ``pyproject.toml`` → ``[project].description``.
SERVER_DESCRIPTION = _distribution_field("Summary")

#: Aus ``pyproject.toml`` → ``[project.urls].Homepage``.
SERVER_WEBSITE_URL = _homepage()

#: Aus den Paket-Metadaten, ueber ``__init__``. Steht hier nur als benannter
#: Durchreicher, damit der Konstruktor-Aufruf in `tools.py` alle fuenf
#: Identitaetsfelder aus derselben Datei bezieht.
SERVER_VERSION = __version__
