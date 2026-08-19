# Mitwirken bei zh-education-mcp

Vielen Dank für dein Interesse an einem Beitrag!

🇬🇧 [English version](CONTRIBUTING.md)

## Entwicklungs-Setup

```bash
git clone https://github.com/malkreide/zh-education-mcp.git
cd zh-education-mcp
pip install -e ".[dev]"
```

## Tests ausführen

```bash
# Unit-Tests (gemockt, kein Netzwerk)
pytest tests/ -m "not live"

# Alle Tests inkl. Live-API-Aufrufe
pytest tests/
```

### Die Live-Suite: wann sie läuft, und wer ein rotes Ergebnis sieht

**Kadenz:** jeden Montag um 05:23 UTC, dazu jederzeit von Hand über *Actions →
Live-Tests → Run workflow*. Siehe [`.github/workflows/live-tests.yml`](.github/workflows/live-tests.yml).

**Wer es sieht:** Ein roter Lauf öffnet ein Issue mit dem Titel `Live-Tests gegen
BISTA rot …` und dem Label `upstream` — und kommentiert das bestehende, statt ein
zweites aufzumachen. Wird die Suite wieder grün, wird es geschlossen.

**Ein roter Live-Lauf heisst nicht zwingend «unser Fehler».** Er heisst: Der
Vertrag mit der Quelle hat sich geändert, oder die Quelle ist gerade aus. Beides
gehört gesehen, nur das Erste gehört gefixt. Bitte den Lauf lesen, bevor der Job
deaktiviert wird — so stirbt dieser Check, und er ist der einzige im Repo, der
einer falschen Grundannahme über BISTA widersprechen kann. Jeder andere Test
prüft gegen eine Fixture, und die Fixture ist aus derselben Annahme geschrieben
wie der Code.

Das ist nicht hypothetisch. Am 3.8.2026 las der Code `r["Schulgemeinde"]`,
während BISTA `schulgemeinde` lieferte — vier von sechs Datensätzen, acht Tools,
alle Unit-Tests grün. Gefunden hat es ein Live-Lauf von Hand, weil keiner geplant
war.

Der PR-Lauf bleibt bei `-m "not live"`: Ein fremder 503 darf keinen fremden Pull
Request rot machen.

## Code-Stil

Wörtlich aus `ci.yml` — dieselben Pfade, dieselben Flags:

```bash
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
```

`tests/` und `scripts/` sind mitgegatet; wer nur `src/` lintet, lässt die CI an
Dateien rot werden, die er nie geprüft hat. Ohne `--check` formatiert `ruff
format`, statt zu prüfen.

`ruff` ist in `pyproject.toml` (`dev`-Extra) gepinnt, `pip install -e ".[dev]"`
oben installiert genau diese Version. Ein anderes `ruff` früher im `PATH`
schlägt den Pin, ohne dass der Install etwas meldet — `python
scripts/check_ruff_pin.py` prüft beide Aufrufwege und läuft auch in der CI.

## Datenquellen

Dieser Server nutzt die öffentliche BISTA-API (`bista.zh.ch/basicapi/ogd/`) — keine Authentifizierung nötig.

**No-Auth-First-Prinzip**: Phase-1-Tools müssen ohne API-Schlüssel funktionieren.

## Neue Tools hinzufügen

1. API-Endpunkt zuerst mit `curl` validieren
2. Pydantic-v2-Input-Modell hinzufügen
3. Tool mit `@mcp.tool`-Decorator und vollständigem Docstring ergänzen
4. Gemockte Unit-Tests mit `respx` schreiben
5. Live-Tests mit `@pytest.mark.live` markieren
6. CHANGELOG.md aktualisieren

## Änderungen einreichen

1. Repo forken
2. Branch erstellen: `git checkout -b feat/dein-feature`
3. Commit: `git commit -m "feat: add xyz tool"`
4. Pushen und einen Pull Request öffnen

## Releases

Publiziert wird nicht über einen Pull Request: Ein GitHub-Release stösst
[`publish.yml`](.github/workflows/publish.yml) an, das die gebauten Artefakte vor
dem PyPI-Upload prüft. Was es prüft und warum es vor dem Upload steht, steht
unter [Release](README.de.md#release).

Zwei Folgen für Beitragende:

- Den `mcp-name:`-Kommentar am Ende von `README.md` unangetastet lassen. Er wird
  als Paket-Beschreibung ausgeliefert, und das Gate verlangt genau einen — ihn zu
  entfernen oder irgendwo in dieser Datei einen zweiten zu schreiben, bringt das
  Release zu Fall.
- Versionen stehen in `pyproject.toml`, `server.json` und den README-Badges.
  [`check_version_sync.py`](scripts/check_version_sync.py) vergleicht sie auf
  jedem Pull Request — also gemeinsam ändern.
