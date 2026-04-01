# zh-education-mcp

![Version](https://img.shields.io/badge/version-0.1.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Python](https://img.shields.io/badge/python-3.11+-blue)
![MCP](https://img.shields.io/badge/MCP-FastMCP-purple)
![Data](https://img.shields.io/badge/data-BISTA%20Kanton%20ZH-orange)

> MCP server for education statistics of the Canton and City of Zurich (BISTA)

[ð©ðª Deutsche Version](README.de.md)

---

> **Part of the [Swiss Public Data MCP Portfolio](https://github.com/malkreide)**
> â connecting AI models to Swiss public data sources.

---

## Overview

`zh-education-mcp` connects AI assistants to the **Bildungsstatistik Kanton ZÃ¼rich (BISTA)** â the official education statistics of the Canton of Zurich. It provides structured access to pupil numbers, school district trends, secondary school profiles, nationality breakdowns, and gymnasium graduation rates.

The server directly bridges the gap between Swiss education data and AI reasoning â enabling queries like:

> *"How has the number of pupils in school district Letzi developed over the last 5 years?"*

All data is fetched from the **BISTA public API** (`bista.zh.ch/basicapi/ogd/`) â no API key required. Data is updated annually on 15 September (reference date).

## Features

- ð **School district trends** â pupil numbers for all Schulkreise (incl. Zurich districts: Letzi, Glattal, Schwamendingen, Oerlikon, Uto, Waidberg, ZÃ¼richberg) from 2000 to present
- ð« **Secondary school profiles** â breakdown by requirement type (Sek A/B/C, Mittelschule, special classes) per Schulgemeinde
- ð **Nationality structure** â top nationalities of pupils per school community
- ð **Gymnasium graduation rates** â by municipality, district, and canton
- ð **Canton-wide overview** â all learners by school level, type, gender, and nationality
- ð  **Residence-based trends** â pupil counts by place of residence (Bezirk / Gemeinde)
- ðï¸ **Secondary schools** â Gymnasium, FMS, HMS statistics

## Prerequisites

- Python 3.11+
- `uv` (recommended) or `pip`
- Claude Desktop or any MCP-compatible host

## Installation

```bash
pip install zh-education-mcp
```

## Claude Desktop

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

## Tools

| Tool | Description |
|------|-------------|
| `zh_edu_list_schulgemeinden` | List all school communities/districts |
| `zh_edu_schulkreis_trend` | â£ Pupil trend by Schulkreis (2000âpresent) |
| `zh_edu_overview` | Canton-wide learner overview |
| `zh_edu_sek1_profil` | Secondary I profile (Sek A/B/C) |
| `zh_edu_staatsangehoerigkeiten` | Nationality breakdown |
| `zh_edu_maturitaetsquote` | Gymnasium graduation rates |
| `zh_edu_wohnort_trend` | Residence-based learner trend |
| `zh_edu_mittelschulen` | Secondary school statistics |

## License

MIT License â see [LICENSE](LICENSE)

## Author

malkreide Â· [GitHub](https://github.com/malkreide)

---

*Data provided by [Bildungsstatistik Kanton ZÃ¼rich BISTA)](https://pub.bista.zh.ch) under open data license (CC BY 4.0).*
