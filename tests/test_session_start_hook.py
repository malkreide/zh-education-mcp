#!/usr/bin/env python3
"""Tests fuer .claude/hooks/session-start.sh — die Klon-Aktualitaetspruefung.

Der Hook meldet beim Sessionstart, wie viele Commits der ausgecheckte Stand
hinter dem Default-Branch liegt. Er existiert, weil ein veralteter Klon am
3.8.2026 zweimal eine rote CI erzeugt hat, deren Ursache nicht im Diff stand.

Gegenprobe zu jeder einzelnen Zusicherung. Die Reihenfolge der Testklassen
entspricht der Rangfolge der Zusicherungen: Blockiert er nie, ist er schnell,
schweigt er bei 0, raet er nicht auf `main`.

Kein Netz, keine Fixtures: Jeder Test baut echte Wegwerf-Repos und redet ueber
`file://` mit ihnen. Handgeschriebene Fixtures koennten die Annahme des Autors
ueber `git`-Verhalten nicht widerlegen — echte Repos koennen es. Genau so ist
hier aufgefallen, dass `git clone --depth` bei Pfad-Remotes still ignoriert
wird und ein vermeintlicher Flach-Klon-Test gar keinen flachen Klon prueft.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

HOOK = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "session-start.sh"

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@example.invalid",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@example.invalid",
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}


def git(cwd: Path, *args: str) -> str:
    env = {**os.environ, **GIT_ENV}
    done = subprocess.run(
        ["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=True
    )
    return done.stdout.strip()


def commit(repo: Path, text: str) -> None:
    (repo / "f").write_text(text, encoding="utf-8")
    git(repo, "add", "f")
    git(repo, "commit", "-qm", text)


class HookCase(unittest.TestCase):
    """Basis: Wegwerf-Verzeichnis, Upstream-Bau, Hook-Aufruf."""

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="zh-hook-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def upstream(self, branch: str = "main", commits: int = 3) -> Path:
        up = self.tmp / "up"
        up.mkdir()
        git(up, "init", "-q", "-b", branch)
        for i in range(1, commits + 1):
            commit(up, f"c{i}")
        return up

    def clone(self, up: Path, name: str = "work", depth: int | None = None) -> Path:
        dest = self.tmp / name
        args = ["clone", "-q"]
        if depth is not None:
            args += ["--depth", str(depth)]
        # file:// statt Pfad: Bei einem Pfad-Remote ignoriert git --depth still,
        # und der Klon waere gar nicht flach.
        args += [f"file://{up}", str(dest)]
        git(self.tmp, *args)
        return dest

    def run_hook(self, cwd: Path, *, env: dict[str, str] | None = None, timeout: str = "5"):
        full = {**os.environ, **GIT_ENV, "CLAUDE_PROJECT_DIR": str(cwd)}
        full["ZH_STALE_CHECK_TIMEOUT"] = timeout
        full.update(env or {})
        started = time.monotonic()
        done = subprocess.run(
            ["bash", str(HOOK)], cwd=cwd, env=full, capture_output=True, text=True, timeout=120
        )
        return done, time.monotonic() - started


class TestBlockiertNie(HookCase):
    """Zusicherung 1: kein Fall haelt die Session an. Exit-Code immer 0."""

    def test_kein_repo(self) -> None:
        plain = self.tmp / "kein-repo"
        plain.mkdir()
        done, _ = self.run_hook(plain)
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout, "")

    def test_repo_ohne_remote(self) -> None:
        solo = self.tmp / "solo"
        solo.mkdir()
        git(solo, "init", "-q")
        commit(solo, "c1")
        done, _ = self.run_hook(solo)
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout, "")

    def test_leeres_repo_ohne_commit(self) -> None:
        """Unborn HEAD: `git rev-list HEAD..` waere hier ein harter Fehler."""
        leer = self.tmp / "leer"
        leer.mkdir()
        git(leer, "init", "-q")
        git(leer, "remote", "add", "origin", "file:///nicht/vorhanden")
        done, _ = self.run_hook(leer)
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout, "")

    def test_unerreichbares_remote(self) -> None:
        """Der Fall 'kein Netz': Remote eingetragen, aber nicht erreichbar."""
        work = self.clone(self.upstream())
        git(work, "remote", "set-url", "origin", f"file://{self.tmp}/weg-damit")
        done, _ = self.run_hook(work)
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout, "")

    def test_detached_head(self) -> None:
        """Detached HEAD blockiert nicht — und wird trotzdem gemeldet."""
        up = self.upstream()
        work = self.clone(up)
        for extra in ("c4", "c5"):
            commit(up, extra)
        git(work, "checkout", "-q", "--detach", "HEAD")
        done, _ = self.run_hook(work)
        self.assertEqual(done.returncode, 0)
        self.assertIn("2 Commit(s) hinter", done.stdout)
        self.assertIn("detached HEAD", done.stdout)


class TestHaengtNicht(HookCase):
    """Zusicherung 2: kurzes Timeout, der Sessionstart haengt nicht."""

    def test_haengendes_netz_wird_abgebrochen(self) -> None:
        """git-Shim, der bei jedem Netzaufruf 30s schlaeft.

        Echte Wanduhr gegen echten Haenger — eine Fake-Uhr, die nur beim
        Schlafen vorrueckt, koennte diese Zusicherung nicht widerlegen.
        Ohne funktionierendes Timeout dauert der Lauf >= 30s.
        """
        work = self.clone(self.upstream())
        shim_dir = self.tmp / "shim"
        shim_dir.mkdir()
        real_git = shutil.which("git")
        shim = shim_dir / "git"
        shim.write_text(
            "#!/usr/bin/env bash\n"
            'for a in "$@"; do\n'
            '  case "$a" in ls-remote|fetch) sleep 30 ;; esac\n'
            "done\n"
            f'exec {real_git} "$@"\n',
            encoding="utf-8",
        )
        shim.chmod(0o755)
        done, elapsed = self.run_hook(
            work, env={"PATH": f"{shim_dir}{os.pathsep}{os.environ['PATH']}"}, timeout="1"
        )
        self.assertEqual(done.returncode, 0)
        self.assertLess(elapsed, 15.0, f"Hook haengt: {elapsed:.1f}s")


class TestSchweigtBeiNull(HookCase):
    """Zusicherung 3: Ausgabe nur, wenn wirklich Commits fehlen."""

    def test_aktueller_klon_schweigt(self) -> None:
        work = self.clone(self.upstream())
        done, _ = self.run_hook(work)
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout, "")

    def test_nur_voraus_schweigt(self) -> None:
        """Eigene Commits davor sind kein Rueckstand."""
        work = self.clone(self.upstream())
        commit(work, "eigenes")
        done, _ = self.run_hook(work)
        self.assertEqual(done.stdout, "")

    def test_meldet_anzahl_fehlender_commits(self) -> None:
        up = self.upstream()
        work = self.clone(up)
        for extra in ("c4", "c5", "c6", "c7"):
            commit(up, extra)
        done, _ = self.run_hook(work)
        self.assertEqual(done.returncode, 0)
        self.assertIn("4 Commit(s) hinter", done.stdout)
        self.assertIn("origin/main", done.stdout)

    def test_meldet_auch_voraus_wenn_zugleich_zurueck(self) -> None:
        up = self.upstream()
        work = self.clone(up)
        for extra in ("c4", "c5"):
            commit(up, extra)
        commit(work, "eigenes")
        done, _ = self.run_hook(work)
        self.assertIn("2 Commit(s) hinter", done.stdout)
        self.assertIn("(und 1 davor)", done.stdout)

    def test_abschaltbar(self) -> None:
        up = self.upstream()
        work = self.clone(up)
        commit(up, "c4")
        done, _ = self.run_hook(work, env={"ZH_STALE_CHECK": "0"})
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout, "")


class TestDefaultBranch(HookCase):
    """Zusicherung 4: ermitteln statt `main` annehmen."""

    def test_master_wird_erkannt(self) -> None:
        """Drei Server im Portfolio heissen ihren Default-Branch `master`.

        Wer hier `main` fest verdrahtet, faellt genau ueber diesen Test.
        """
        up = self.upstream(branch="master")
        work = self.clone(up)
        for extra in ("c4", "c5", "c6"):
            commit(up, extra)
        done, _ = self.run_hook(work)
        self.assertEqual(done.returncode, 0)
        self.assertIn("3 Commit(s) hinter", done.stdout)
        self.assertIn("origin/master", done.stdout)

    def test_erkennt_ohne_lokales_origin_head(self) -> None:
        """In frisch geklonten Agent-Umgebungen ist der lokale Zeiger nicht gesetzt.

        Genau so gemessen im Zielsystem: `fatal: ref refs/remotes/origin/HEAD
        is not a symbolic ref`. Wer sich allein darauf verlaesst, meldet nie
        etwas.
        """
        up = self.upstream(branch="master")
        work = self.clone(up)
        git(work, "symbolic-ref", "-d", "refs/remotes/origin/HEAD")
        for extra in ("c4", "c5"):
            commit(up, extra)
        done, _ = self.run_hook(work)
        self.assertIn("2 Commit(s) hinter", done.stdout)
        self.assertIn("origin/master", done.stdout)

    def test_raet_nicht_auf_main(self) -> None:
        """Ist der Default-Branch nicht ermittelbar, schweigt er.

        Ein Fallback auf `main` wuerde hier eine Zahl gegen einen Branch
        melden, der zufaellig genauso heisst — oder gar nicht existiert.
        """
        up = self.upstream(branch="master")
        work = self.clone(up)
        git(work, "symbolic-ref", "-d", "refs/remotes/origin/HEAD")
        # `master` ist echt zwei Commits voraus — es gaebe also etwas zu melden.
        for extra in ("c4", "c5"):
            commit(up, extra)
        # Upstream mit detached HEAD advertisiert keine `ref:`-Zeile mehr;
        # `ls-remote --symref` liefert nur noch den nackten SHA. Damit ist der
        # Default-Branch nicht ermittelbar.
        git(up, "checkout", "-q", "--detach", "HEAD")
        done, _ = self.run_hook(work)
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout, "")


class TestFlacherKlon(HookCase):
    """Der Klon, in dem dieser Hook tatsaechlich laeuft."""

    def test_flacher_klon_zaehlt_richtig(self) -> None:
        up = self.upstream(commits=12)
        work = self.clone(up, depth=1)
        self.assertEqual(git(work, "rev-parse", "--is-shallow-repository"), "true")
        for extra in ("c13", "c14", "c15", "c16"):
            commit(up, extra)
        done, _ = self.run_hook(work)
        self.assertEqual(done.returncode, 0)
        self.assertIn("4 Commit(s) hinter", done.stdout)

    def test_ohne_gemeinsamen_vorfahr_schweigt(self) -> None:
        """Lieber keine Zahl als eine erfundene.

        Ohne gemeinsamen Vorfahr zaehlt `HEAD..FETCH_HEAD` den ganzen
        Remote-Ast — das ist kein Rueckstand, sondern eine andere Historie.
        """
        up = self.upstream(commits=3)
        work = self.clone(up)
        git(work, "checkout", "-q", "--orphan", "fremd")
        git(work, "rm", "-rqf", ".")
        commit(work, "voellig anderer Anfang")
        done, _ = self.run_hook(work)
        self.assertEqual(done.returncode, 0)
        self.assertEqual(done.stdout, "")


if __name__ == "__main__":
    unittest.main()
