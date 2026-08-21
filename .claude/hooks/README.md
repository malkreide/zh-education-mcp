# SessionStart-Hook: Klon-Aktualität

`session-start.sh` meldet beim Sessionstart, wie viele Commits der
ausgecheckte Stand hinter `<remote>/<default-branch>` liegt. Registriert ist er
in `.claude/settings.json` unter `hooks.SessionStart`.

## Warum

Ein veralteter Klon hat am **3.8.2026 zweimal eine rote CI erzeugt, deren
Ursache nicht im Diff stand** — die fehlenden Commits waren jeweils genau die,
die das Gate einführten, an dem der Branch scheiterte. Man sucht den Fehler
dann in den geänderten Dateien, und dort ist er nicht. Die Prüfung kostet eine
Sekunde und ersetzt eine Fehlersuche in den falschen Dateien.

Der Hook ist die automatische Fassung des Absatzes «Vor der Arbeit» in
`CLAUDE.md`. Er ersetzt ihn nicht — er sorgt dafür, dass man nicht daran
denken muss.

## Zusicherungen

Nach Wichtigkeit geordnet; die erste hat Vorrang vor allen anderen.

1. **Er blockiert die Session niemals.** Kein Netz, kein Remote, detached
   HEAD, flatterndes DNS, kein `git`, gar kein Repo, leeres Repo ohne Commit —
   jeder dieser Fälle geht still durch, Exit-Code 0. Ein Hook, der bei
   Netzproblemen die Arbeit anhält, wird nach dem zweiten Mal abgeschaltet und
   schützt danach gar nichts. Darum kein `set -e`, sondern `trap 'exit 0' EXIT`:
   Auch ein unvorhergesehener Fehler endet mit 0.
2. **Kurzes Timeout auf jeden Netzaufruf** (zwei Stück: `ls-remote` und
   `fetch`, Default je 5 s, Worst Case also ~10 s). Zusätzlich sind alle
   interaktiven Rückfragen von git, ssh und credential-helper abgeschaltet —
   ein Passwort-Prompt ist der eine Hänger, den `timeout(1)` nicht sauber
   abräumt, und der eigentliche Grund für einen zähen Sessionstart. Fehlt
   `timeout(1)` (macOS ohne coreutils), tragen `http.lowSpeedLimit` /
   `http.lowSpeedTime` die Abbruchlogik.
3. **Ausgabe nur, wenn tatsächlich Commits fehlen.** Bei 0 schweigt er.
4. **Der Default-Branch wird ermittelt, nicht als `main` angenommen.** Drei
   Server im Portfolio heissen ihn `master` (`openlex-mcp`, `swiss-courts-mcp`,
   `swisstopo-mcp`); genau diese Annahme hat schon einmal einen Branch 15
   Commits alt werden lassen. Primärquelle ist `git ls-remote --symref origin
   HEAD`, Fallback das lokale `refs/remotes/origin/HEAD`. Liefert keins von
   beiden etwas, schweigt der Hook — er rät nicht auf `main`.

## Zwei Fallen, die hier bewusst behandelt sind

**Flacher Klon.** Agent-Umgebungen klonen mit `--depth`; in genau der
Umgebung, für die dieser Hook gebaut ist, ist `git rev-parse
--is-shallow-repository` `true`. Ein `git fetch` holt dort die verbindenden
Commits mit, die Zahl stimmt also normalerweise. Fehlt aber ein gemeinsamer
Vorfahr — flacher Klon mit zu kurzem Verlauf, oder umgeschriebene Historie —,
zählte `HEAD..FETCH_HEAD` den halben Remote-Ast und meldete eine erfundene
Zahl. Der Hook prüft darum vorher `git merge-base` und schweigt lieber, als zu
raten.

**Nicht gesetztes `refs/remotes/origin/HEAD`.** In frisch geklonten
Agent-Umgebungen ist der lokale Zeiger oft gar nicht gesetzt (`fatal: ref
refs/remotes/origin/HEAD is not a symbolic ref`). Deshalb ist er hier nur der
Fallback, nicht die Primärquelle.

## Stellschrauben

| Variable                  | Default  | Wirkung                              |
| ------------------------- | -------- | ------------------------------------ |
| `ZH_STALE_CHECK`          | `1`      | `0`/`off`/`false`/`no` schaltet ab   |
| `ZH_STALE_CHECK_REMOTE`   | `origin` | zu prüfendes Remote                  |
| `ZH_STALE_CHECK_TIMEOUT`  | `5`      | Sekunden je Netzaufruf               |

## Gegenprobe

`tests/test_session_start_hook.py` fährt den Hook gegen echte Wegwerf-Repos
(lokale `file://`-Remotes, auch ein flacher Klon) und deckt jede Zusicherung
einzeln ab. Läuft im normalen Gate mit:

```bash
PYTHONPATH=src pytest tests/test_session_start_hook.py -m "not live"
```
