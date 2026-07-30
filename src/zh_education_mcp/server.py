#!/usr/bin/env python3
"""
zh-education-mcp — Bildungsstatistik Kanton & Stadt Zürich (BISTA)

AI-nativer Zugang zu den Bildungsstatistiken des Kantons Zürich:
  · Lernende nach Schulgemeinde, Schulkreis, Stufe und Anforderungstyp
  · Maturitätsquoten nach Gemeinde, Bezirk und Kanton
  · Staatsangehörigkeiten der Lernenden
  · Mittelschulstatistiken (Gymnasium, FMS, HMS)

Datenquelle: BISTA Public API (bista.zh.ch/basicapi/ogd/)
Kein API-Schlüssel erforderlich. Stichtag: 15. September (jährlich).

Dieses Modul ist die schlanke Kompositions-/Einstiegsschicht. Die Logik ist
auf fokussierte Submodule aufgeteilt (ARCH-011):

  · config         — ENV-Settings
  · constants       — API-Basis, Endpunkte, Timeouts
  · logging_setup   — strukturiertes stderr-Logging
  · provenance      — Response-Envelope, Lizenz-Attribution, ResponseFormat
  · http_client     — Egress-Guard, Connection-Pool, Lifespan
  · data            — Cache, CSV-Fetch, Filter, Fehler-Sanitisierung
  · models          — Pydantic-Input-Modelle
  · tools           — MCPServer-Instanz + die 8 Tools
"""

from __future__ import annotations

import sys

# Re-Exports für Abwärtskompatibilität (`from zh_education_mcp.server import ...`).
# Die Logik lebt in Submodulen; dieses Modul bündelt sie. F401/F403 bewusst
# unterdrückt, da es sich um absichtliche Re-Exports handelt.
from .config import Settings, settings  # noqa: F401
from .constants import (  # noqa: F401
    BISTA_API,
    CACHE_TTL,
    EP_MATURITAET,
    EP_MITTELSCHULEN,
    EP_NAT_REGIONAL,
    EP_SEK1,
    EP_UEBERSICHT,
    EP_WOHNORT,
    HTTP_TIMEOUT,
)
from .data import (  # noqa: F401
    _cache,
    _fetch_csv,
    _filter_rows,
    _handle_error,
    _latest_year,
)
from .http_client import (  # noqa: F401
    ALLOWED_HOSTS,
    AppContext,
    _egress_guard,
    _get_client,
    _http_get,
    lifespan,
)
from .logging_setup import log  # noqa: F401
from .models import (  # noqa: F401
    ListSchulgemeindensInput,
    MaturitaetsquoteInput,
    MittelschulenInput,
    SchulkreisTrendInput,
    Sek1ProfilInput,
    StaatsangehoerigkeitInput,
    UebersichtInput,
    WohnortTrendInput,
)
from .provenance import (  # noqa: F401
    PROVENANCE,
    SOURCE_LICENSE,
    SOURCE_NAME,
    SOURCE_URL,
    ResponseFormat,
    _envelope,
    _not_found,
    _source_footer,
)
from .tools import (  # noqa: F401
    mcp,
    zh_edu_list_schulgemeinden,
    zh_edu_maturitaetsquote,
    zh_edu_mittelschulen,
    zh_edu_overview,
    zh_edu_schulkreis_trend,
    zh_edu_sek1_profil,
    zh_edu_staatsangehoerigkeiten,
    zh_edu_wohnort_trend,
)

__all__ = [
    "ALLOWED_HOSTS",
    "AppContext",
    "BISTA_API",
    "CACHE_TTL",
    "HTTP_TIMEOUT",
    "PROVENANCE",
    "ResponseFormat",
    "SOURCE_LICENSE",
    "SOURCE_NAME",
    "SOURCE_URL",
    "Settings",
    "ListSchulgemeindensInput",
    "MaturitaetsquoteInput",
    "MittelschulenInput",
    "Sek1ProfilInput",
    "SchulkreisTrendInput",
    "StaatsangehoerigkeitInput",
    "UebersichtInput",
    "WohnortTrendInput",
    "main",
    "mcp",
    "settings",
    "log",
    "zh_edu_list_schulgemeinden",
    "zh_edu_maturitaetsquote",
    "zh_edu_mittelschulen",
    "zh_edu_overview",
    "zh_edu_schulkreis_trend",
    "zh_edu_sek1_profil",
    "zh_edu_staatsangehoerigkeiten",
    "zh_edu_wohnort_trend",
]


# ─────────────────────────── Einstiegspunkt ────────────────────────────────────
def main() -> None:
    """Startet den Server.

    Konfiguration primär über ENV-Vars (``MCP_TRANSPORT``/``MCP_HOST``/``MCP_PORT``).
    CLI-Flags ``--http``/``--sse``/``--port``/``--host`` überschreiben die ENV-Werte
    (Abwärtskompatibilität mit der README-Doku). Default bleibt lokal: stdio + Loopback.
    """
    from .telemetry import setup_telemetry

    setup_telemetry()  # opt-in via MCP_OTEL_ENABLED; No-Op sonst (OBS-006)

    transport = settings.transport
    host = settings.host
    port = settings.port

    argv = sys.argv[1:]
    for i, arg in enumerate(argv):
        if arg == "--http":
            transport = "streamable-http"
        elif arg == "--sse":
            transport = "sse"
        elif arg == "--port" and i + 1 < len(argv):
            port = int(argv[i + 1])
        elif arg == "--host" and i + 1 < len(argv):
            host = argv[i + 1]

    # Netzwerk-Binding nur für HTTP-Transporte relevant.
    mcp.settings.host = host
    mcp.settings.port = port

    if transport in ("streamable-http", "sse"):
        _run_http(transport, host, port)
    else:
        mcp.run(transport="stdio")


def build_transport_security(host: str, port: int):
    """Host/Origin-Allow-List für die HTTP-Transporte (SEC-005, eingehend).

    Ohne ``transport_security`` lässt das SDK den DNS-Rebinding-Schutz **aus** —
    es sagt das selbst: "If not specified, disable DNS rebinding protection by
    default for backwards compatibility". Ein ungesetzter Wert heisst also:
    keinerlei Host- oder Origin-Prüfung.

    Rückgabe ``None``, wenn die Allow-List nicht bestimmbar ist. Das ist genau
    der Fall "Nicht-Loopback-Bind ohne ``MCP_ALLOWED_HOSTS``": der Server wird
    dann unter einem Service- oder DNS-Namen erreicht, den dieser Prozess nicht
    kennt, und eine geratene Liste würde jede echte Anfrage mit HTTP 421
    abweisen. Der Aufrufer warnt in dem Fall.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    loopback = {f"127.0.0.1:{port}", f"localhost:{port}", f"[::1]:{port}"}
    if settings.allowed_host_list:
        # Loopback bleibt für Health-Checks und lokales Debugging erreichbar.
        hosts = set(settings.allowed_host_list) | loopback
    elif host in ("127.0.0.1", "localhost", "::1"):
        hosts = loopback | {f"{host}:{port}"}
    else:
        return None

    # Die konfigurierten CORS-Origins müssen auch die Transport-Prüfung
    # passieren, sonst weist der Server Browser-Clients ab, die CORS erlaubt.
    origins = set(settings.cors_origin_list) | {f"http://{h}" for h in hosts}
    return TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=sorted(hosts),
        allowed_origins=sorted(origins),
    )


def _run_http(transport: str, host: str, port: int) -> None:
    """Startet einen HTTP-Transport mit CORS-Middleware (SDK-004).

    Die Starlette-App wird um ``CORSMiddleware`` gewickelt, die ``Mcp-Session-Id``
    explizit exponiert und akzeptiert (sonst brechen Browser-Clients wie claude.ai).
    Origins kommen aus ``MCP_CORS_ORIGINS`` — keine Wildcard in Produktion.
    """
    import logging

    import uvicorn
    from starlette.middleware.cors import CORSMiddleware

    security = build_transport_security(host, port)
    if security is None:
        logging.getLogger("zh_education_mcp").warning(
            "DNS-Rebinding-Schutz ist AUS: Bind auf %s ist nicht Loopback und "
            "MCP_ALLOWED_HOSTS ist leer. Setze MCP_ALLOWED_HOSTS auf die "
            "Hostnamen, unter denen dieser Server erreichbar ist "
            "(z. B. mcp.example.ch), damit Host und Origin geprüft werden.",
            host,
        )
    # mcp 2.x: transport_security, stateless_http und json_response sind
    # per-App-Kwargs, keine Settings mehr. `stateless_http` muss hier stehen:
    # es war in 1.x ein MCPServer-Konstruktor-Argument, der Default in
    # `config.py` ist `True`, und der App-Kwarg-Default ist `False` — ohne diese
    # Zeile kippt SCALE-002/003 still ins Gegenteil und der Server braucht
    # wieder Sticky Sessions.
    # `sse_app()` nimmt beide nicht: SSE hat kein Stateless-Modell und kein
    # JSON-Response-Format, deshalb nur im Streamable-HTTP-Zweig.
    app = (
        mcp.sse_app(transport_security=security, host=host)
        if transport == "sse"
        else mcp.streamable_http_app(
            transport_security=security,
            host=host,
            stateless_http=settings.stateless_http,
            json_response=settings.json_response,
        )
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Mcp-Session-Id", "Last-Event-ID"],
        expose_headers=["Mcp-Session-Id"],
        max_age=86_400,
    )
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
