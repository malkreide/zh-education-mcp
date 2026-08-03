"""Konstanten: API-Basis, Timeouts, Cache-TTL, BISTA-Endpunkte."""

from __future__ import annotations

BISTA_API = "https://www.bista.zh.ch/basicapi/ogd"
HTTP_TIMEOUT = 30.0
CACHE_TTL = 86_400  # 24 Stunden — passend zum jährlichen Stichtag

# --- Retry-Politik gegenüber BISTA (ARCH-014) --------------------------------
# Drei Fragen muss ein Retry beantworten: *was* wird wiederholt, *wie schnell*
# und *wie lange*. Die erste klärt die Schleife in ``http_client`` (4xx ausser
# 429 scheitert sofort); diese Konstanten klären die anderen beiden.

RETRY_ATTEMPTS = 4

# Deckel über den *ganzen* Aufruf — alle Versuche und alle Wartezeiten zusammen.
#
# Eine Versuchszahl ist keine Grenze: Vier Versuche à 30 s Timeout plus Backoff
# sind über zwei Minuten, und die Zahl 4 sagt das nirgends. Entscheidender ist,
# dass die massgebliche Grenze gar nicht uns gehört — der Aufrufer hat sein
# eigenes Timeout, und jenseits davon hört niemand mehr zu: Die Arbeit läuft
# weiter, die Last landet bei BISTA, das Ergebnis geht ins Leere.
#
# Der Anker ist gemessen, nicht geschätzt: Das Python-MCP-SDK setzt
# ``MCP_DEFAULT_TIMEOUT = 30.0`` (``mcp/shared/_httpx_utils.py``). 25 s lassen
# Luft für MCP-Framing, CSV-Parsing und die Tool-Schicht über dem Abruf.
#
# ``HTTP_TIMEOUT`` liegt bewusst darüber: Es begrenzt eine einzelne Operation,
# das Budget den Aufruf. Wirksam ist pro Versuch das Kleinere von beidem.
RETRY_TOTAL_BUDGET = 25.0

# Deckel für eine einzelne Wartezeit. Sichert zweierlei zugleich: eine
# Exponentialleiter, die sonst unbegrenzt wächst, und ein ``Retry-After``, das
# die Quelle senden darf, das man aber nicht absitzen muss.
RETRY_MAX_DELAY = 20.0

RETRY_BACKOFF_BASE = 2.0

# Streuung. Ohne sie retryen alle Clients, die denselben Ausfall getroffen
# haben, im Gleichtakt, und die Last kommt als Welle zurück — genau wenn die
# Quelle sich erholt. Der Retry-Sturm verlängert den Ausfall, den er
# überbrücken soll.
RETRY_JITTER_SPREAD = 0.5  # exponentielle Wartezeiten landen in [0.5x, 1.5x]

# Auf einem ``Retry-After`` einseitig: Die Quelle hat gesagt, wann wir
# wiederkommen sollen — später ist höflich, früher wäre die Missachtung
# derselben Angabe, die man gerade liest.
RETRY_AFTER_JITTER = 0.25  # landet in [1.0x, 1.25x]

# Status, die ein sinnvolles ``Retry-After`` tragen (RFC 9110 §10.2.3). Ein 429
# oder 503 ist die Quelle, die sagt «nicht jetzt, versuch es um T» — eine
# Antwort auf genau die Frage, die die Backoff-Kurve rät.
RETRY_AFTER_STATUSES = frozenset({429, 503})

# Endpunkte
EP_SEK1 = "data_lernende_sekundarstufe_i_anforderungstyp"
EP_UEBERSICHT = "data_uebersicht_alle_lernende"
EP_NAT_REGIONAL = "data_lernende_regelschule_regional_staatsangehoerigkeit"
EP_MATURITAET = "data_maturitaetsquote_gemeinden_und_kanton"
EP_WOHNORT = "data_lernende_nach_wohngemeinde"
EP_MITTELSCHULEN = "data_lernende_mittelschulen"
