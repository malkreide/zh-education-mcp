"""Eingehende Host/Origin-Prüfung der HTTP-Transporte (SEC-005, eingehende Hälfte).

Das SDK lässt den DNS-Rebinding-Schutz aus, solange ``transport_security``
ungesetzt ist. Bis zu diesem Commit war er in diesem Server nie gesetzt, also
gab es keine Host-Prüfung. Diese Tests halten das neue Verhalten fest — und
zwar so, dass sie fehlschlagen, wenn der Schutz wieder wegfällt.
"""

from __future__ import annotations

import pytest
from starlette.testclient import TestClient

from zh_education_mcp.config import Settings
from zh_education_mcp.server import build_transport_security, mcp

_INIT = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "1"},
    },
}
_HEADERS = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}


def test_loopback_bind_enables_protection():
    """Auf Loopback ist die Allow-List ableitbar, also wird geprüft."""
    sec = build_transport_security("127.0.0.1", 8000)
    assert sec is not None
    assert sec.enable_dns_rebinding_protection is True
    assert "127.0.0.1:8000" in sec.allowed_hosts
    assert "localhost:8000" in sec.allowed_hosts


def test_non_local_bind_without_allowlist_stays_off(monkeypatch):
    """0.0.0.0 ohne MCP_ALLOWED_HOSTS: der erreichbare Name ist unbekannt.

    Eine geratene Liste würde jede echte Anfrage abweisen, darum bleibt der
    Schutz aus (unverändertes Verhalten) und der Aufrufer warnt.
    """
    monkeypatch.setattr("zh_education_mcp.server.settings", Settings(allowed_hosts=""))
    assert build_transport_security("0.0.0.0", 8000) is None


def test_non_local_bind_with_allowlist_enables_protection(monkeypatch):
    """Mit MCP_ALLOWED_HOSTS wird auch der 0.0.0.0-Bind geprüft."""
    monkeypatch.setattr(
        "zh_education_mcp.server.settings",
        Settings(allowed_hosts="mcp.example.ch,mcp.example.ch:443"),
    )
    sec = build_transport_security("0.0.0.0", 8000)
    assert sec is not None
    assert "mcp.example.ch" in sec.allowed_hosts
    # Loopback bleibt drin, sonst brechen Container-Health-Checks.
    assert "127.0.0.1:8000" in sec.allowed_hosts


def test_configured_cors_origins_pass_transport_check(monkeypatch):
    """CORS-Origins müssen auch die Transport-Prüfung passieren.

    Sonst weist der Server genau die Browser-Clients ab, die CORS erlaubt —
    ein Fehler, der sich erst im Browser zeigt, nie im Unit-Test.
    """
    monkeypatch.setattr(
        "zh_education_mcp.server.settings",
        Settings(cors_origins="https://claude.ai", allowed_hosts=""),
    )
    sec = build_transport_security("127.0.0.1", 8000)
    assert "https://claude.ai" in sec.allowed_origins


def _post_with_host(host_header: str):
    # mcp 2.x: transport_security is a per-app kwarg, not a setting.
    with TestClient(
        mcp.streamable_http_app(transport_security=build_transport_security("127.0.0.1", 8000))
    ) as client:
        return client.post("/mcp", headers={"Host": host_header, **_HEADERS}, json=_INIT)


def test_allowed_host_is_served():
    assert _post_with_host("127.0.0.1:8000").status_code == 200


def test_foreign_host_is_rejected():
    assert _post_with_host("evil.example.com").status_code == 421


def test_right_host_wrong_port_is_rejected():
    """Der tragende Fall.

    ``evil.example.com`` allein beweist wenig: würde der Schutz auf einen
    Localhost-Default zurückfallen, wäre der ebenfalls abgewiesen. Nur der
    Fall "richtiger Hostname, falscher Port" unterscheidet eine port-genaue
    Allow-List von einer, die ``127.0.0.1:*`` erlaubt — und er schlägt fehl,
    sobald ``transport_security`` nicht mehr gesetzt wird.
    """
    assert _post_with_host("127.0.0.1:9999").status_code == 421


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost", "::1"])
def test_all_loopback_forms_are_local(host):
    assert build_transport_security(host, 8000) is not None


# ---------------------------------------------------------------------------
# Per-App-Kwargs, die in 1.x Konstruktor-Argumente waren
# ---------------------------------------------------------------------------


def _spy_app_kwargs(monkeypatch, transport="streamable-http"):
    """Fängt die Kwargs ab, mit denen die echte App gebaut wird."""
    import uvicorn

    from zh_education_mcp import server as srv

    captured: dict = {}
    real = type(srv.mcp).streamable_http_app

    def _spy(self, **kwargs):
        captured.update(kwargs)
        return real(self, **kwargs)

    monkeypatch.setattr(type(srv.mcp), "streamable_http_app", _spy)
    monkeypatch.setattr(uvicorn, "run", lambda *a, **k: None)
    srv._run_http(transport, "127.0.0.1", 8000)
    return captured


def test_stateless_http_reaches_the_app(monkeypatch):
    """SCALE-002/003: horizontale Skalierung ohne Sticky Sessions.

    In 1.x war ``stateless_http`` ein MCPServer-Konstruktor-Argument. Die
    Migration auf mcp 2.x hat es fallen gelassen, ohne es als App-Kwarg wieder
    anzuhängen. Das ist ein stiller Rückschritt: der Default in ``config.py``
    ist ``True``, der App-Kwarg-Default ``False`` — der Server verlangte also
    wieder Sticky Sessions, und nichts schlug fehl.
    """
    assert _spy_app_kwargs(monkeypatch)["stateless_http"] is True


def test_json_response_reaches_the_app(monkeypatch):
    """Gleiche Fehlerklasse, gleiche Prüfung — hier ist der Default ``False``,
    weshalb der Verlust noch unauffälliger war."""
    assert _spy_app_kwargs(monkeypatch)["json_response"] is False


def test_stateless_follows_the_setting(monkeypatch):
    """Beweist, dass der Wert durchreist und nicht hartkodiert ist."""
    from zh_education_mcp import server as srv
    from zh_education_mcp.config import Settings

    monkeypatch.setattr(srv, "settings", Settings(stateless_http=False))
    assert _spy_app_kwargs(monkeypatch)["stateless_http"] is False


def test_settings_no_longer_carries_them():
    """Der 1.x-Lesepfad ist weg — und zwar laut, nicht still."""
    import pytest as _pytest

    from zh_education_mcp.server import mcp

    for field in ("stateless_http", "json_response"):
        assert not hasattr(mcp.settings, field)
        with _pytest.raises(ValueError, match=f'has no field "{field}"'):
            setattr(mcp.settings, field, True)
