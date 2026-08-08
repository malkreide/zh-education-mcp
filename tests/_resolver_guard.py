"""Der echte Namensauflöser, festgehalten bevor ihn jemand ersetzen kann.

Eigene Datei und nicht `conftest.py`, weil ein Test den Wächter prüfen muss
und `conftest.py` dafür nicht zuverlässig importierbar ist: `from
tests.conftest import …` hängt davon ab, ob das Arbeitsverzeichnis auf
`sys.path` liegt. Beim Aufruf über `python -m pytest` liegt es dort, beim
blossen `pytest` — wie in der CI — nicht. Genau daran ist der erste Anlauf
gescheitert, und lokal fand der Import sogar ein **fremdes** `tests`-Paket
aus den site-packages.

Ein Modul neben den Tests wird dagegen unter dem blossen Namen gefunden:
pytest legt im Standard-Importmodus das Verzeichnis der Testdatei auf
`sys.path`.

Warum überhaupt festhalten, und zwar hier oben: Wer die echte Funktion erst
*innerhalb* eines Tests greift, greift die bereits gepatchte. Der Wächter
vergliche dann einen Stub mit sich selbst und schwiege für immer —
dieselbe Falle, die im Kopf von `conftest.py` schon für `asyncio.sleep`
beschrieben steht.
"""

from __future__ import annotations

import socket

_REAL_GETADDRINFO = socket.getaddrinfo


def resolver_is_stubbed() -> bool:
    """Ob irgendetwas den Namensauflöser dieses Prozesses ersetzt hat."""
    return socket.getaddrinfo is not _REAL_GETADDRINFO
