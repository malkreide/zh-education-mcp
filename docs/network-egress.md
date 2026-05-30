# Network Egress

Defense-in-Depth für ausgehende Verbindungen (Audit SEC-004 / SEC-021).

## Code-Layer (implementiert)

Die erlaubten Ziel-Hosts sind als unveränderliches `frozenset` im Code definiert
(`ALLOWED_HOSTS` in `server.py`) — **nicht** zur Laufzeit oder via ENV mutierbar:

```
ALLOWED_HOSTS = frozenset({"www.bista.zh.ch"})
```

Ein httpx-`request`-Event-Hook (`_egress_guard`) prüft **jeden** ausgehenden
Request — auch Redirect-Hops — und erzwingt:

- Schema `https` (kein Cleartext)
- Host ∈ `ALLOWED_HOSTS`

Damit sind klassische SSRF (kein user-kontrollierter Host) **und**
Redirect-basierte SSRF (Umleitung auf Metadata-IPs wie `169.254.169.254`)
blockiert.

## Network-Layer (Deployment-Verantwortung)

Im Cloud-Deployment ist ergänzend eine Netzwerk-Egress-Kontrolle zu setzen
(Defense-in-Depth, falls der Code-Layer kompromittiert wird):

- **Render/Railway:** Egress auf `www.bista.zh.ch:443` beschränken (sofern Plattform-Egress-Rules unterstützt werden).
- **Kubernetes:** `NetworkPolicy` mit `egress`-Allow nur für den BISTA-Host + DNS (Port 53).
- **DNS** muss erlaubt bleiben, sonst schlägt die Hostname-Auflösung still fehl.

## Allow-List erweitern

Neue Datenquellen werden durch Ergänzen von `ALLOWED_HOSTS` im Code (per PR,
mit Review) freigeschaltet — bewusst kein Runtime-Mechanismus.

## Bekannte Resterisiken

- **DNS-Pinning (SEC-005):** Aktuell kein explizites IP-Pinning gegen TOCTOU;
  das Restrisiko ist durch die Single-Host-Allow-List (ein vertrauenswürdiger
  Host) gering. Vollständiges Pinning (resolved-IP-Transport) ist als
  Folge-Härtung vorgemerkt.
