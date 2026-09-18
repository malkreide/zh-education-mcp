"""Was dieser Server auf dem 2026-07-28-Draht wirklich tut.

Bis hierher wurde die moderne Aera im Repo nur *behauptet*: `README` und
`CHANGELOG` beschreiben sie, `tests/test_protocol_version.py` misst den
`initialize`-Handshake — also genau die ANDERE Aera — und
`tests/test_cache_hints.py` fragt ueber eine In-Process-`ClientSession`, die
sich ihre Revision selbst aussucht. Keine Zeile fuhr je einen Umschlag nach
`2026-07-28` ueber HTTP durch diesen Server.

Diese Datei tut es, und sie tut es ueber den zusammengebauten ASGI-Stack aus
`build_http_app`, nicht ueber eine Abkuerzung. Der Unterschied ist nicht
theoretisch: der Umschlag wird zur Haelfte aus HTTP-Headern geprueft
(`Mcp-Protocol-Version`, `Mcp-Method`, `Mcp-Name`), und eine In-Process-Sitzung
hat keine.

Drei Sorten Zusicherung stehen hier, und die Reihenfolge ist Absicht:

1. **Die Leiter greift** — ein defekter Umschlag wird benannt abgewiesen. Das
   ist der Beleg, dass die Anfrage ueberhaupt den modernen Weg genommen hat.
   Ohne ihn waere jede gruene Antwort unten auch mit einem Server vereinbar,
   der den Umschlag schlicht ignoriert.
2. **Die Antwort traegt die Pflichtfelder der Revision** — `resultType` und den
   `serverInfo`-Stempel.
3. **Die Gegenprobe:** die Handshake-Aera traegt beides NICHT. Ohne sie
   pruefte (2) nur, dass irgendein Feld da ist, nicht dass es die Revision
   ist, die es hinlegt.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest
from mcp.shared.inbound import (
    MCP_METHOD_HEADER,
    MCP_NAME_HEADER,
    MCP_PROTOCOL_VERSION_HEADER,
)
from mcp_types import (
    CLIENT_CAPABILITIES_META_KEY,
    CLIENT_INFO_META_KEY,
    PROTOCOL_VERSION_META_KEY,
    SERVER_INFO_META_KEY,
)
from mcp_types.jsonrpc import HEADER_MISMATCH, INVALID_PARAMS, UNSUPPORTED_PROTOCOL_VERSION
from mcp_types.version import LATEST_MODERN_VERSION

from zh_education_mcp.identity import (
    SERVER_DESCRIPTION,
    SERVER_NAME,
    SERVER_TITLE,
    SERVER_VERSION,
    SERVER_WEBSITE_URL,
)
from zh_education_mcp.server import build_http_app

MODERN = "2026-07-28"


def _envelope(
    method: str, params: dict[str, Any] | None = None, *, version: str = MODERN
) -> dict[str, Any]:
    """Ein JSON-RPC-Body mit dem Pro-Request-`_meta`-Umschlag der Revision."""
    payload = dict(params or {})
    payload["_meta"] = {
        PROTOCOL_VERSION_META_KEY: version,
        CLIENT_CAPABILITIES_META_KEY: {},
        CLIENT_INFO_META_KEY: {"name": "modern-test-client", "version": "1"},
    }
    return {"jsonrpc": "2.0", "id": 1, "method": method, "params": payload}


async def _post(body: dict[str, Any], headers: dict[str, str]) -> tuple[int, dict[str, Any]]:
    """Eine Anfrage durch den echten ASGI-Stack; Status und geparster Body."""
    app = build_http_app("streamable-http", "127.0.0.1", 8000)
    base = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "Host": "127.0.0.1:8000",
    }
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1:8000"
        ) as client:
            response = await client.post("/mcp", headers={**base, **headers}, json=body)
    text = response.text
    for line in text.splitlines():  # SSE-Rahmen abstreifen, falls vorhanden
        if line.startswith("data: "):
            text = line[len("data: ") :]
    return response.status_code, json.loads(text)


async def _modern(method: str, params: dict[str, Any] | None = None, **overrides: str):
    """Eine wohlgeformte moderne Anfrage; `overrides` verbiegt einzelne Header."""
    headers = {
        MCP_PROTOCOL_VERSION_HEADER: MODERN,
        MCP_METHOD_HEADER: method,
        **overrides,
    }
    return await _post(_envelope(method, params), headers)


# ── 1. Die Leiter greift ───────────────────────────────────────────────────────


async def test_ein_body_ohne_umschlag_wird_benannt_abgewiesen() -> None:
    """Der wichtigste Test der Datei: er belegt, dass der Umschlag GEPRUEFT wird.

    Ohne ihn koennten alle Zusicherungen weiter unten auch von einem Server
    kommen, der `params._meta` gar nicht ansieht und jede Anfrage auf demselben
    Weg beantwortet. Dann waere «nativ auf 2026-07-28» ein Satz im README und
    sonst nichts.
    """
    status, body = await _post(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        {MCP_PROTOCOL_VERSION_HEADER: MODERN, MCP_METHOD_HEADER: "tools/list"},
    )
    assert status == 400, body
    assert body["error"]["code"] == INVALID_PARAMS


async def test_ein_header_der_dem_body_widerspricht_wird_abgewiesen() -> None:
    """`Mcp-Method` ist kein Schmuck: eine Zwischenstation routet danach.

    Stimmt der Header nicht mit dem Body ueberein, haben Zwischenstation und
    Server verschiedene Anfragen vor sich. Die Revision laesst das nicht
    durchgehen, und dieser Server auch nicht.
    """
    status, body = await _post(
        _envelope("tools/list"),
        {MCP_PROTOCOL_VERSION_HEADER: MODERN, MCP_METHOD_HEADER: "resources/list"},
    )
    assert status == 400, body
    assert body["error"]["code"] == HEADER_MISMATCH


async def test_ein_name_header_der_dem_body_widerspricht_wird_abgewiesen() -> None:
    """Dasselbe fuer `Mcp-Name` — den Header, an dem ein Gateway entscheidet,
    WELCHES Werkzeug gerufen wird. Ein Server, der ihn ungeprueft laesst, laedt
    genau die Verwechslung ein, gegen die es ihn gibt."""
    status, body = await _post(
        _envelope("tools/call", {"name": "zh_edu_list_schulgemeinden", "arguments": {}}),
        {
            MCP_PROTOCOL_VERSION_HEADER: MODERN,
            MCP_METHOD_HEADER: "tools/call",
            MCP_NAME_HEADER: "zh_edu_maturitaetsquote",
        },
    )
    assert status == 400, body
    assert body["error"]["code"] == HEADER_MISMATCH


async def test_eine_unbekannte_moderne_revision_wird_mit_der_liste_beantwortet() -> None:
    """Eine Absage, die sagt, was ginge — nicht bloss, dass es nicht geht.

    Der Fehler traegt `supported`; ein Client kann daraus selbst waehlen,
    statt zu raten oder aufzugeben.
    """
    status, body = await _post(
        _envelope("tools/list", version="2099-01-01"),
        {MCP_PROTOCOL_VERSION_HEADER: "2099-01-01", MCP_METHOD_HEADER: "tools/list"},
    )
    assert status == 400, body
    assert body["error"]["code"] == UNSUPPORTED_PROTOCOL_VERSION
    assert MODERN in body["error"]["data"]["supported"]


# ── 2. Die Antwort traegt die Pflichtfelder der Revision ───────────────────────


@pytest.mark.parametrize(
    "method", ["server/discover", "tools/list", "resources/list", "prompts/list"]
)
async def test_jede_antwort_traegt_resulttype(method: str) -> None:
    """«Servers implementing this protocol version MUST include this field.»

    Wortlaut aus `DiscoverResult.resultType` im SDK-Typ der Revision. Ein
    Client darf ohne dieses Feld nicht wissen, wie er das Ergebnis liest.
    """
    status, body = await _modern(method)
    assert status == 200, body
    assert body["result"]["resultType"] == "complete"


@pytest.mark.parametrize("method", ["server/discover", "tools/list", "resources/list"])
async def test_jede_antwort_traegt_die_server_identitaet(method: str) -> None:
    """Der Stempel aus Spec #3002 — und der Grund, warum es `identity.py` gibt.

    Vor dieser Aenderung trug er `{"name": "zh_education_mcp", "version": ""}`
    und sonst nichts: kein Titel, keine Beschreibung, keine Website. Die leere
    Version war nicht die Voreinstellung des SDK, sondern unsere Auslassung —
    «An unversioned server reports an empty `version`; the SDK never
    substitutes its own» (`mcp/server/lowlevel/server.py`).
    """
    status, body = await _modern(method)
    assert status == 200, body
    stamp = body["result"]["_meta"][SERVER_INFO_META_KEY]
    assert stamp == {
        "name": SERVER_NAME,
        "title": SERVER_TITLE,
        "version": SERVER_VERSION,
        "description": SERVER_DESCRIPTION,
        "websiteUrl": SERVER_WEBSITE_URL,
    }


async def test_die_gestempelte_version_ist_keine_leere_zeichenkette() -> None:
    """Die Regression, die diese Datei ueberhaupt ausgeloest hat, einzeln benannt.

    `test_jede_antwort_traegt_die_server_identitaet` faellt auch, wenn nur der
    Titel fehlt — die Meldung zeigt dann nicht, dass der lasttragende Fall die
    Version ist. `Implementation.version` ist im Typ der Revision ein
    Pflichtfeld; `""` erfuellt es formal und sagt nichts.
    """
    _, body = await _modern("tools/list")
    version = body["result"]["_meta"][SERVER_INFO_META_KEY]["version"]
    assert version, "der Server stempelt eine leere Version auf jede Antwort"


async def test_server_discover_nennt_die_moderne_revision() -> None:
    """`server/discover` ist der Einstieg der Revision («Servers **MUST**
    implement `server/discover`») und die einzige Stelle, an der ein Client
    ohne Handshake erfaehrt, was gesprochen wird."""
    status, body = await _modern("server/discover")
    assert status == 200, body
    assert MODERN in body["result"]["supportedVersions"]


async def test_server_discover_traegt_die_instructions() -> None:
    """Das Feld, das dem Modell sagt, WIE dieser Server zu benutzen ist.

    Es stand bis zu dieser Aenderung auf `null`. Die Spec beschreibt es als
    «guidance […] that helps the model use the server effectively and should
    not duplicate information already in tool descriptions» — der Stichtag und
    die unterdrueckten Fallzahlen stehen in keiner Tool-Beschreibung, und ohne
    sie liest ein Modell eine Untergrenze als Summe.
    """
    status, body = await _modern("server/discover")
    assert status == 200, body
    instructions = body["result"]["instructions"]
    assert instructions, "server/discover antwortet ohne instructions"
    assert "15. September" in instructions
    assert "1 bis 5" in instructions


# ── 3. Gegenprobe: die Handshake-Aera traegt beides nicht ──────────────────────


async def test_die_handshake_aera_bleibt_ungestempelt() -> None:
    """Ohne diesen Test misst der Abschnitt oben nur, dass irgendwo Felder sind.

    Der `serverInfo`-Stempel und `resultType` gehoeren der Revision
    `2026-07-28`; auf einer Handshake-Verbindung darf beides NICHT erscheinen —
    ein Client dieser Aera kennt die Vokabeln nicht. Faellt dieser Test, hat
    das SDK die Aeren zusammengelegt, und die Aufteilung in
    `tests/test_protocol_version.py` ist neu zu bewerten.
    """
    status, body = await _post(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "legacy-client", "version": "1"},
            },
        },
        {},
    )
    assert status == 200, body
    result = body["result"]
    assert result["protocolVersion"] == "2025-06-18"
    assert "resultType" not in result
    assert SERVER_INFO_META_KEY not in (result.get("_meta") or {})
    # Die Identitaet ist deshalb nicht weg — sie steht dort, wo diese Aera sie
    # erwartet, und traegt dieselben Werte wie der Stempel oben.
    assert result["serverInfo"]["version"] == SERVER_VERSION
    assert result["instructions"]


def test_die_moderne_revision_ist_die_des_sdk() -> None:
    """Der Pin dieser Datei gegen den des SDK.

    `tests/test_protocol_version.py` haelt `LATEST_MODERN_VERSION` gegen die
    READMEs; diese Datei baut ihre Umschlaege aus einem eigenen Literal. Ohne
    diese Zeile koennten beide auseinanderlaufen, und die Tests oben wuerden
    dann eine Revision messen, die der Server gar nicht mehr fuehrt.
    """
    assert MODERN == LATEST_MODERN_VERSION
