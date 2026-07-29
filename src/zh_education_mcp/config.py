"""Laufzeit-Konfiguration (ENV-basiert) für zh-education-mcp."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Laufzeit-Konfiguration aus Umgebungsvariablen (Präfix ``MCP_``).

    Beispiele:
      ``MCP_TRANSPORT=streamable-http`` · ``MCP_HOST=0.0.0.0`` · ``MCP_PORT=8000``

    Default ist der lokale stdio-Betrieb mit Loopback-Binding — Cloud-Betrieb
    wird ausschliesslich explizit über ENV-Vars (oder CLI-Flags) aktiviert.
    """

    model_config = SettingsConfigDict(env_prefix="MCP_", env_file=".env", extra="ignore")

    transport: str = "stdio"
    host: str = "127.0.0.1"
    port: int = 8000

    # Stateless HTTP: read-only Server hält keinen Session-State → jeder
    # Load-Balancer (Round-Robin) funktioniert ohne Sticky Sessions (SCALE-002/003).
    stateless_http: bool = True
    json_response: bool = False

    # CORS-Origins für Browser-Clients (z. B. claude.ai). Komma-separiert via
    # MCP_CORS_ORIGINS. Default deckt den dokumentierten Browser-Use-Case ab;
    # in Produktion explizit auf die genutzten Origins setzen (keine Wildcard).
    cors_origins: str = "https://claude.ai"

    # Inbound Host-Allow-List für die HTTP-Transporte (SEC-005, eingehende
    # Hälfte). Komma-separiert via MCP_ALLOWED_HOSTS, z. B.
    # "mcp.example.ch,mcp.example.ch:443". Nur bei Nicht-Loopback-Bind nötig:
    # der erreichbare Name ist dann ein Service- oder öffentlicher DNS-Name,
    # den dieser Prozess aus der Bind-Adresse nicht ableiten kann. Leer lassen
    # behält bei solchem Bind das bisherige Verhalten (keine Host-Prüfung) und
    # löst eine Warnung beim Start aus.
    allowed_hosts: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_host_list(self) -> list[str]:
        return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]

    @property
    def is_local_bind(self) -> bool:
        return self.host in ("127.0.0.1", "localhost", "::1")


settings = Settings()
