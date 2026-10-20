"""install/portable.sh: the commands GNU and BSD (macOS) spell differently.

Each helper runs for real through bash, the way the installer calls it.
`airlock_timeout` also runs with `timeout` hidden from PATH, which is what a
Mac looks like, so its Python stand-in is exercised on Linux too.
"""

import tests  # noqa: F401, I001 -- MUST be the first import; see test_compat_shims.py.

import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

from tests import posix_only

REPO_ROOT = Path(__file__).resolve().parent.parent
PORTABLE = REPO_ROOT / "install" / "portable.sh"
BASH = shutil.which("bash")


def run(script, env=None):
    """Source portable.sh in a fresh bash, then run `script`."""
    return subprocess.run(
        [BASH, "-c", '. "$1"; ' + script, "bash", str(PORTABLE)],
        capture_output=True, text=True, env=env, timeout=30)


def env_without_timeout(bin_dir):
    """A PATH holding only what the timeout tests need, and no `timeout`."""
    for name in ("sleep", "sh", "cat"):
        os.symlink(shutil.which(name), os.path.join(bin_dir, name))
    return dict(os.environ, PATH=bin_dir, PY=sys.executable)


@posix_only("portable.sh is a bash helper")
class TestRename(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir = os.path.realpath(self.tmp.name)

    def test_a_link_to_a_directory_is_replaced_not_entered(self):
        old = os.path.join(self.dir, "old-release")
        new = os.path.join(self.dir, "new-release")
        os.makedirs(old)
        os.makedirs(new)
        current = os.path.join(self.dir, "current")
        os.symlink(old, current)
        tmp_link = os.path.join(self.dir, ".current.tmp")
        os.symlink(new, tmp_link)

        proc = run('airlock_rename "%s" "%s"; echo "rc=$?"' % (tmp_link, current))

        self.assertIn("rc=0", proc.stdout, proc.stderr)
        self.assertEqual(os.path.realpath(current), new)
        self.assertFalse(os.path.lexists(tmp_link))
        # A plain mv would have put the link inside the old release.
        self.assertEqual(os.listdir(old), [])

    def test_a_directory_moves_to_a_new_name(self):
        src = os.path.join(self.dir, "plumbline")
        os.makedirs(src)
        Path(src, "mode").write_text("shadow\n")
        dst = os.path.join(self.dir, "airlock")

        proc = run('airlock_rename "%s" "%s"' % (src, dst))

        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(Path(dst, "mode").read_text(), "shadow\n")
        self.assertFalse(os.path.exists(src))


@posix_only("portable.sh is a bash helper")
class TestOwnerMode(unittest.TestCase):
    def test_prints_the_owner_uid_and_the_octal_mode(self):
        with tempfile.NamedTemporaryFile() as f:
            os.chmod(f.name, 0o640)
            proc = run('airlock_owner_mode "%s"' % f.name)
        self.assertEqual(proc.stdout.strip(), "%d 640" % os.getuid())

    def test_fails_for_a_missing_file(self):
        proc = run('airlock_owner_mode /nonexistent/airlock-test')
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(proc.stdout, "")


@posix_only("portable.sh is a bash helper")
class TestTimeout(unittest.TestCase):
    def envs(self):
        """The real PATH, and one with no `timeout` on it."""
        bin_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, bin_dir)
        return {"real PATH": None, "no timeout": env_without_timeout(bin_dir)}

    def test_the_command_exit_code_passes_through(self):
        for label, env in self.envs().items():
            with self.subTest(label):
                proc = run('airlock_timeout 5 sh -c "exit 3"; echo "rc=$?"', env)
                self.assertIn("rc=3", proc.stdout, proc.stderr)

    def test_a_slow_command_is_stopped_with_124(self):
        for label, env in self.envs().items():
            with self.subTest(label):
                start = time.monotonic()
                proc = run('airlock_timeout 0.5 sleep 10; echo "rc=$?"', env)
                self.assertIn("rc=124", proc.stdout, proc.stderr)
                self.assertLess(time.monotonic() - start, 5)

    def test_stdin_and_stdout_reach_the_command(self):
        for label, env in self.envs().items():
            with self.subTest(label):
                proc = run('echo hello | airlock_timeout 5 sh -c "cat"', env)
                self.assertEqual(proc.stdout, "hello\n", proc.stderr)


if __name__ == "__main__":
    unittest.main()
