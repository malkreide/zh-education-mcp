# CLAUDE.md

## Teil 1 — Portfolio-Konventionen

### Vor der Arbeit

Klon-Aktualität prüfen — Standard-Branch ermitteln, nicht `main` annehmen:

```bash
B=$(git ls-remote --symref origin HEAD | sed -n 's|^ref: refs/heads/\([^[:space:]]*\).*|\1|p')
git fetch origin "${B:?Standard-Branch nicht ermittelbar}" &&
  git rev-list --count HEAD..FETCH_HEAD
```

Drei Server im Portfolio heissen ihren Standard-Branch `master`
(`openlex-mcp`, `swiss-courts-mcp`, `swisstopo-mcp`); dort scheitert ein fest
verdrahtetes `origin/main` mit «couldn't find remote ref main». Wer das für ein
Netzproblem hält, arbeitet weiter auf genau dem veralteten Klon, vor dem dieser
Absatz warnt. Den `:?`-Schutz nicht weglassen: Bei leerem `B` fetcht git still
den Remote-HEAD und endet mit 0.

Ein veralteter Klon erzeugt eine rote CI, deren Ursache nicht im Diff steht.
Am 3.8.2026 zweimal passiert — beide Male fehlten genau die Commits, die
das Gate einführten, an dem der Branch scheiterte.

In diesem Repo nimmt ein SessionStart-Hook diese Prüfung ab (Teil 2). Er meldet
nur den Rückstand; eingespielt wird weiterhin von Hand, und der Befehl oben
bleibt die Fassung für alle anderen Server im Portfolio.

Gates lokal fahren, mit der GEPINNTEN ruff-Version aus der CI. Eine andere
Version meldet Abweichungen, die niemand verursacht hat.

### Tests

Gegenprobe ist Pflicht. Ein Test, der grün bleibt, wenn man die
Implementierung entfernt, prüft nichts. Jede neue Zusicherung einzeln
neutralisieren und zeigen, dass genau die zugehörigen Tests fallen.

Zwei Fallen, die beide grün blieben:

- Eine Fake-Uhr, die nur beim Schlafen vorrückt, kann eine Zusicherung über
  echte Zeit nicht widerlegen.
- `monkeypatch.setattr(modul.asyncio, "sleep", ...)` greift ins Modul
  `asyncio` selbst und entschärft die Mechanik im ganzen Prozess. Patche
  einen Modul-Alias (`_sleep = asyncio.sleep`), nicht das fremde Modul.

Handgeschriebene Fixtures kodieren die Annahme des Autors und können sie
nicht widerlegen. Mindestens eine aufgezeichnete Antwort pro externem
Endpunkt, mit Aufnahmedatum.

### Wenn etwas rot ist

Roter Live-Test: erst die Quelle abfragen, dann einordnen. Nicht aus der
Fehlermeldung schliessen. Am 3.8.2026 hiess "nicht gefunden" nicht, dass der
Datensatz weg war, sondern dass die Quelle die Schreibweise ihrer Kopfzeile
gewechselt hatte — vier von sechs Datensätzen produktiv kaputt, alle
Unit-Tests grün.

PR ohne jeden Check ist selten ein Repo ohne CI, meistens ein
Merge-Konflikt: GitHub berechnet dafür keinen Merge-Commit und startet nichts.

Ein Codex-Review auf einem PR wird beantwortet oder behoben, nie ignoriert.

Nicht jede Fehlmeldung ist rot. `git push origin --delete <branch>` scheitert in
der Claude-Code-Umgebung am Agent-Proxy und schliesst mit «Everything
up-to-date» — die Meldung, die es sonst gibt, wenn nichts zu tun war. Der Grund
wird erst mit expliziter Refspec sichtbar: `git push origin :refs/heads/<branch>`
liefert `HTTP 403`, die GitHub-API dazu «Write access to this GitHub API path is
not permitted through this proxy». Gesperrt sind löschende Operationen, nicht
gewöhnliche Pushes. Also nicht mit Backoff wiederholen — es ist kein Netzproblem
— sondern lokal oder über die GitHub-Oberfläche löschen. Am 19.8.2026 gemessen:
fünf Versuche, fünfmal dieselbe 403.

### Wenn Codex gar nicht erst hinsieht

Die Zeile oben unterstellt, dass es einen Befund geben *kann*. Das ist nicht
immer so, und man sieht es dem PR nicht an.

Am 21.8.2026 war das Code-Review-Kontingent zwischen 08:41 und 09:48
aufgebraucht — davor echte Reviews, danach in 30 Repos nur noch:

```
You have reached your Codex usage limits for code reviews.
```

Bis mindestens zum 22.8. um 08:30, also 23 Stunden später, blieb es dabei. In
der Zwischenzeit sind 32 PRs mit formal erfülltem Häkchen gemergt worden, ohne
dass jemand hineingesehen hat.

Vier Gründe, warum Codex schweigt, und nur einer davon ist harmlos:

- **Kein Befund** — dann reagiert er mit 👍 und schreibt nichts.
- **Der PR ist ein Draft** — darauf läuft Codex nicht an.
- **Das Kontingent ist weg** — dann schreibt er die Meldung oben.
- **Für das Repo ist keine Codex-Umgebung eingerichtet** — dann schreibt er
  stattdessen «To use Codex here, create an environment for this repo», und
  daran ändert kein Wartefenster etwas.

«Kein Kommentar» heisst also nicht «geprüft und sauber». Unterscheiden lässt es
sich an der Form: Ein echter Review ist ein Review-Objekt («💡 Codex Review»,
mit Commit-Angabe), die Limit-Meldung ein gewöhnlicher Issue-Kommentar. Das
sind zwei verschiedene Abfragen — `get_reviews` gegen `get_comments`; wer nur
eine davon nimmt, übersieht die andere Hälfte. Genau so ist die Limit-Meldung
zuerst durchgerutscht.

Portfolio-weit nachsehen:

```
search_pull_requests: user:malkreide commenter:chatgpt-codex-connector[bot] updated:>=<Datum>
```

Findet nur, wo er *kommentiert* hat. Repos ohne PR-Aktivität tauchen nicht auf
— das ist kein Beleg, dass dort geprüft wurde.

Eine Absage taugt umgekehrt nicht als Beleg fürs Gegenteil, denn die vier
Fälle kommen in einer Reihenfolge: Ist das Kontingent leer, meldet Codex das
— ob überhaupt eine Umgebung besteht, prüft er dann womöglich gar nicht. In
`swiss-public-data-mcp` kam am 22.8. die Limit-Meldung und am 23.8., nach
Rückkehr des Kontingents, die Umgebungs-Meldung; erst als der erste Engpass
weg war, wurde der zweite sichtbar. Eine Limit-Meldung belegt also, dass die
App reagiert, nicht dass sie hier arbeiten könnte.

Belastbar ist nur ein Review-Objekt, und dafür gibt es eine eigene Abfrage:

```
search_pull_requests: user:malkreide type:pr reviewed-by:chatgpt-codex-connector[bot]
```

Am 23.8.2026 über die 41 Server-Repos: 25 mit mindestens einem echten Review,
16 nur mit Absagen. «Belegt» heisst dabei «damals», nicht «heute» — ein Review
vom 16.8. sagt über den aktuellen Stand nichts.

Zweiter Weg, den Prüfer zu verlieren, ganz ohne Kontingentproblem: zu schnell
mergen. Am 21./22.8. lagen zwischen «ready for review» und Merge mehrfach drei
bis fünf Sekunden. Codex wird beim Umschalten von Draft auf ready ausgelöst und
braucht danach Zeit; wer sofort mergt, hat das Häkchen gesetzt und den Review
nicht abgewartet.

Das Kontingent hängt am Konto, nicht am Repo, und Code-Reviews haben einen
eigenen Topf — nur GitHub-getriggerte Reviews zählen hinein. ChatGPT-Pläne
fahren ein rollendes Fünf-Stunden-Fenster plus Wochenlimits; welches greift,
steht im Codex-Dashboard. Zeigt das freies Kontingent, während Reviews weiter
scheitern, ist das ein bekannter Fehler bei mehreren verbundenen Konten — dann
den GitHub-Connector in den Codex-Einstellungen trennen und neu verbinden.

### Wenn zwei Agenten dasselbe tun

Vor dem Anlegen eines Branches mit vorgegebenem Namen prüfen, ob es ihn schon
gibt:

```bash
git ls-remote --heads origin claude/<name> | wc -l
```

Steht dort `1`, arbeitet jemand anderes daran — mit Schreibrecht auf denselben
Ref.

Ein PR mit leerem Diff wird geschlossen, nicht gemergt. Der Test ist
`get_files` auf dem PR: kommt `[]` zurück, ändert er nichts. Ein grüner Check
sagt dazu nichts — die CI prüft den Head, nicht die Differenz zur Basis.

Am 21.8.2026 liefen zwei Sessions dieselbe Aufgabe über 45 Repos, auf den
Branches `claude/codex-review-audit-templates-9sn6mx` und
`claude/codex-review-audit-7ioh56`. Wo die eine zuerst nach `main` kam, wurde
`main` in den Branch der anderen gemergt und der add/add-Konflikt zugunsten
von `main` aufgelöst. Übrig blieben 14 PRs, die durch sämtliche Gates grün
liefen und nichts enthielten; sie wurden gemergt und hinterliessen leere
Merge-Commits. Mit den zwei Folge-PRs, die aus demselben Grund gegenstandslos
waren, waren 16 der 59 PRs jenes Tages reine Reibung.

Dieselbe Klasse wie der handgeschriebene Stub, der denselben Feldnamen annahm
wie der Code: Nichts ist rot, weil nichts geprüft wird, worauf es ankommt.

## Teil 2 — Dieses Repo


**ruff: eine Quelle.** `pyproject.toml`, `dev`-Extra, `ruff==0.16.3`. Die CI
hat keinen eigenen Pin-Schritt — der Install über `ci.yml` genügt, lokal wie
dort. Eine `.pre-commit-config.yaml` gibt es nicht; wenn eine dazukommt, muss
sie dieselbe Version aus `pyproject.toml` beziehen und keine zweite nennen.

Vor dem Lauf `ruff --version` prüfen: ein älteres ruff früher im `PATH`
schlägt den Pin, ohne dass der Install etwas meldet.

**Gates, wörtlich aus `ci.yml`** (Matrix: Python 3.11 / 3.12 / 3.13):

```
PYTHONPATH=src pytest tests/ -m "not live"
python scripts/check_ruff_pin.py
ruff check src/ tests/ scripts/
ruff format --check src/ tests/ scripts/
python scripts/check_version_sync.py
```

Die fünf Zeilen sind der lokale Lauf. `CONTRIBUTING.md` und
`CONTRIBUTING.de.md` nennen unter «Code-Stil» dieselben ruff-Pfade und -Flags —
wer das Gate ändert, ändert beide Dateien mit. Sie standen schon einmal
auseinander: `ruff check src/` ohne `tests/` und `scripts/`, `format` ohne
`--check`. Wer danach ging, war lokal grün und in der CI rot.

**Alle fünf laufen in einem Job auf allen drei Versionen.** Keine
`if: matrix.python-version`-Ausnahme — ein grünes 3.13 heisst hier wirklich,
dass alles auf 3.13 lief. (Im Portfolio nicht selbstverständlich:
`swiss-food-safety-mcp` gated zwei Gates auf 3.11.) Kein `fail-fast: false`:
Eine rote 3.11 bricht 3.12 und 3.13 ab, bevor sie etwas sagen.

**Ein vierter Workflow ist kein Gate, sondern ein Werkzeug.**
`.github/workflows/tls-probe.yml` («TLS-Import-Sonde») läuft **nur** auf
`workflow_dispatch` und fährt `scripts/tls_import_probe.py` gegen eine
wählbare URL. Er taucht auf keinem PR auf und soll das auch nicht — er ist
da, wenn ein Verdacht auf ein TLS- oder Import-Problem gegen die Quelle
besteht. Wer ihn nicht kennt, baut sich die Sonde von Hand nach.

**Ein Gate, das kein PR sieht.** `.github/workflows/publish.yml` fährt auf
`release: published` `scripts/check_release_artifacts.py` gegen die gebauten
Artefakte. Was es prüft, steht im Release-Abschnitt der README; hier nur der
Grund, es ernst zu nehmen: Es fällt erst beim Release, und eine PyPI-Version
ist dann unveränderlich.

**Ein Hook prüft die Klon-Aktualität beim Sessionstart.**
`.claude/hooks/session-start.sh`, registriert in `.claude/settings.json` unter
`hooks.SessionStart`. Er meldet, wie viele Commits der ausgecheckte Stand hinter
`origin/<Default-Branch>` liegt, und schweigt bei 0. Abschalten: `ZH_STALE_CHECK=0`.

Vier Zusicherungen, nach Wichtigkeit: Er blockiert die Session nie — kein
`set -e`, sondern `trap 'exit 0' EXIT`, damit auch ein unvorhergesehener Fehler
mit 0 endet. Kurzes Timeout je Netzaufruf (zwei Stück, Default je 5s), dazu
abgeschaltete interaktive Rückfragen von git, ssh und credential-helper — ein
Passwort-Prompt ist der eine Hänger, den `timeout(1)` nicht abräumt. Ausgabe nur
bei echtem Rückstand. Default-Branch ermittelt statt geraten; ist er nicht
ermittelbar, schweigt der Hook, statt auf `main` zu fallen.

Zwei am 21.8.2026 in der Agent-Umgebung gemessene Eigenheiten bestimmen den
Aufbau: Der Klon ist dort **flach** (`--is-shallow-repository` = `true`), und
`refs/remotes/origin/HEAD` ist **nicht gesetzt**. Darum ist `ls-remote --symref`
die Primärquelle und der lokale Zeiger nur Fallback — wer sich allein auf ihn
verlässt, meldet nie etwas. Und darum steht vor der Zählung ein `git merge-base`:
Ohne gemeinsamen Vorfahr zählt `HEAD..FETCH_HEAD` den halben Remote-Ast statt
einen Rückstand, und eine erfundene Zahl ist schlechter als keine.

Gegenprobe in `tests/test_session_start_hook.py` — 16 Tests gegen echte
Wegwerf-Repos über `file://`, ohne Netz, im Gate mitlaufend. Wer den Hook
ändert, fährt sie mit. Der Rest steht in `.claude/hooks/README.md`.

**Live-Tests: geplanter Workflow vorhanden.** `.github/workflows/live-tests.yml`,
`cron: "23 5 * * 1"` plus `workflow_dispatch`. Die Live-Suite ist also nicht bloss
per `-m "not live"` ausgeschlossen — DRIFT-005 ist hier erfüllt. `schedule`
greift nur auf dem Default-Branch (`main`): Änderungen am Workflow wirken erst
nach dem Merge, vorher von Hand per `workflow_dispatch`.
