"""Der Einstiegspunkt muss den Transport erreichen.

Bis 0.2.4 tat er das nicht. `main()` setzte `mcp.settings.host` — ein Rest der
1.x-API, den die Migration auf mcp 2.x übersehen hat. Unter 2.x hat
`MCPServer.settings` dieses Feld nicht mehr, pydantic wirft beim Zuweisen, und
weil die Zeile **vor** der Transport-Weiche stand, starb `zh-education-mcp`
ohne Argumente, bevor stdio überhaupt an die Reihe kam:

    ValueError: "Settings" object has no field "host"

Kein Test hat je `main()` aufgerufen. Import-Tests gab es, aber importieren ist
nicht starten — und der Unterschied war hier genau der Fehler.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def calls(monkeypatch):
    """Fängt den Transport-Aufruf ab, statt wirklich zu starten."""
    from zh_education_mcp import server as srv

    recorded: dict[str, object] = {}
    monkeypatch.setattr(srv.mcp, "run", lambda **kw: recorded.update(kw))
    monkeypatch.setattr(srv, "_run_http", lambda *a: recorded.update(http=a))
    monkeypatch.setattr(srv, "setup_telemetry", lambda: None, raising=False)
    return recorded


def test_main_reaches_the_stdio_transport(monkeypatch, calls) -> None:
    monkeypatch.setattr("sys.argv", ["zh-education-mcp"])
    from zh_education_mcp.server import main

    main()
    assert calls == {"transport": "stdio"}


def test_main_reaches_the_http_transport_with_host_and_port(monkeypatch, calls) -> None:
    """`--host`/`--port` müssen bis zum HTTP-Start durchkommen.

    Genau dieser Weg trug die entfernte Settings-Zuweisung; er darf die Werte
    nicht verlieren, nur weil sie nicht mehr über `mcp.settings` laufen.
    """
    monkeypatch.setattr(
        "sys.argv", ["zh-education-mcp", "--http", "--host", "0.0.0.0", "--port", "9123"]
    )
    from zh_education_mcp.server import main

    main()
    assert calls["http"] == ("streamable-http", "0.0.0.0", 9123)


def test_the_sdk_settings_object_still_lacks_host(monkeypatch) -> None:
    """Die Annahme hinter der Entfernung, festgehalten statt geglaubt.

    Sollte das SDK `host` je zurückbringen, schlägt dieser Test fehl und jemand
    entscheidet bewusst neu — statt dass die alte Zeile still wieder einzieht.
    """
    from zh_education_mcp.server import mcp

    assert "host" not in type(mcp.settings).model_fields
    assert "port" not in type(mcp.settings).model_fields
