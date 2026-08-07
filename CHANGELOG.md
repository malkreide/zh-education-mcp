# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Die gelesenen Feldnamen werden jetzt bestätigt, nicht nur normalisiert.**
  `_normalise_keys` nimmt seit dem 3. August 2026 die **Schreibweise** aus dem
  Spiel — das war die Lehre aus dem BISTA-Wechsel von `Schulgemeinde` auf
  `schulgemeinde`.

  Die **Identität** des Namens nimmt es nicht aus dem Spiel. Wechselt die
  Quelle einen Feldnamen — `anzahl` zu `wert`, `schulgemeinde` zu `gemeinde` —,
  hilft keine Normalisierung: Der Server fände wieder nichts und meldete
  «nicht gefunden». Derselbe Ausfall, andere Ursache.

  `_READ_FIELDS` erklärt jetzt je Endpunkt, welche Spalten der Code
  **tatsächlich anfasst** — aus dem Quelltext erhoben, nicht geraten —, und
  `_confirm_shape` bestätigt sie auf dem ersten Eintrag. Bei Abweichung fliegt
  `UpstreamSchemaError` mit den tatsächlich vorhandenen Spalten in der Meldung.

  **Ausdrücklich keine Schema-Validierung** (`FID-006` verlangt sie nicht): Eine
  neue Spalte upstream ist harmlos und lässt die Prüfung grün. Eine leere Datei
  ebenso — sie sagt nichts über die Form, und `FID-003` behandelt sie an der
  richtigen Stelle.

- **Live-Tests, die die Erklärung gegen die echte Quelle halten.**
  `tests/test_read_fields.py` prüft für alle sechs Endpunkte, dass die
  deklarierten Felder in der echten Antwort stehen — und dass die aufgezeichnete
  Fixture noch dieselbe Kopfzeile hat wie die Quelle. Ein Fixture allein kann
  diese Klasse nicht widerlegen: Es trägt die angenommene Kopfzeile und
  bestätigt sie dauerhaft.

  **Noch ohne grünen Lauf.** Am 2026-08-07 antwortete
  `https://www.bista.zh.ch/basicapi/ogd/…` auf allen sechs Endpunkten mit
  **HTTP 502** (HTML-Fehlerseite des BISTA-Webservers; die Startseite lieferte
  200, es lag also nicht am Netz und nicht am User-Agent). Nach
  [`FID-006`](https://github.com/malkreide/mcp-audit-skill/blob/main/checks/FID-006.md)
  §2.6 ist der Ausgang damit `todo`, **nicht** `pass`: Der Test existiert, aber
  er hat noch nichts belegt. Der nächste Live-Lauf entscheidet.

### Geaendert — die aufgezeichneten Fixtures stehen jetzt im `schema_fields.toml`

Als das Manifest geschrieben wurde, gab es hier keine aufgezeichneten
Kopfzeilen — nur handgeschriebene Zeilen in den Tests. Es stand deshalb
ausdruecklich drin: «Sobald eine echte CSV-Fixture dazukommt, gehoert sie
hierher.» `scripts/record_fixtures.py` hat sie geliefert; hier ist die Zeile.

Sechs `fixture = …`-Eintraege, je einer pro Datensatz. Damit haelt
`schema_field_probe` bei jedem Lauf auch die Aufzeichnung gegen die Quelle und
meldet `FIXTURE_PINS_OLD_HEADER`, sobald eine Fixture Namen pinnt, die BISTA
nicht mehr sendet.

Das ist genau der Satz, der am 3.8.2026 gefehlt hat. Die Unit-Tests waren gruen,
weil sie die Annahme des Codes gegen eine Aufzeichnung derselben Annahme hielten
— und niemand konnte das sehen, weil nichts die Aufzeichnung mit der Quelle
verglich.

Die Fixture ist dabei **nicht** der Massstab: Verglichen wird weiterhin der Code
gegen die Quelle. Die Fixture wird nur gelesen, um zu erklaeren, warum eine
gruene Suite nichts bedeutet haette.

Am Tag der Aufzeichnung meldet die Probe erwartungsgemaess nichts — eine heute
aufgezeichnete Kopfzeile kann nicht die von gestern pinnen. Geprueft wurde
trotzdem, ob die Deklaration wirkt und nicht nur dasteht: Mit einer versuchsweise
auf `Schulgemeinde` zurueckgedrehten Kopfzeile in `sek1.csv` meldet die Probe

    FIXTURE_PINS_OLD_HEADER: tests/fixtures/sek1.csv pins 1 field name(s)
    the source no longer sends (Schulgemeinde)

Eine Deklaration, die nichts tut, saehe von aussen aus wie eine aktuelle Fixture.

### Behoben — die Maturitätsquote war um den Faktor 100 zu hoch

`zh_edu_maturitaetsquote` rechnete `float(quote) * 100`. Die Quelle publiziert
`Maturitaetsquote_gymnasial` aber **bereits als Prozentzahl**: Gegenprobe an
einer echten Zeile 25/85 = 29.41, und die Spalte sagt 29.41; der Wertebereich
über alle 1658 Zeilen liegt bei 0.71 bis 54.19. Gegen die echte Quelle meldete
das Tool damit Quoten wie **«2290.0 %»** statt «22.9 %».

**Warum das niemand gesehen hat, ist der eigentliche Eintrag.** Die Fixture war
erfunden — sie trug `0.15` in dieser Spalte, eine Bruchzahl, die es in der
Quelle nicht gibt. Mit `* 100` ergaben sich daraus die vollkommen plausiblen
«15.0 %». Produktivcode und Fixture trugen denselben Irrtum, stammten aus
demselben Kopf und derselben Stunde, also konnte kein Test ihn widerlegen. Der
Fehler ist nicht beim Lesen des Codes aufgefallen, sondern beim **Aufzeichnen
der Fixtures** (siehe unten).

Festgehalten wird er jetzt zweimal: durch die Zusicherung in
`test_maturitaetsquote_zeigt_die_19_jaehrigen`, die auf der aufgezeichneten
Zeile «22.9 %» erwartet, und durch
`test_die_maturitaetsquote_wird_nicht_ein_zweites_mal_mal_hundert_genommen`,
die die **Einheit** der Quellspalte prüft statt einer Zahl — sie schlägt an,
wenn BISTA eines Tages auf Bruchzahlen umstellt. Gegenprobe geführt: Mit dem
wiederhergestellten `* 100` fallen beide.

### Hinzugefügt — die Fixtures sind aufgezeichnet, nicht mehr ausgedacht

Bis hierher standen die Unit-Test-Daten als CSV-Literale in den Testdateien,
überschrieben mit «Sample CSV-Daten (anonymisiert)» und gefüllt mit runden
Phantasiezahlen (500, 300, 10746). Ein handgeschriebener Mock kodiert die
Annahme seines Autors und kann sie deshalb prinzipiell nicht widerlegen.

Neu: **`scripts/record_fixtures.py`** zeichnet alle sechs Endpunkte von der
Live-Quelle auf und schreibt `tests/fixtures/*.csv` plus
`tests/fixtures/PROVENANCE.md` mit Endpunkt, **Aufzeichnungsdatum**,
Auswahlregel, Zeilenzahl und SHA-256 je Datei. Der Abruf liegt als Skript
daneben und nicht als Handgriff im Gedächtnis: So kostet das nächste Datum
einen Lauf statt einer Rekonstruktion.

Ohne Datum ist «aufgezeichnet» nach zwei Jahren von «ausgedacht» nicht mehr zu
unterscheiden — die Datei sieht gleich aus.

**Was der Wechsel sofort aufgedeckt hat:**

- Die Maturitätsquote war um Faktor 100 zu hoch (oben).
- Die `maturitaet`-Fixture behauptete ein Schema, das die Quelle nicht hat:
  `Kanton,Jahr` erfunden, `Stand_Gemeindegrenzen,Gemeinde_BFSCode` gefehlt.
- Die `mittelschulen`-Fixture kannte `stufe`, `finanzierung` und
  `staatsangehoerigkeit` nicht und kürzte die Typen zu «FMS»/«HMS» — die
  Quelle schreibt «Fachmittelschule» und «Handelsmittelschule» aus.
- Vier Zusicherungen hatten «2024» hartcodiert, während die Quelle auf 2025
  steht. Sie leiten den Jahrgang jetzt über `latest_year()` aus der Fixture ab:
  Ein Test, der «das aktuellste Jahr» im Namen führt und eine Jahreszahl
  hinschreibt, prüft ab dem nächsten Jahrgang etwas anderes, als er verspricht.

Die aufgezeichneten Kopfzeilen bleiben **uneinheitlich**, so wie die Quelle sie
liefert — vier Endpunkte klein, zwei gross, und zwei mischen innerhalb einer
Zeile (`gebiet_Bezeichnung`, `staatsangehoerigkeit_ISO2_Code`). Sie zu
vereinheitlichen würde genau die Eigenschaft wegputzen, an der der Server am
3.8.2026 gescheitert ist.

Der Rahmen dazu steht im Skill [`mcp-data-fidelity`](https://github.com/malkreide/mcp-data-fidelity-skill)
unter Regel 5 und im Katalog-Check `OPS-009`.

### Hinzugefuegt — die Live-Suite läuft geplant, statt nur markiert zu sein

`ci.yml` fährt `pytest tests/ -m "not live"`. Das ist richtig — ein fremder 503
darf keinen fremden Pull Request rot machen — und es liess die drei Live-Tests
seit ihrer Entstehung an keiner Stelle laufen. **`-m "not live"` ist kein Ort, an
dem Tests laufen; es ist die Abwesenheit eines solchen.**

Ausgerechnet diese drei sind die einzigen im Repo, die einer falschen
Grundannahme über BISTA widersprechen können: Jeder andere Test prüft gegen eine
Fixture, und die Fixture ist aus derselben Annahme geschrieben wie der Code. Zwei
Belege in fünf Tagen, beide von aussen gefunden statt von der Suite:

* **3.8.2026** — `r["Schulgemeinde"]` gegen `schulgemeinde`. Vier von sechs
  Datensätzen, acht Tools, alle Unit-Tests grün.
* **7.8.2026** — `r.get("Total_19_Jahre_alt")` gegen eine Zeile, deren Schlüssel
  der Fix vom 3.8. kleingeschrieben hatte. Die Spalte «19-Jährige» stand seitdem
  in jeder Antwort auf «—».

`.github/workflows/live-tests.yml`: wöchentlich montags 05:23 UTC auf einer
ungeraden Minute, dazu `workflow_dispatch`, damit die Suite nach einem Hinweis
sofort laufen kann statt bis Montag zu warten. Der PR-Lauf bleibt unverändert bei
`-m "not live"` — dies ist ein *zusätzlicher* Lauf, kein Umbau.

**Drei Antworten, nicht zwei.** `if: failure()` allein kann nicht zwischen «ein
Test ist rot» und «der Job kam gar nicht bis zu den Tests» unterscheiden; ein
gescheitertes `pip install` sähe aus wie ein gebrochener Vertrag mit der Quelle.
Ausgewertet wird deshalb der Exit-Code von pytest:

| Exit | Bedeutung | Wirkung aufs Issue |
|---|---|---|
| 0 | alle grün | offenes Issue wird geschlossen |
| 1 | Tests gefallen | Issue öffnen oder kommentieren |
| 5 | **null Tests eingesammelt** | nichts — und der Job wird rot |
| 2, 3, 4 | pytest kam nicht durch | nichts — und der Job wird rot |

Die 5 ist die wichtigste Zeile: Benennt jemand die Marke um oder verschiebt die
Tests, sammelt `-m live` null Tests ein und pytest meldet Erfolg. Ein Workflow,
der das grün bucht, hat sich selbst stillgelegt und sagt es niemandem — dieselbe
Klasse Ausfall wie ein leeres Suchergebnis, das wie eine Antwort aussieht.

Ein `unknown` schliesst nie ein Issue: zuzumachen hiesse zu behaupten, der
Vergleich sei gelaufen. Ein Issue mit stabilem Titel-Präfix und Label `upstream`
wird kommentiert statt verdoppelt, damit ein zweiter roter Montag den Thread
verlängert und nicht die Liste.

Kadenz und Zuständigkeit stehen in CONTRIBUTING (beide Sprachen) und im README —
samt dem Satz, ohne den der Job beim ersten transienten Rot deaktiviert wird: Ein
roter Live-Lauf heisst nicht zwingend «unser Fehler», sondern «der Vertrag mit
der Quelle hat sich geändert oder die Quelle ist aus».

Gemessen mit `live_schedule_probe` aus `mcp-continuous-auditor`: vorher
`LIVE_UNSCHEDULED`, jetzt `LIVE_SCHEDULED`, Exit 0.

### Behoben — «19-Jährige» stand seit dem Kopfzeilen-Fix in jeder Zeile auf «—»

`_normalise_keys` senkt seit dem 3.8.2026 jede BISTA-Kopfzeile auf
Kleinschreibung. `zh_edu_maturitaetsquote` las an einer Stelle weiter
`r.get("Total_19_Jahre_alt")` — gegen eine Zeile, deren Schlüssel längst
`total_19_jahre_alt` heissen.

`.get()` mit Default wirft nicht und loggt nicht. Die Spalte «19-Jährige» der
Maturitätsquoten-Tabelle trug seitdem in **jeder Zeile jeder Antwort** einen
Gedankenstrich, und die Quote daneben stimmte weiter — die Tabelle sah richtig
aus und war es an einer von fünf Spalten nicht.

Dass es niemandem auffiel, ist kein Zufall: Die beiden bestehenden Tests prüfen
`"Zürich" in result` und `"15.0%" in result`, also genau die zwei Spalten, die
funktionierten. Ein Test, der nur die grüne Hälfte einer Tabelle behauptet,
deckt die andere nicht ab.

Gefunden hat es `schema_field_probe` aus `mcp-continuous-auditor` gegen die
Live-Quelle — der Vergleich der Feldnamen, die dieser Code liest, mit denen, die
`www.bista.zh.ch` gerade liefert. Genau der Lauf, für den das mitgelieferte
`schema_fields.toml` da ist. Nach dem Fix: `SCHEMA_OK`, 6 von 6 Datensätzen,
Exit 0.

Zwei Regressionstests halten es fest — einer prüft die **ganze** Tabellenzeile
Spalte für Spalte statt einzelner Teilstrings, der andere fährt dieselbe Antwort
mit kleingeschriebener Kopfzeile, damit der Fix nicht an einer Schreibweise
hängt, die BISTA morgen wieder ändern kann.

### Hinzugefuegt

- **Release-Gate vor dem PyPI-Upload** (`scripts/check_release_artifacts.py`,
  eingehaengt in `publish.yml` zwischen `python -m build` und dem Upload).
  Geprueft wird das **gebaute Artefakt**, nicht die Quelldatei — und zwar
  genau das, was sonst erst nach einem erfolgreichen Upload auffiele:

  - der `mcp-name`-Marker in der Wheel-METADATA. Er muss in der Datei stehen,
    die `pyproject.toml` als `readme` deklariert; einer nur in `README.de.md`
    wandert nicht ins Wheel, und ohne ihn kann die MCP-Registry die
    PyPI-Ownership nicht belegen.
  - `server.json` description ≤ 100 Zeichen. Die Registry antwortet sonst mit
    `422` — nach dem PyPI-Upload.
  - Tag == gebaute Version. Ein Re-Run eines alten Tag-Laufs checkt den alten
    Commit aus und reproduziert denselben Fehler, waehrend der Fix im
    Default-Branch unsichtbar bleibt.

  Der Zeitpunkt ist der Punkt: Eine PyPI-Version ist unveraenderlich. Was
  hinterher auffaellt, kostet einen Versionssprung, kein Nachbessern.

### Geaendert

- **`ruff` hat eine Obergrenze bekommen** (`>=0.16,<0.17` statt `>=0.4.0`).
  Ohne sie installiert ein frischer Klon die jeweils neuste Version und
  formatiert anders als das gepinnte `ruff==0.16.1` in `ci.yml`. Genau so kam
  am 3. August ein roter Format-Check an Code zustande, den niemand angefasst
  hatte: lokal mit Standard-Zeilenbreite 88 umgebrochen, waehrend das Projekt
  100 setzt. Beim Anheben gehoeren Grenze und CI-Pin gemeinsam bewegt.

## [0.2.7] - 2026-08-03

### Behoben

- **Der DNS-Retry war nur gegen Mocks belegt.** Die Unit-Tests faelschen
  Aufloeser *und* Antwort; sie zeigen, dass die Schleife tut, was sie soll,
  aber nicht, dass der Aufruf am Ende echte Daten bringt. Genau diese Luecke
  hat den Fehler ueberhaupt erst durchgelassen — gemeldet hat ihn am
  3. August 2026 ein Live-Lauf, nicht die Suite.

  Ein Live-Test faelscht jetzt nur noch den **ersten** Aufloesungsversuch und
  laesst alles danach echt: echtes DNS beim zweiten Versuch, echte Verbindung,
  echte BISTA-Antwort, echte Backoff-Wartezeit. Ein zweiter Live-Test prueft
  die Egress-Blocklist (SEC-005) gegen die echte Antwort des echten Hosts
  statt gegen eine erfundene.

  Zwei Nebenbefunde, beide behoben: Die DNS-Stub-Fixture in
  `tests/test_retry_policy.py` setzt fuer Live-Tests aus (ein «Live»-Test
  gegen einen gestubbten Aufloeser prueft das Gegenteil seines Namens), und
  der gepoolte HTTP-Client wird vor und nach jedem Live-Test frisch gesetzt:
  Seine offenen Verbindungen gehoeren dem Event-Loop, in dem sie entstanden,
  und pytest-asyncio gibt jedem Test einen eigenen. Der zweite Live-Test
  scheiterte deshalb mit «Event loop is closed» — an einem Fehler des
  Testaufbaus, der wie ein Ausfall der Quelle aussieht. Unit-Tests merken
  davon nichts, weil respx die Transport-Schicht ersetzt; latent war es,
  bis ein zweiter Live-Test dazukam.

- **Ein DNS-Zucken beendete den Tool-Aufruf sofort — und wurde als
  Egress-Verstoss gemeldet.** `_resolve_and_validate` warf fuer zwei
  grundverschiedene Lagen denselben `PermissionError`: fuer den
  Policy-Verstoss (Host loest auf eine interne IP auf, SEC-005) **und** fuer
  das Scheitern von `socket.getaddrinfo` («Temporary failure in name
  resolution»). Die Retry-Schleife ueberspringt `PermissionError` bewusst —
  richtig fuer die Politik, falsch fuer den Ausfall. Bei einem Live-Lauf am
  3. August 2026 scheiterten drei Tool-Aufrufe hintereinander genau so; der
  vierte ging durch.

  Die Lagen tragen jetzt eigene Typen, `EgressBlocked` und
  `UpstreamUnresolvable`, beide weiterhin auf `PermissionError` als
  gemeinsamer Basis — bestehende `except`-Klauseln und Tests behalten damit
  ihre Bedeutung, statt still ins Leere zu laufen.

  `UpstreamUnresolvable` wird wiederholt, unter **demselben** Budget,
  derselben Versuchszahl und derselben Backoff-Kurve wie jeder andere
  Ausfall; `EgressBlocked` wird weiterhin nie wiederholt. Damit das Budget
  fuer diesen Pfad auch haelt, laeuft die Aufloesung im Thread-Pool statt im
  Event-Loop: `getaddrinfo` ist synchron, und was den Loop blockiert, kann
  die Wanduhr-Deadline nicht schneiden — aus vier Versuchen waeren sonst vier
  Blockaden ueber das Budget hinaus geworden.

  `_handle_error` trennt die Meldungen: Ein Aufloeser-Ausfall verweist nicht
  mehr auf die Egress-Konfiguration, wo dabei nichts zu finden ist, sondern
  sagt, dass es voruebergehend ist und ein erneuter Versuch die richtige
  Handlung. Die sanitisierte Form bleibt (OBS-002, keine `str(e)`-Leaks).

- **Vier von sechs Datensaetzen waren gegen die echte API kaputt: BISTA hat die
  Schreibweise der Kopfzeile gewechselt.** Der Code las `r["Schulgemeinde"]`,
  die Quelle liefert `schulgemeinde`. Der Zugriff ergab keinen Treffer,
  sondern ein leeres Ergebnis mit der Meldung «Schulgemeinde nicht gefunden» —
  ein Ausfall, der wie eine Antwort aussieht.

  Stand 3. August 2026 liefern vier der sechs genutzten Datensaetze klein,
  zwei gross, und zwei mischen **innerhalb** einer Kopfzeile
  (`gebiet_Bezeichnung`, `staatsangehoerigkeit_ISO2_Code`). Die Schluesselnamen
  werden deshalb beim Parsen normalisiert, statt eine Schreibweise zu waehlen,
  die schon zweimal gewechselt hat.

  Die Unit-Tests haben davon nichts gesehen: Ihre Fixtures pinnen die alte
  Kopfzeile, also blieben sie gruen. Gemeldet hat es allein der Live-Test — den
  CI per `-m "not live"` ausschliesst.

- **Ein Fuenftel der Zeilen liess die Tools abstuerzen.** BISTA unterdrueckt
  kleine Fallzahlen aus Datenschutzgruenden und schreibt statt einer Zahl
  `1 bis 5`; dazu kommen `NULL` und leere Zellen. Betroffen waren 18.6 % der
  Sek-I- und 18.1 % der Staatsangehoerigkeits-Zeilen. `int("1 bis 5")` wirft,
  und der Aufrufer sah davon nur «unerwarteter interner Fehler».

  Solche Werte als 0 zu zaehlen waere die schlechtere Antwort gewesen: Die
  Summe bliebe plausibel, waere still zu tief und durch nichts als falsch
  erkennbar. Sie werden jetzt aus den Summen ausgenommen, in der Tabelle als
  `1 bis 5` gezeigt, und **jede betroffene Ausgabe traegt einen Hinweis**, wie
  viele Zeilen fehlen und dass die echten Werte hoeher liegen (FID-003).

- **`_latest_year` suchte in `Jahr` statt `jahr`** und lieferte darum «Keine
  Jahresdaten verfuegbar» — derselbe Drift, eine Ebene tiefer.

- **`Staatsangehoerigkeit_ISO2_Code` wurde nie gefunden**, weil die Spalte
  gemischt geschrieben ist. Die ISO2-Spalte blieb dauerhaft auf «—».

- **Die `_no_sleep`-Fixture griff weiter, als sie durfte.** Sie patchte
  `http_client.asyncio.sleep` — das sieht lokal aus, trifft aber das *Modul*
  `asyncio` und damit jeden Import im Prozess. Jeder Test, der
  `asyncio.sleep(0)` benutzt, um dem Event-Loop das Wort zu geben, haette
  danach still nichts mehr geprueft: Er laeuft weiter und misst nichts.

  In diesem Repo gibt es derzeit keinen solchen Test, der Schaden war also
  latent. In `srgssr-mcp` ist derselbe Griff in derselben Kampagne
  zugeschnappt und hat eine Parallelitaets-Pruefung entschaerft.

  Der Backoff laeuft jetzt ueber den Modul-Alias `http_client._sleep`, und ein
  Test haelt fest, dass `asyncio.sleep` intakt bleibt.

### Hinzugefuegt

- **Retry-Politik gegenueber BISTA** (ARCH-014). Bisher gab es keine: Ein
  einzelner Netzwerkfehler, ein Timeout oder ein 503 beendete den Tool-Aufruf,
  obwohl der naechste Versuch Sekunden spaeter geklappt haette. Genau so fielen
  am 1. August in `swiss-efv-mcp` vier Live-Tests wegen eines voruebergehenden
  Ausfalls der Quelle.

  Wiederholt werden Netzwerkfehler, Timeouts, 5xx und 429 — vier Versuche. Ein
  4xx ausser 429 ist eine Aussage ueber die Anfrage und keine ueber den Moment
  und scheitert weiterhin sofort. `PermissionError` aus dem Egress-Guard ist
  eine Policy-Entscheidung und wird nie wiederholt: Vier Mal dieselbe verbotene
  Anfrage zu stellen macht sie nicht erlaubter.

- **`Retry-After` wird gelesen und schlaegt die eigene Backoff-Kurve.** Bei 429
  und 503 sagt die Quelle im Header, wann sie wieder mag — als Sekundenzahl
  oder als HTTP-Datum; beide Formen kommen vor, beide werden gelesen
  (RFC 9110 §10.2.3). Ein unbrauchbarer Header fuehrt zurueck auf die Kurve
  statt zum Absturz — auf dem Fehlerpfad ist das der Unterschied zwischen einer
  Verzoegerung und einem zweiten Fehler.

- **Backoff ist gestreut (Jitter).** Eine reine `2**attempt`-Kurve ist
  deterministisch: Faellt BISTA aus, waehrend mehrere Clients es abfragen,
  laufen deren Retries im Gleichtakt, und die Last kommt als Welle zurueck —
  genau wenn die Quelle sich erholt. Exponentielle Wartezeiten landen in
  `[0.5x, 1.5x]`; auf einem `Retry-After` ist die Streuung einseitig
  (`[1.0x, 1.25x]`), weil frueher wiederzukommen die Missachtung derselben
  Angabe waere, die man gerade liest. Deckel von 20 s auf jede Einzelwartezeit,
  angewandt **nach** dem Jittern — die andere Reihenfolge macht den Deckel zu
  gar keiner Schranke.

- **Gesamtbudget von 25 s ueber den ganzen Aufruf.** Eine Versuchszahl ist
  keine Grenze: Vier Versuche a 30 s Timeout plus Backoff sind ueber zwei
  Minuten, und die Zahl `4` sagt das nirgends. Entscheidender ist, dass die
  massgebliche Grenze gar nicht uns gehoert — der Aufrufer hat sein eigenes
  Timeout, und jenseits davon hoert niemand mehr zu. Der Anker ist gemessen:
  Das Python-MCP-SDK setzt `MCP_DEFAULT_TIMEOUT = 30.0`.

  Das Budget haengt an einer `asyncio.timeout`-Deadline, nicht am
  httpx-Timeout: httpx begrenzt pro Operation, und sein Read-Timeout beginnt
  mit jedem Chunk von vorn — eine langsam troepfelnde Antwort wuerde das Budget
  sonst ueberdauern, ohne dass ein einzelner Read ablaeuft.

### Behoben

- **Ein aufgebrauchtes Gesamtbudget las sich als «unerwarteter interner
  Fehler».** Es wirft den builtin `TimeoutError`, `_handle_error` kannte aber
  nur `httpx.TimeoutException`. Fuer den Aufrufer ist beides dasselbe: Es hat
  zu lange gedauert.

## [0.2.6] - 2026-08-02

### Behoben

- **`structlog` hatte keine Obergrenze, und der Index fuehrt bereits einen Major
  oberhalb der Untergrenze.** Deklariert war `structlog>=24.1.0`; auf PyPI liegt
  `26.1.0`. Das Artefakt aendert sich nicht — die Antwort des Resolvers auf
  die naechste frische Installation schon, und genau so wurde
  `swiss-energy-mcp` 0.3.3 uninstallierbar, als `mcp` 2.0.0 das Modul entfernt
  hat, das es importierte.

  Neu `structlog>=24.1.0,<27`. Die Grenze ist gemessen, nicht geraten: dieses Paket installiert
  und importiert heute gegen `structlog 26.1.0`, die Obergrenze laesst also zu,
  was nachweislich funktioniert, und stoppt nur den naechsten, unbekannten
  Major.

- **`starlette` hatte keine Obergrenze, und der Index fuehrt bereits einen Major
  oberhalb der Untergrenze.** Deklariert war `starlette>=0.37.0`; auf PyPI liegt
  `1.3.1`. Das Artefakt aendert sich nicht — die Antwort des Resolvers auf
  die naechste frische Installation schon, und genau so wurde
  `swiss-energy-mcp` 0.3.3 uninstallierbar, als `mcp` 2.0.0 das Modul entfernt
  hat, das es importierte.

  Neu `starlette>=0.37.0,<2`. Die Grenze ist gemessen, nicht geraten: dieses Paket installiert
  und importiert heute gegen `starlette 1.3.1`, die Obergrenze laesst also zu,
  was nachweislich funktioniert, und stoppt nur den naechsten, unbekannten
  Major.

Ein Abhaengigkeitsbereich erreicht die Nutzenden nur ueber ein neues
Release, daher der Versions-Bump. Am Code aendert sich nichts.

## [0.2.5] - 2026-08-02

### Behoben

- **Der Server startete gar nicht mehr.** `zh-education-mcp` ohne Argumente
  brach sofort ab:

  ```
  ValueError: "Settings" object has no field "host"
  ```

  `main()` setzte `mcp.settings.host` und `mcp.settings.port` — ein Rest der
  1.x-API, den die Migration auf das mcp-SDK 2.x uebersehen hat. Unter 2.x
  kennt `MCPServer.settings` nur noch `debug`, `log_level`,
  `warn_on_duplicate_*`, `dependencies`, `lifespan` und `auth`; pydantic wirft
  beim Zuweisen eines unbekannten Feldes.

  Weil die beiden Zeilen **vor** der Transport-Weiche standen, war auch stdio
  betroffen, nicht nur die HTTP-Transporte — also der Standardfall, mit dem
  Claude Desktop den Server startet.

  Die Zeilen sind ersatzlos entfernt: `_run_http` bekommt `host` und `port` als
  Argumente und reicht sie an die App und an `uvicorn.run` weiter. Ueber die
  Settings brauchte sie ohnehin niemand.

- **Kein Test hat je `main()` aufgerufen.** Es gab Import-Tests, aber
  importieren ist nicht starten, und genau dieser Unterschied war der Fehler.
  `tests/test_entrypoint.py` prueft jetzt, dass `main()` den stdio-Transport
  erreicht, dass `--host`/`--port` bis zum HTTP-Start durchkommen, und dass das
  SDK weiterhin kein `host`-Feld in den Settings hat — sollte es zurueckkehren,
  schlaegt der Test fehl und jemand entscheidet bewusst, statt dass die alte
  Zeile still wieder einzieht.

  Gegengeprueft: mit den entfernten Zeilen zurueck im Code schlagen zwei der
  drei Tests fehl.

  Aufgefallen ist der Ausfall beim ersten portfolioweiten Lauf einer Sonde, die
  das installierte Konsolen-Skript **startet** statt es nur zu importieren.

## [0.2.4] - 2026-07-31

### Hinzugefuegt

- **Der Server nennt jetzt seinen Namen.** Bisher ging gegenueber jedem
  Upstream der httpx-Default hinaus: der Betreiber der Datenquelle sah
  eine Bibliothek, nicht uns, und hatte keinen Weg, uns bei Fehlverhalten
  zu erreichen. Neu traegt den HTTP-Client
  `zh-education-mcp/<version> (+github.com/malkreide/zh-education-mcp)`.

  Die Version stammt aus `importlib.metadata` und kann nicht getrennt vom
  Paket driften.

### Fixed

- **`stateless_http` und `json_response` kamen nicht mehr bei der App an
  (SCALE-002/003).** In mcp 1.x waren beide `MCPServer`-Konstruktor-Argumente;
  die Migration auf 2.x hat sie gelöscht, ohne sie als App-Kwargs wieder
  anzuhängen. Das war ein stiller Rückschritt: der Default in `config.py` ist
  `stateless_http: bool = True`, der App-Kwarg-Default ist `False` — der Server
  hielt also wieder Session-State und verlangte Sticky Sessions, während der
  Kommentar in `tools.py` weiterhin Round-Robin ohne Sticky Sessions zusicherte.
  Nichts schlug fehl, weil der Lesepfad, an dem man es gesehen hätte, mit
  verschwunden ist.

  Beide reisen jetzt in `streamable_http_app()`. `sse_app()` bekommt sie nicht:
  SSE hat kein Stateless-Modell und kein JSON-Response-Format.

  Vier neue Tests prüfen die App-Kwargs selbst statt eines Zwischenzustands —
  inklusive eines Falls mit `stateless_http=False`, der beweist, dass der Wert
  durchreist und nicht hartkodiert ist, und eines, der festhält, dass der
  1.x-Lesepfad laut fehlschlägt (`ValueError`) statt still zu verpuffen.
  Mutationsgetestet: entfernt man die Kwargs wieder, fallen genau diese drei.

  Geprüft mit dem wörtlichen CI-Kommando: 55 passed, 1 skipped, 1 deselected;
  `ruff check src/ tests/` clean.


### Fixed

- **Capped `mcp` at `<2`.** `mcp` 2.0.0, published 2026-07-28, removed
  `mcp.server.fastmcp` — the module this server imports. With the previous
  unbounded `>=1.28.1` every fresh resolve picked 2.0.0 and failed at import
  with `ModuleNotFoundError`, in CI and for anyone running `pip install` alike.
  Verified in both directions: 2.0.0 fails, `<2` resolves to 1.29.0 and imports
  cleanly. Migrating to the 2.x API (`mcp.server.mcpserver`) stays a separate,
  deliberate piece of work.

## [0.2.0] - 2026-05-30

Production-Hardening nach MCP-Best-Practice-Audit (Skill v1.0.0, Catalog-Hash `091f446b`).
Audit-Verifikation: **42/42 Checks bestanden · 0 Findings · production-ready** (Run `2026-05-30T072745-Z-zh-education-mcp`).

### Added
- ENV-basierte Konfiguration (`MCP_TRANSPORT`/`MCP_HOST`/`MCP_PORT`/`MCP_CORS_ORIGINS`/`MCP_STATELESS_HTTP`)
- `lifespan`-verwalteter, gepoolter HTTP-Client (Connection-Pooling)
- CORS-Middleware für HTTP-Transporte (exponiert `Mcp-Session-Id`)
- Stateless HTTP (kein Sticky-Session-Routing nötig)
- Multi-Stage-`Dockerfile` (non-root, HEALTHCHECK), `docker-compose.yml` mit Resource-Limits
- `/health`-Endpoint für Load-Balancer- und Container-Probes
- Egress-Allow-List (`frozenset` + httpx-Hook, HTTPS-Zwang, Redirect-Schutz)
- Strukturiertes JSON-Logging auf stderr (`structlog`)
- Strikte Input-Validierung (`strict=True`) auf allen Tool-Modellen
- Context-Injektion (`ctx`) mit Progress-Reports und Logging bei Tool-Calls
- Optionales OpenTelemetry-Tracing pro Tool-Call (`[otel]`-Extra, `MCP_OTEL_ENABLED`)
- DNS-Auflösung + IP-Blocklist-Validierung vor jedem Egress (Anti-Rebinding)
- Dokumentation: `docs/deployment.md`, `docs/network-egress.md`, `docs/security.md`, `docs/secret-management.md`, `docs/roadmap.md`, `docs/accepted-risks.md`, `CONTRIBUTING.de.md`
- Dependabot für monatliche Dependency-Updates

### Changed
- Fehlerbehandlung sanitisiert: Originalfehler nur ins stderr-Log, Client erhält generische Meldung
- Execution-Errors werden als `isError:true` (ToolError) statt als Erfolgs-String signalisiert
- README: Cloud-Endpoint korrigiert (`/mcp` statt `/sse`), Protokoll-/Phasen-Sektion ergänzt

### Security
- SSRF-/Egress-Härtung, Container-Sandboxing, CORS, strikte Validierung (siehe Audit-Findings W1–W3)

### Phase
- Phase 1 (read-only) bestätigt; siehe `docs/roadmap.md`

## [0.1.0] - 2026-04-01

### Added
- Initial release
- `zh_edu_list_schulgemeinden`: List all school communities and Schulkreise in Canton Zurich
- `zh_edu_schulkreis_trend`: Pupil trend by school district (anchor query: Schulkreis Letzi)
- `zh_edu_overview`: Canton-wide learner overview by school level (2000–present)
- `zh_edu_sek1_profil`: Secondary I profile per school community (Sek A/B/C breakdown)
- `zh_edu_staatsangehoerigkeiten`: Nationality structure of pupils per school community
- `zh_edu_maturitaetsquote`: Gymnasium graduation rates by municipality, district, canton
- `zh_edu_wohnort_trend`: Learner trend by place of residence (Bezirk / Gemeinde)
- `zh_edu_mittelschulen`: Secondary school statistics (Gymnasium, FMS, HMS)
- 24h in-memory cache matching annual BISTA update cycle (Stichtag 15. September)
- Dual transport: stdio (Claude Desktop) + SSE (cloud / Railway)
- Pydantic v2 input validation on all tools
- Bilingual documentation: README.md (EN) + README.de.md (DE)
- Mocked test suite with respx (6 unit tests)
- Phase 1: No-auth data sources only (BISTA public API)
