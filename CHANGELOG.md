# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Behoben

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
