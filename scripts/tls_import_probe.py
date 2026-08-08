"""Misst, ob ein Import den TLS-Verifizierer dieses Prozesses verändert.

WARUM ES DIESES SKRIPT GIBT
---------------------------
Am 8.8.2026 ist `test_live_bista_api_letzi` in fünf Läufen hintereinander mit

    [SSL: CERTIFICATE_VERIFY_FAILED] Hostname mismatch,
    certificate is not valid for 'www.bista.zh.ch'

gescheitert — während im selben Lauf, gegen dieselbe Adresse, zwei Dinge
gleichzeitig galten:

  * Die übrigen Live-Tests bauten sauberes TLS auf. Ein `502` setzt eine
    gelungene Verbindung voraus; sie hatten also keinen TLS-Fehler.
  * `openssl s_client` bekam Sekunden später ein gültiges Zertifikat von
    DigiCert für `www.bista.zh.ch`.

Zwei Erklärungen sind damit bereits ausgeschlossen. **Die Quelle** nicht,
denn die liefert nachweislich ein gültiges Zertifikat. Und **die
Reihenfolge** nicht, denn eine Sonde mit `-k test_live_bista_api_letzi`
liess genau diesen einen Test allein laufen — ohne Vorgänger, ohne den
`getaddrinfo`-Patch des Nachbartests — und er scheiterte trotzdem.

Übrig bleibt eine Beobachtung, die über alle fünf Läufe lückenlos passt:

    vor  dem Import von `zh_education_mcp.server`:  TLS geht  (Antwort 502)
    nach dem Import von `zh_education_mcp.server`:  Hostname mismatch

`test_live_bista_api_letzi` ist der einzige Live-Test, der dieses Modul
importiert. Alle anderen rufen `_fetch_csv` direkt auf.

Wenn das die Ursache ist, ist es **kein Testproblem, sondern ein
Produktionsproblem**: Der ausgelieferte Server importiert dieses Modul
immer. Dann erreicht er BISTA über TLS nie und meldet dem Modell
«Unerwarteter interner Fehler» — ein Ausfall, den bisher der 502 überdeckt
hat.

WIE GEMESSEN WIRD
-----------------
Drei Zustände in **einem** Prozess, in dieser Reihenfolge:

    S0  nackt, nur `httpx` importiert
    S1  nach `import zh_education_mcp.http_client`   (was die anderen Tests tun)
    S2  nach `import zh_education_mcp.server`        (was nur der eine Test tut)
    S3  nach dem Tool-Aufruf selbst, der in fünf Läufen gescheitert ist

S1 ist die entscheidende Zwischenstufe. Ohne sie liesse sich «der Import
des Servers» nicht von «der Import des Pakets überhaupt» unterscheiden, und
die Sonde beantwortete eine gröbere Frage als die gestellte.

Je Zustand werden **zwei** Abrufe gemacht, nicht einer. Bei einem einzigen
wäre jede Seite ein n=1, und ein einzelnes Zucken der Leitung sähe aus wie
ein Zustandswechsel.

DER 502 IST HIER DAS GUTE ERGEBNIS
----------------------------------
Solange BISTA ausgefallen ist, bedeutet `http=502`: Die TLS-Verbindung kam
zustande. Gemessen wird nicht, ob die API antwortet, sondern ob überhaupt
verbunden werden kann. Ein `ConnectError` ist der Befund, ein `502` ist die
Entwarnung — deshalb steht in der Ausgabe je Zeile ausdrücklich `TLS ok`
oder `TLS KAPUTT` und nicht bloss der Status.
"""

from __future__ import annotations

import asyncio
import importlib
import ssl
import sys

import httpx

# Der Abruf geht über einen frischen Client je Versuch. Ein wiederverwendeter
# Client könnte eine bereits offene Verbindung aus einem früheren Zustand
# weiterbenutzen und damit genau den Wechsel verdecken, um den es geht.
TIMEOUT = 30.0
ATTEMPTS = 2


def _snapshot(label: str) -> dict[str, object]:
    """Was der SSL-Stack in diesem Moment über sich sagt."""
    ctx = ssl.create_default_context()
    return {
        "label": label,
        "ssl.SSLContext": f"{ssl.SSLContext.__module__}.{ssl.SSLContext.__qualname__}",
        "create_default_context": f"{type(ctx).__module__}.{type(ctx).__qualname__}",
        "check_hostname": ctx.check_hostname,
        "verify_mode": str(ctx.verify_mode),
        "truststore geladen": "truststore" in sys.modules,
        "ca-Zertifikate": len(ctx.get_ca_certs()),
    }


def _reach(url: str, user_agent: str) -> list[tuple[bool, str]]:
    """Versucht den Abruf und meldet je Versuch, ob TLS zustande kam."""
    results: list[tuple[bool, str]] = []
    for _ in range(ATTEMPTS):
        try:
            with httpx.Client(timeout=TIMEOUT, headers={"User-Agent": user_agent}) as client:
                resp = client.get(url)
            results.append((True, f"http={resp.status_code}"))
        except Exception as exc:  # noqa: BLE001 — jede Ausnahme ist hier ein Messwert
            results.append((False, f"{type(exc).__name__}: {exc}"))
    return results


# Waehrend die Quelle 502 liefert, scheitert der Tool-Aufruf IMMER -- an der
# Antwort, nicht an der Verbindung. Eine Sonde, die jede Ausnahme als Befund
# bucht, meldet dann bei jedem Lauf «Ursache gefunden» und hat nichts
# gemessen. Der Probelauf vom 8.8. hat genau das getan, bevor diese beiden
# Funktionen dazukamen.
_TLS_MARKER = ("CERTIFICATE_VERIFY_FAILED", "Hostname mismatch", "SSLError", "ConnectError")


def _causes(exc: BaseException) -> list[str]:
    """Die Ausnahmekette von aussen nach innen, als lesbare Zeilen."""
    lines: list[str] = []
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        lines.append(f"{type(cur).__module__}.{type(cur).__qualname__}: {cur}")
        cur = cur.__cause__ or cur.__context__
    return lines


def _is_tls(line: str) -> bool:
    """Nur ein Verbindungs- oder Zertifikatsfehler ist hier der Befund."""
    return any(marker in line for marker in _TLS_MARKER)


def _report(snap: dict[str, object], reach: list[tuple[bool, str]]) -> bool:
    print(f"\n### {snap['label']}")
    for key, value in snap.items():
        if key != "label":
            print(f"    {key:24s} {value}")
    for ok, detail in reach:
        print(f"    {'TLS ok    ' if ok else 'TLS KAPUTT'}           {detail}")
    return all(ok for ok, _ in reach)


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("Aufruf: tls_import_probe.py <url>", file=sys.stderr)
        return 2
    url = argv[1]

    # S0 — bevor irgendetwas aus dem Paket importiert ist.
    user_agent = "tls-import-probe"
    s0 = _report(_snapshot("S0  nackt, nur httpx"), _reach(url, user_agent))

    # S1 — der Pfad, den die übrigen Live-Tests nehmen.
    http_client = importlib.import_module("zh_education_mcp.http_client")
    user_agent = getattr(http_client, "USER_AGENT", user_agent)
    s1 = _report(_snapshot("S1  nach import zh_education_mcp.http_client"), _reach(url, user_agent))

    # S2 — der Pfad, den nur test_live_bista_api_letzi nimmt, und den der
    # ausgelieferte Server immer nimmt.
    server = importlib.import_module("zh_education_mcp.server")
    s2 = _report(_snapshot("S2  nach import zh_education_mcp.server"), _reach(url, user_agent))

    # S3 — der fehlschlagende Aufruf selbst, und unmittelbar danach noch
    # einmal ein nackter Abruf.
    #
    # Ohne diesen Zustand kann die Sonde nur eine Vermutung widerlegen, nicht
    # den Fehler finden. Stirbt die Import-Vermutung an S0..S2, bleibt sonst
    # nur «irgendwo dazwischen». Hier wird der Unterschied schmal: Scheitert
    # der Tool-Aufruf mit dem Mismatch, während der nackte Abruf eine Sekunde
    # später durchgeht, liegt es nicht am Zustand des Prozesses, sondern an
    # dem, was dieser Aufruf anders macht.
    print("\n### S3  der Aufruf, der in fünf Läufen gescheitert ist")
    try:
        params = server.SchulkreisTrendInput(schulgemeinde="Zürich-Letzi", letzte_n_jahre=3)
        asyncio.run(server.zh_edu_schulkreis_trend(params))
        print("    Aufruf durchgelaufen (kein Fehler)")
        tool_tls_failure = False
    except Exception as exc:  # noqa: BLE001 — die Ausnahme IST der Messwert
        chain = _causes(exc)
        for line in chain:
            print(f"    {line}")
        tool_tls_failure = any(_is_tls(line) for line in chain)
        print(
            f"    eingeordnet als:         {'TLS-Fehler' if tool_tls_failure else 'kein TLS-Fehler'}"
        )
    s3 = _report(_snapshot("S3  unmittelbar nach dem Aufruf"), _reach(url, user_agent))

    print("\n" + "=" * 70)
    states = {"S0": s0, "S1": s1, "S2": s2, "S3": s3}
    print(
        "Nackter Abruf je Zustand: "
        + ", ".join(f"{k}={'ok' if v else 'KAPUTT'}" for k, v in states.items())
    )
    print(f"Tool-Aufruf in S3: {'TLS-FEHLER' if tool_tls_failure else 'kein TLS-Fehler'}")

    if len(set(states.values())) > 1:
        print("\nBEFUND: der Prozesszustand aendert sich.")
        for name, ok in states.items():
            if not ok:
                print(f"  -> ab {name} schlaegt schon der nackte Abruf fehl")
                break
        print("Das trifft den ausgelieferten Server, nicht nur den Test.")
        return 1

    if tool_tls_failure:
        # Der schaerfste Ausgang: Der Prozess ist unveraendert, aber genau
        # dieser eine Aufruf faellt. Dann liegt es nicht am Import, sondern an
        # dem, was der Aufrufpfad anders macht -- und das ist eine Zeile Code,
        # keine Umgebungsfrage mehr.
        print("\nBEFUND: der Prozess ist unveraendert, der Tool-Aufruf faellt trotzdem.")
        print("Die Import-Vermutung ist widerlegt. Die Ursache liegt im Aufrufpfad.")
        return 1

    # Weder Zustandswechsel noch Fehlschlag. Auch das ist ein Ergebnis: Der
    # Fehler ist hier nicht reproduzierbar, und die naechste Frage lautet,
    # was der pytest-Lauf anders macht als dieses Skript.
    print("\nBEFUND: nichts reproduziert -- kein Zustandswechsel, kein TLS-Fehler.")
    print("Die Import-Vermutung ist widerlegt; als Naechstes ist der Testaufbau dran.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
