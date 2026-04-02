> 🇨🇭 **Teil des [Swiss Public Data MCP Portfolios](https://github.com/malkreide)**

# 📊 zh-education-mcp

![Version](https://img.shields.io/badge/version-0.1.0-blue)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP](https://img.shields.io/badge/MCP-Model%20Context%20Protocol-purple)](https://modelcontextprotocol.io/)
[![No Auth Required](https://img.shields.io/badge/auth-none%20required-brightgreen)](https://github.com/malkreide/zh-education-mcp)
![CI](https://github.com/malkreide/zh-education-mcp/actions/workflows/ci.yml/badge.svg)

> MCP-Server für Bildungsstatistiken des Kantons und der Stadt Zürich (BISTA)

[🇬🇧 English Version](README.md)

---

## Überblick

`zh-education-mcp` verbindet KI-Assistenten mit der **Bildungsstatistik Kanton Zürich (BISTA)** — den offiziellen Bildungsdaten des Kantons Zürich. Der Server bietet strukturierten Zugang zu Lernendenzahlen, Schulkreis-Trends, Sekundarschulprofilen, Nationalitätenstrukturen und Maturitätsquoten.

| Quelle | Daten | API |
|--------|-------|-----|
| **BISTA Kanton Zürich** | Lernenden-Statistiken (Volksschule, Mittelschulen, Maturität) | REST/CSV |

Alle Daten stammen von der **BISTA Public API** (`bista.zh.ch/basicapi/ogd/`) — kein API-Schlüssel erforderlich. Stichtag: 15. September (jährlich).

**Anker-Abfrage:** *«Wie hat sich die Anzahl Lernender im Schulkreis Letzi in den letzten 5 Jahren entwickelt?»*

---

## Funktionen

- 📊 **8 Tools** für Bildungsdaten über alle Schulstufen
- 🔍 **Schulkreis-Trends** — Lernendenzahlen für alle Schulkreise (Letzi, Glattal, Schwamendingen, Oerlikon, Uto, Waidberg, Zürichberg) ab 2000
- 🏫 **Sekundarschulprofile** — Aufschlüsselung nach Anforderungstyp (Sek A/B/C, Mittelschule, Sonderklassen)
- 🌐 **Nationalitätenstruktur** — Häufigste Staatsangehörigkeiten der Lernenden pro Schulgemeinde
- 🎓 **Maturitätsquoten** — Gymnasiale Maturitätsquote nach Gemeinde, Bezirk und Kanton
- 📈 **Kantonsweite Übersicht** — Alle Lernenden nach Stufe, Schultyp, Geschlecht und Staatsangehörigkeit
- 🏠 **Wohnort-Trends** — Lernendenzahlen nach Wohnort (Bezirk / Gemeinde)
- 🏛️ **Mittelschulen** — Gymnasium, FMS, HMS Statistiken
- 🔓 **Kein API-Schlüssel** — alle Daten unter CC BY 4.0
- ☁️ **Dual Transport** — stdio (Claude Desktop) + Streamable HTTP (Cloud)

---

## Voraussetzungen

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) (empfohlen) oder pip

---

## Installation

```bash
# Repository klonen
git clone https://github.com/malkreide/zh-education-mcp.git
cd zh-education-mcp

# Installieren
pip install -e .
# oder mit uv:
uv pip install -e .
```

Oder mit `uvx` (ohne permanente Installation):

```bash
uvx zh-education-mcp
```

---

## Schnellstart

```bash
# stdio (für Claude Desktop)
python -m zh_education_mcp.server

# Streamable HTTP (Port 8000)
python -m zh_education_mcp.server --http --port 8000
```

Sofort ausprobieren in Claude Desktop:

> *«Wie hat sich die Lernendenzahl im Schulkreis Letzi entwickelt?»*
> *«Zeige die Maturitätsquote der Stadt Zürich»*
> *«Welche Nationalitäten sind in Adliswil am häufigsten?»*

---

## Konfiguration

### Claude Desktop

`~/Library/Application Support/Claude/claude_desktop_config.json` (macOS) oder `%APPDATA%\Claude\claude_desktop_config.json` (Windows) bearbeiten:

```json
{
  "mcpServers": {
    "zh-education": {
      "command": "python",
      "args": ["-m", "zh_education_mcp.server"]
    }
  }
}
```

Oder mit `uvx`:

```json
{
  "mcpServers": {
    "zh-education": {
      "command": "uvx",
      "args": ["zh-education-mcp"]
    }
  }
}
```

### Cloud-Deployment (SSE für Browser-Zugang)

Für die Nutzung via **claude.ai im Browser** (z. B. auf verwalteten Arbeitsplätzen ohne lokale Software):

**Render.com (empfohlen):**
1. Repository auf GitHub pushen/forken
2. Auf [render.com](https://render.com): New Web Service → GitHub-Repo verbinden
3. Start-Kommando: `python -m zh_education_mcp.server --http --port 8000`
4. In claude.ai unter Einstellungen → MCP Servers hinzufügen: `https://your-app.onrender.com/sse`

> 💡 *«stdio für den Entwickler-Laptop, SSE für den Browser.»*

---

## Verfügbare Tools

| Tool | Beschreibung |
|------|-------------|
| `zh_edu_list_schulgemeinden` | Alle Schulgemeinden / Schulkreise im Kanton Zürich auflisten |
| `zh_edu_schulkreis_trend` | Lernenden-Trend nach Schulkreis (ab 2000) |
| `zh_edu_overview` | Kantonsweite Lernenden-Übersicht nach Schulstufe |
| `zh_edu_sek1_profil` | Sekundarstufe-I-Profil (Sek A/B/C Aufschlüsselung) |
| `zh_edu_staatsangehoerigkeiten` | Staatsangehörigkeitsstruktur pro Schulgemeinde |
| `zh_edu_maturitaetsquote` | Gymnasiale Maturitätsquote nach Gemeinde / Bezirk |
| `zh_edu_wohnort_trend` | Lernenden-Trend nach Wohnort (Bezirk / Gemeinde) |
| `zh_edu_mittelschulen` | Mittelschulstatistiken (Gymnasium, FMS, HMS) |

### Beispiel-Abfragen

| Abfrage | Tool |
|---------|------|
| *«Alle Schulkreise in Zürich auflisten»* | `zh_edu_list_schulgemeinden` |
| *«Lernenden-Trend Letzi über 5 Jahre»* | `zh_edu_schulkreis_trend` |
| *«Wie viele Sek A vs Sek B in Winterthur?»* | `zh_edu_sek1_profil` |
| *«Top-Nationalitäten in Zürich-Letzi»* | `zh_edu_staatsangehoerigkeiten` |
| *«Maturitätsquote der Stadt Zürich»* | `zh_edu_maturitaetsquote` |

---

## Architektur

```
┌─────────────────┐     ┌──────────────────────────────┐     ┌──────────────────────────┐
│   Claude / AI   │────▶│  zh-education-mcp            │────▶│  BISTA Kanton Zürich     │
│   (MCP Host)    │◀────│  (MCP Server)                │◀────│  REST/CSV (Public API)   │
└─────────────────┘     │                              │     └──────────────────────────┘
                        │  8 Tools                     │
                        │  Stdio | Streamable HTTP     │
                        │  24h Cache                   │
                        │  Keine Auth erforderlich     │
                        └──────────────────────────────┘
```

---

## Projektstruktur

```
zh-education-mcp/
├── src/zh_education_mcp/
│   ├── __init__.py              # Package
│   └── server.py                # 8 Tools, Cache, Dual Transport
├── tests/
│   └── test_server.py           # Unit-Tests (gemocktes HTTP mit respx)
├── .github/workflows/ci.yml     # GitHub Actions (Python 3.11/3.12/3.13)
├── pyproject.toml
├── CHANGELOG.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md                    # English Version
└── README.de.md                 # Diese Datei (Deutsch)
```

---

## Bekannte Einschränkungen

- **Jährliche Aktualisierung:** BISTA-Daten werden einmal jährlich aktualisiert (Stichtag: 15. September). Der 24h-In-Memory-Cache passt zu diesem Zyklus.
- **CSV-basierte API:** Die BISTA-API liefert CSV-Daten; grosse Datensätze können einen Moment zum Parsen brauchen.
- **Schulgemeinde-Namen:** Namen müssen exakt übereinstimmen (`zh_edu_list_schulgemeinden` zeigt gültige Namen).

---

## Testen

```bash
# Unit-Tests (keine API-Aufrufe)
PYTHONPATH=src pytest tests/ -m "not live"

# Integrationstests (echte API-Aufrufe)
pytest tests/ -m "live"
```

---

## Changelog

Siehe [CHANGELOG.md](CHANGELOG.md)

---

## Mitmachen

Siehe [CONTRIBUTING.md](CONTRIBUTING.md)

---

## Lizenz

MIT-Lizenz — siehe [LICENSE](LICENSE)

---

## Autor

Hayal Oezkan · [malkreide](https://github.com/malkreide)

---

## Credits & Verwandte Projekte

- **BISTA:** [pub.bista.zh.ch](https://pub.bista.zh.ch) — Bildungsstatistik Kanton Zürich (CC BY 4.0)
- **Protokoll:** [Model Context Protocol](https://modelcontextprotocol.io/) — Anthropic / Linux Foundation
- **Verwandt:** [zurich-opendata-mcp](https://github.com/malkreide/zurich-opendata-mcp) — Zürcher Open Data (Parking, Wetter, Parlament)
- **Verwandt:** [swiss-cultural-heritage-mcp](https://github.com/malkreide/swiss-cultural-heritage-mcp) — Schweizer Kulturerbe-Daten
- **Verwandt:** [fedlex-mcp](https://github.com/malkreide/fedlex-mcp) — Schweizer Bundesrecht
- **Portfolio:** [Swiss Public Data MCP Portfolio](https://github.com/malkreide)
