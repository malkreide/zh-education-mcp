#!/usr/bin/env bash
#
# SessionStart-Hook: Klon-Aktualität melden.
#
# WARUM ES DIESEN HOOK GIBT
# -------------------------
# Ein veralteter Klon hat am 3.8.2026 zweimal eine rote CI erzeugt, deren
# Ursache nicht im Diff stand — die fehlenden Commits waren jeweils genau die,
# die das Gate einführten, an dem der Branch scheiterte. Die Prüfung kostet
# eine Sekunde und ersetzt eine Fehlersuche in den falschen Dateien.
#
# ZUSICHERUNGEN (in dieser Reihenfolge wichtig)
# ---------------------------------------------
# 1. Der Hook blockiert die Session NIEMALS. Kein Netz, kein Remote, detached
#    HEAD, flatterndes DNS, kein git, gar kein Repo — jeder dieser Fälle geht
#    still durch, Exit-Code 0. Ein Hook, der bei Netzproblemen die Arbeit
#    anhält, wird nach dem zweiten Mal abgeschaltet und schützt danach gar
#    nichts. Darum kein `set -e`, sondern `trap 'exit 0' EXIT`: Selbst ein
#    unvorhergesehener Fehler endet mit 0.
# 2. Kurzes Timeout auf jeden Netzaufruf (zwei Stück, Default je 5s).
#    Zusätzlich sind alle interaktiven Rückfragen von git/ssh/credential-helper
#    abgeschaltet — ein Passwort-Prompt ist der eine Hänger, den timeout(1)
#    nicht sauber abräumt, und der eigentliche Grund für einen zähen Start.
# 3. Ausgabe nur, wenn tatsächlich Commits fehlen. Bei 0 schweigt er.
# 4. Der Default-Branch wird ERMITTELT, nicht als "main" angenommen. Drei
#    Server im Portfolio heissen ihn `master` (openlex-mcp, swiss-courts-mcp,
#    swisstopo-mcp); genau diese Annahme hat schon einmal einen Branch
#    15 Commits alt werden lassen. Ist er nicht ermittelbar, schweigt der Hook,
#    statt auf "main" zu raten.
#
# Abschalten:  ZH_STALE_CHECK=0
# Stellschraub: ZH_STALE_CHECK_TIMEOUT (Sekunden je Netzaufruf, Default 5)
#               ZH_STALE_CHECK_REMOTE  (Default: origin)

trap 'exit 0' EXIT
set -u

case "${ZH_STALE_CHECK:-1}" in
  0 | off | false | no | "") exit 0 ;;
esac

REMOTE="${ZH_STALE_CHECK_REMOTE:-origin}"
TMO="${ZH_STALE_CHECK_TIMEOUT:-5}"
case "$TMO" in '' | *[!0-9]*) TMO=5 ;; esac

command -v git >/dev/null 2>&1 || exit 0
cd "${CLAUDE_PROJECT_DIR:-$PWD}" 2>/dev/null || exit 0

# Kein Repo / leeres Repo ohne Commit / kein solches Remote -> still raus.
git rev-parse --git-dir      >/dev/null 2>&1 || exit 0
git rev-parse --verify -q HEAD >/dev/null 2>&1 || exit 0
git remote get-url "$REMOTE" >/dev/null 2>&1 || exit 0

# Hänger-Schutz: keine interaktiven Rückfragen, egal welcher Transport.
NOOP="$(command -v true 2>/dev/null)"
export GIT_TERMINAL_PROMPT=0
export GCM_INTERACTIVE=never
[ -n "$NOOP" ] && export GIT_ASKPASS="$NOOP" SSH_ASKPASS="$NOOP"
export GIT_SSH_COMMAND="${GIT_SSH_COMMAND:-ssh} -o BatchMode=yes -o ConnectTimeout=$TMO"

# timeout(1) fehlt auf macOS ohne coreutils. Dann tragen die
# http.lowSpeed*-Optionen die Abbruchlogik — deshalb sind beide gesetzt.
TIMEOUT_BIN="$(command -v timeout 2>/dev/null || command -v gtimeout 2>/dev/null || true)"
net_git() {
  if [ -n "$TIMEOUT_BIN" ]; then
    "$TIMEOUT_BIN" -k 1 "$TMO" git -c http.lowSpeedLimit=1000 -c "http.lowSpeedTime=$TMO" "$@"
  else
    git -c http.lowSpeedLimit=1000 -c "http.lowSpeedTime=$TMO" "$@"
  fi
}

# --- Default-Branch ermitteln, nicht raten ---------------------------------
# Primär die Quelle fragen; sie ist auch dann richtig, wenn der Branch nach
# dem Klonen umbenannt wurde. Fallback ist das lokale refs/remotes/*/HEAD —
# das ist in frisch geklonten Agent-Umgebungen oft gar nicht gesetzt.
DEFAULT_BRANCH="$(
  net_git ls-remote --symref "$REMOTE" HEAD 2>/dev/null |
    sed -n 's|^ref: refs/heads/\([^[:space:]]*\)[[:space:]].*|\1|p' | head -1
)"
if [ -z "$DEFAULT_BRANCH" ]; then
  DEFAULT_BRANCH="$(
    git symbolic-ref --short "refs/remotes/$REMOTE/HEAD" 2>/dev/null |
      sed "s|^$REMOTE/||"
  )"
fi
[ -n "$DEFAULT_BRANCH" ] || exit 0

net_git fetch --quiet "$REMOTE" "$DEFAULT_BRANCH" >/dev/null 2>&1 || exit 0

# Ohne gemeinsamen Vorfahr ist die Zahl Unsinn statt Information: In einem
# flachen Klon (Agent-Umgebungen klonen mit --depth) oder nach einem
# umgeschriebenen Verlauf zählte HEAD..FETCH_HEAD sonst den halben Remote-Ast.
# Lieber schweigen als eine erfundene Zahl melden.
git merge-base HEAD FETCH_HEAD >/dev/null 2>&1 || exit 0

BEHIND="$(git rev-list --count HEAD..FETCH_HEAD 2>/dev/null)"
case "$BEHIND" in '' | *[!0-9]*) exit 0 ;; esac
[ "$BEHIND" -gt 0 ] || exit 0    # Bei 0 schweigt er.

AHEAD="$(git rev-list --count FETCH_HEAD..HEAD 2>/dev/null)"
case "$AHEAD" in '' | *[!0-9]*) AHEAD=0 ;; esac

HERE="$(git symbolic-ref --quiet --short HEAD 2>/dev/null)"
[ -n "$HERE" ] || HERE="detached HEAD @ $(git rev-parse --short HEAD 2>/dev/null)"

printf 'Klon-Aktualität: %s liegt %s Commit(s) hinter %s/%s' \
  "$HERE" "$BEHIND" "$REMOTE" "$DEFAULT_BRANCH"
[ "$AHEAD" -gt 0 ] && printf ' (und %s davor)' "$AHEAD"
printf '.\n'
printf 'Ein veralteter Klon erzeugt eine rote CI, deren Ursache nicht im Diff steht:\n'
printf 'Es fehlen womoeglich genau die Commits, die das Gate einfuehren, an dem der\n'
printf 'Branch scheitert. Vor der Arbeit einspielen:\n'
printf '    git fetch %s %s && git merge FETCH_HEAD\n' "$REMOTE" "$DEFAULT_BRANCH"
exit 0
