# zh-education-mcp v0.3.0 — Nativ auf MCP-Spec 2026-07-28

Erstes Release, in dem der Server die Revision `2026-07-28` nicht nur *spricht*,
sondern auch bedient: die Auskünfte, die ein Server über sich selbst geben muss,
stehen jetzt auf dem Draht statt leer zu bleiben. Dazu eine Datenkorrektur, die
jede Maturitätsquote betraf, und Fixtures, die aufgezeichnet statt ausgedacht sind.

Alle Gates grün auf Python 3.11 / 3.12 / 3.13.

## ✨ Highlights

### MCP-Spec 2026-07-28 — nativ statt geerbt

- **`serverInfo`-Stempel auf jeder Antwort der modernen Ära** (Spec #3002) mit
  Name, Titel, Version, Beschreibung und Website. Vorher stand dort
  `version: ""` — `Implementation.version` ist im Typ der Revision ein
  Pflichtfeld, und das SDK setzt nichts ein.
- **`server/discover` antwortet mit `instructions`** («Servers **MUST**
  implement»). Inhalt: Stichtag, unterdrückte Fallzahlen, Attributionspflicht,
  Lese-Beschränkung — bewusst das, was in keiner Tool-Beschreibung steht.
- **Neues Modul `identity.py`.** Version, Beschreibung und Website kommen aus
  den Distributions-Metadaten und damit aus `pyproject.toml`, nicht aus
  Literalen.
- **Frischehinweise (SEP-2549)** auf allen cachebaren Verzeichnis-Methoden
  (`ttlMs` 300 000, `cacheScope` `public`); `resources/read` bewusst ohne.
  `prompts/list` fehlte bisher und antwortete mit `ttlMs: 0`.
- **CORS-Preflight repariert:** Die Freigabeliste nannte keinen der Header, über
  die `2026-07-28` eine Anfrage routet (`Mcp-Method`, `Mcp-Name`,
  `Mcp-Protocol-Version`). Browser-Clients starben vor dem ersten MCP-Byte,
  während stdio und Python weiterliefen.

### Datenkorrektheit

- **Maturitätsquote war um den Faktor 100 zu hoch.** Jede ausgegebene Quote
  betroffen.
- **«19-Jährige» stand seit dem Kopfzeilen-Fix in jeder Zeile auf «—».**
- **Gelesene Feldnamen werden bestätigt, nicht nur normalisiert.** Lehre aus dem
  BISTA-Wechsel `Schulgemeinde` → `schulgemeinde` vom 3.8.2026: vier von sechs
  Datensätzen produktiv kaputt, alle Unit-Tests grün.

### Tests & Betrieb

- **Die moderne Protokoll-Ära wird zum ersten Mal gemessen**
  (`tests/test_modern_protocol.py`, 16 Fälle): echte `2026-07-28`-Umschläge über
  HTTP durch den zusammengebauten ASGI-Stack, Leiter-Abweisungen
  (`-32602` / `-32020` / `-32022`), plus Gegenprobe, dass die Handshake-Ära
  `resultType` und Stempel **nicht** trägt.
- **Beide Protokoll-Ären sind einzeln gepinnt** (`tests/test_protocol_version.py`);
  ein Dependabot-Bump von `mcp` kann keine still verschieben.
- **Fixtures sind aufgezeichnet, mit Aufnahmedatum**, statt handgeschrieben.
- **Live-Suite läuft geplant** (`live-tests.yml`, wöchentlich) und wird von
  `scripts/classify_live_run.py` aus dem JUnit-XML eingeordnet, nicht mehr am
  Exit-Code: ein Lauf, in dem *jeder* Test übersprungen wurde, endet mit 0 und
  hätte vorher fälschlich Entwarnung gegeben.
- **SessionStart-Hook** meldet einen veralteten Klon, mit 16 eigenen Tests
  (`tests/test_session_start_hook.py`, gegen echte Wegwerf-Repos, ohne Netz).
- **`ruff` hat jetzt genau eine Quelle** (`pyproject.toml`, `dev`-Extra) und ein
  Gate, das prüft, ob das *aufgerufene* `ruff` der gepinnte ist: ein älteres im
  `PATH` schlägt den Pin, ohne dass der Install etwas meldet.
- **TLS-Import-Sonde** (`workflow_dispatch`) macht einen Verdacht auf ein TLS-
  oder Import-Problem gegen die Quelle prüfbar.

## Protokoll-Ären

Der Server bedient beide über denselben Endpunkt; die erste Anfrage einer
Verbindung entscheidet:

| Ära | Revision |
|---|---|
| `initialize`-Handshake | `2024-11-05` … `2025-11-25` |
| Pro-Request-Envelope | `2026-07-28` |

## Keine Breaking Changes

Tool-Namen und -Signaturen sind unverändert, der stdio-Default-Betrieb
funktioniert wie zuvor. Clients der Handshake-Ära sehen die neuen Felder nicht —
`serverInfo`-Stempel und `resultType` gehören der modernen Ära und erscheinen
dort auch nicht.

**Full Changelog:** https://github.com/malkreide/zh-education-mcp/compare/v0.2.7...v0.3.0
