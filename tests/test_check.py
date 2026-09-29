"""Regression tests for ai_protocol.check (TODO severity and LOCAL-ONLY close handling).

Run from the repo root, with the package installed (pip install -e .):
    python -m unittest discover tests

Each test builds a throwaway Git repo in a temp dir; runs the INSTALLED module
(`python -m ai_protocol.check`), not a path to a script file, so this also proves the
console-script wiring resolves regardless of the current working directory.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


def write(root, rel, text):
    p = Path(root, rel)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8", newline="\n")


class AiCheckTest(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="ai_check_test_")
        git(self.repo, "init", "-q")
        git(self.repo, "symbolic-ref", "HEAD", "refs/heads/main")
        git(self.repo, "config", "user.name", "test")
        git(self.repo, "config", "user.email", "test@example.invalid")
        git(self.repo, "config", "core.autocrlf", "false")

    def tearDown(self):
        shutil.rmtree(self.repo, ignore_errors=True)

    def make_protocol_repo(self, agents_todo=False):
        """Protocol skeleton, no origin, correctly closed: last commit is the handoff commit."""
        agents = "# AGENTS.md\n" + ("- Test: TODO: verify the test command\n" if agents_todo else "- Test: run it\n")
        write(self.repo, "AGENTS.md", agents)
        write(self.repo, "CLAUDE.md", "@AGENTS.md\n")
        write(self.repo, "ai/STATE.md", "# State\n")
        write(self.repo, ".gitignore", "ai/logs/\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "init")
        head = git(self.repo, "rev-parse", "HEAD")
        write(self.repo, "ai/handoffs/20260929T120000Z-test-T-1.md", f"---\nhead_sha: {head}\n---\n# Handoff\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "handoff: T-1 test")

    def run_checker(self, *flags):
        env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1")
        p = subprocess.run([sys.executable, "-m", "ai_protocol.check", *flags], cwd=self.repo,
                           capture_output=True, text=True, env=env, timeout=120)
        return p.returncode, p.stdout

    def test_agents_todo_is_warn_in_normal_mode(self):
        self.make_protocol_repo(agents_todo=True)
        rc, out = self.run_checker("--allow-local")
        self.assertIn("[WARN] AGENTS.md placeholders", out)
        self.assertNotIn("[FAIL]", out)
        self.assertIn("STATUS: LOCAL-ONLY", out)
        self.assertEqual(rc, 0, out)

    def test_agents_todo_is_fail_with_close(self):
        self.make_protocol_repo(agents_todo=True)
        rc, out = self.run_checker("--close", "--allow-local")
        self.assertIn("[FAIL] AGENTS.md placeholders", out)
        self.assertIn("STATUS: BLOCKED", out)
        self.assertEqual(rc, 1, out)

    def test_no_origin_close_allow_local_succeeds(self):
        self.make_protocol_repo()
        rc, out = self.run_checker("--close", "--allow-local")
        self.assertNotIn("[FAIL]", out)
        self.assertIn("[WARN] HEAD pushed", out)
        self.assertIn("STATUS: LOCAL-ONLY", out)
        self.assertEqual(rc, 0, out)

    def test_no_origin_close_without_allow_local_fails(self):
        self.make_protocol_repo()
        rc, out = self.run_checker("--close")
        self.assertIn("[FAIL] HEAD pushed", out)
        self.assertIn("STATUS: BLOCKED", out)
        self.assertEqual(rc, 1, out)


if __name__ == "__main__":
    unittest.main()
