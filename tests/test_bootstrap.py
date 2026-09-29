"""End-to-end bootstrap safety tests against disposable Git repositories."""
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ai_protocol import bootstrap, check

SOURCE = str(Path(__file__).resolve().parents[1] / "src")


class BootstrapTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.env = dict(os.environ, PYTHONPATH=SOURCE, GIT_CONFIG_NOSYSTEM="1",
                        GIT_CONFIG_GLOBAL=os.devnull, GIT_TERMINAL_PROMPT="0")
        self.git("init", "-q")
        self.git("symbolic-ref", "HEAD", "refs/heads/main")
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "core.autocrlf", "false")

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, env=self.env,
                              check=True, capture_output=True).stdout

    def write(self, name, data):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def seed(self, files=None):
        for name, data in (files or {"project.txt": b"base\n"}).items():
            self.write(name, data)
        self.git("add", "--", *(files or {"project.txt": b""}))
        self.git("commit", "-qm", "seed")

    def run_bootstrap(self, cwd=None, agent="test"):
        return subprocess.run([sys.executable, "-m", "ai_protocol.bootstrap", "--agent", agent],
                              cwd=cwd or self.root, env=self.env, capture_output=True,
                              text=True, timeout=90)

    def assert_complete(self, p):
        self.assertIn("Bootstrap structure created successfully.", p.stdout, p.stderr)
        self.assertIn("ai-check exit code:", p.stdout)
        self.assertEqual(p.returncode, 0, p.stdout)  # LOCAL-ONLY accepted by bootstrap

    def test_not_git_no_files(self):
        folder = self.root / "outside"
        folder.mkdir()
        # Separate directory outside the initialized repository.
        with tempfile.TemporaryDirectory() as other:
            p = self.run_bootstrap(other)
            self.assertNotEqual(p.returncode, 0)
            self.assertEqual(list(Path(other).iterdir()), [])

    def test_clean_existing_repo_one_commit_and_lf(self):
        self.seed()
        p = self.run_bootstrap()
        self.assert_complete(p)
        self.assertEqual(self.git("rev-list", "--count", "HEAD").strip(), b"2")
        self.assertEqual(self.git("log", "-1", "--format=%s").strip(), b"handoff: bootstrap test")
        for name in ("AGENTS.md", "CLAUDE.md", "ai/STATE.md", "ai/tasks/.gitkeep", ".gitignore"):
            data = (self.root / name).read_bytes()
            self.assertNotIn(b"\r", data)
        handoffs = list((self.root / "ai/handoffs").glob("*.md"))
        self.assertEqual(len(handoffs), 1)
        self.assertRegex(handoffs[0].name, r"^\d{8}T\d{6}Z-test-bootstrap\.md$")
        self.assertNotIn(b"\r", handoffs[0].read_bytes())
        self.assertIn("TODO: not verified", (self.root / "ai/STATE.md").read_text())
        self.assertEqual(self.git("status", "--porcelain"), b"")

    def test_existing_files_preserved_and_claude_prepended(self):
        original = {"AGENTS.md": b"custom\r\n", "CLAUDE.md": b"custom\r\n",
                    "ai/STATE.md": b"state\r\n", ".gitattributes": b"* -text\r\n",
                    ".gitignore": b"# ours\r\nai/logs/\r\n"}
        self.seed(original)
        p = self.run_bootstrap()
        self.assert_complete(p)
        for name in ("AGENTS.md", "ai/STATE.md", ".gitattributes"):
            self.assertEqual((self.root / name).read_bytes(), original[name])
        self.assertEqual((self.root / "CLAUDE.md").read_bytes(), b"@AGENTS.md\n" + original["CLAUDE.md"])
        self.assertEqual((self.root / ".gitignore").read_bytes(),
                         original[".gitignore"] + b".claude/settings.local.json\nCLAUDE.local.md\n")
        self.assertIn("may be missing", p.stdout)

    def test_dirty_staged_unstaged_untracked_are_byte_and_index_identical(self):
        self.seed({"staged.txt": b"old", "unstaged.txt": b"old", "both.txt": b"old"})
        self.write("staged.txt", b"staged")
        self.write("both.txt", b"index")
        self.git("add", "--", "staged.txt", "both.txt")
        self.write("both.txt", b"worktree")
        self.write("unstaged.txt", b"\x00\xff\r\n")
        self.write("untracked space.txt", b"user")
        index = self.git("ls-files", "--stage", "-z")
        status = self.git("status", "--porcelain=v1", "-z", "--untracked-files=all")
        snapshots = {name: (self.root / name).read_bytes() for name in
                     ("staged.txt", "unstaged.txt", "both.txt", "untracked space.txt")}
        p = self.run_bootstrap()
        self.assert_complete(p)
        for name, data in snapshots.items():
            self.assertEqual((self.root / name).read_bytes(), data)
        self.assertEqual(self.git("status", "--porcelain=v1", "-z", "--untracked-files=all"), status)
        for entry in index.split(b"\0"):
            if entry:
                self.assertIn(entry + b"\0", self.git("ls-files", "--stage", "-z"))
        committed = self.git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").decode().splitlines()
        self.assertFalse(set(snapshots) & set(committed))
        self.assertEqual(self.git("show", "HEAD:staged.txt"), b"old")
        self.assertIn("STATUS: LOCAL-ONLY", p.stdout)

    def test_dirty_protocol_needing_repair_refused_before_writes(self):
        self.seed({"CLAUDE.md": b"base"})
        self.write("CLAUDE.md", b"user change")
        p = self.run_bootstrap()
        self.assertIn("Pre-existing user change", p.stderr)
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertEqual((self.root / "CLAUDE.md").read_bytes(), b"user change")

    def test_untracked_protocol_file_preserved(self):
        self.seed()
        self.write("AGENTS.md", b"user content")
        p = self.run_bootstrap()
        self.assert_complete(p)
        self.assertEqual(self.git("ls-files", "--", "AGENTS.md"), b"")
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), b"user content")

    def test_gitattributes_missing_stays_missing(self):
        self.seed()
        self.assert_complete(self.run_bootstrap())
        self.assertFalse((self.root / ".gitattributes").exists())

    def test_no_origin_reports_checker_verbatim(self):
        p = self.run_bootstrap()
        self.assertIn('"origin status": "LOCAL-ONLY"', p.stdout)
        self.assertIn("STATUS: LOCAL-ONLY", p.stdout)
        self.assertNotIn("Manual push", p.stdout)
        self.assertEqual(p.returncode, 0)

    def test_origin_never_pushed_checker_does_not_fetch_or_run_hooks(self):
        remote = self.root / "remote.git"
        self.git("init", "--bare", "-q", str(remote))
        self.git("remote", "add", "origin", str(remote))
        self.seed()
        hooks = self.root / ".git/hooks"
        self.write(".git/hooks/pre-push", b"#!/bin/sh\necho bad > hook-ran\nexit 1\n")
        (hooks / "pre-push").chmod(0o755)
        p = self.run_bootstrap()
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("git push -u origin main", p.stdout)
        self.assertFalse((self.root / ".git/FETCH_HEAD").exists())
        self.assertFalse((self.root / "hook-ran").exists())
        self.assertEqual(self.git("--git-dir=" + str(remote), "for-each-ref", "--format=%(refname)"), b"")

    def test_detached_refused(self):
        self.seed()
        self.git("checkout", "--detach", "-q")
        p = self.run_bootstrap()
        self.assertIn("Detached HEAD", p.stderr)
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_merge_and_rebase_refused(self):
        self.seed()
        for name in ("MERGE_HEAD", "rebase-merge", "rebase-apply"):
            with self.subTest(marker=name):
                marker = self.root / ".git" / name
                if name == "MERGE_HEAD":
                    marker.write_bytes(self.git("rev-parse", "HEAD"))
                else:
                    marker.mkdir()
                p = self.run_bootstrap()
                self.assertIn("Merge/rebase in progress", p.stderr)
                self.assertFalse((self.root / "AGENTS.md").exists())
                marker.unlink() if marker.is_file() else marker.rmdir()

    def test_missing_identity_refused(self):
        for key in ("user.name", "user.email"):
            with self.subTest(key=key):
                self.git("config", key, "")
                p = self.run_bootstrap()
                self.assertIn("Missing git " + key, p.stderr)
                self.assertFalse((self.root / "AGENTS.md").exists())
                self.git("config", key, "test")

    def test_unborn_with_staged_user_file(self):
        self.write("user.txt", b"staged user")
        self.git("add", "--", "user.txt")
        p = self.run_bootstrap()
        self.assert_complete(p)
        self.assertIn(b"A  user.txt", self.git("status", "--porcelain"))
        self.assertNotIn(b"user.txt", self.git("ls-tree", "--name-only", "HEAD"))
        handoff = next((self.root / "ai/handoffs").glob("*.md")).read_text()
        self.assertIn("base_sha: none\nhead_sha: none", handoff)
        self.assertEqual(self.git("rev-list", "--count", "HEAD").strip(), b"1")

    def test_idempotent_no_duplicate_handoff_or_commit(self):
        self.assert_complete(self.run_bootstrap())
        head = self.git("rev-parse", "HEAD")
        files = self.git("ls-files")
        p = self.run_bootstrap()
        self.assertIn("already structurally bootstrapped", p.stdout)
        self.assertIn("no commit needed", p.stdout)
        self.assertIn("ai-check exit code:", p.stdout)
        self.assertEqual(head, self.git("rev-parse", "HEAD"))
        self.assertEqual(files, self.git("ls-files"))
        self.assertEqual(self.git("status", "--porcelain"), b"")

    def test_subdirectory_resolves_root(self):
        self.seed()
        folder = self.root / "nested"
        folder.mkdir()
        self.assert_complete(self.run_bootstrap(folder))
        self.assertTrue((self.root / "AGENTS.md").exists())
        self.assertFalse((folder / "AGENTS.md").exists())

    def test_missing_state_gets_new_handoff(self):
        name = "ai/handoffs/20260101T000000Z-human-task.md"
        self.seed({name: b"---\nhead_sha: none\n---\n"})
        self.assert_complete(self.run_bootstrap())
        handoffs = sorted((self.root / "ai/handoffs").glob("*.md"))
        self.assertEqual(len(handoffs), 2)
        self.assertEqual((self.root / name).read_bytes(), b"---\nhead_sha: none\n---\n")
        self.assertIn(handoffs[-1].name, (self.root / "ai/STATE.md").read_text())

    def test_renamed_dirty_paths_preserved(self):
        self.seed({"old name.txt": b"user"})
        self.git("mv", "--", "old name.txt", "new name.txt")
        before = self.git("status", "--porcelain=v1", "-z")
        self.assert_complete(self.run_bootstrap())
        self.assertEqual(before, self.git("status", "--porcelain=v1", "-z"))

    def test_ignored_existing_protocol_file_is_never_modified(self):
        self.seed({".gitignore": b"CLAUDE.md\n"})
        self.write("CLAUDE.md", b"private user instructions")
        p = self.run_bootstrap()
        self.assertIn("untracked/ignored protocol file", p.stderr)
        self.assertEqual((self.root / "CLAUDE.md").read_bytes(), b"private user instructions")
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_ignored_new_protocol_path_refused_before_writes(self):
        self.seed({".gitignore": b"ai/\n"})
        p = self.run_bootstrap()
        self.assertIn("Protocol path is ignored", p.stderr)
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_assume_unchanged_path_refused(self):
        self.seed({"CLAUDE.md": b"base"})
        self.git("update-index", "--assume-unchanged", "CLAUDE.md")
        self.write("CLAUDE.md", b"invisible user change")
        p = self.run_bootstrap()
        self.assertIn("assume-unchanged/skip-worktree", p.stderr)
        self.assertEqual((self.root / "CLAUDE.md").read_bytes(), b"invisible user change")
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_invalid_agent_refused(self):
        p = self.run_bootstrap(agent="../unsafe")
        self.assertNotEqual(p.returncode, 0)
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_parent_file_refused_before_writes(self):
        self.seed({"ai": b"not a directory"})
        p = self.run_bootstrap()
        self.assertIn("Expected directory", p.stderr)
        self.assertFalse((self.root / "AGENTS.md").exists())

    def test_packaged_template_is_used(self):
        self.assert_complete(self.run_bootstrap())
        template = bootstrap.resources.files("ai_protocol").joinpath("templates/AGENTS.md").read_bytes()
        self.assertEqual((self.root / "AGENTS.md").read_bytes(), template.replace(b"\r\n", b"\n"))

    def test_repair_creates_new_committed_handoff(self):
        self.assert_complete(self.run_bootstrap())
        original = {p.name: p.read_bytes() for p in (self.root / "ai/handoffs").glob("*.md")}
        state = (self.root / "ai/STATE.md").read_bytes()
        self.write(".gitignore", b"ai/logs/\n")
        self.git("add", "--", ".gitignore")
        self.git("commit", "-qm", "remove protocol ignore entries")
        self.assert_complete(self.run_bootstrap())
        handoffs = sorted((self.root / "ai/handoffs").glob("*.md"))
        self.assertEqual(len(handoffs), 2)
        for name, data in original.items():
            self.assertEqual((self.root / "ai/handoffs" / name).read_bytes(), data)
        self.assertEqual((self.root / "ai/STATE.md").read_bytes(), state)
        changed = self.git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").decode()
        self.assertIn(handoffs[-1].name, changed)
        p = subprocess.run([sys.executable, "-m", "ai_protocol.check", "--close", "--allow-local"],
                           cwd=self.root, env=self.env, capture_output=True, text=True, timeout=90)
        self.assertIn("[PASS] HEAD commit is a handoff commit", p.stdout)
        self.assertIn("[PASS] latest handoff committed at HEAD", p.stdout)

    def test_blocked_checker_returns_one(self):
        self.git("remote", "add", "origin", str(self.root / "missing-remote.git"))
        p = self.run_bootstrap()
        self.assertIn("Bootstrap structure created successfully.", p.stdout)
        self.assertIn("STATUS: BLOCKED", p.stdout)
        self.assertIn("ai-check exit code: 1", p.stdout)
        self.assertEqual(p.returncode, 1)

    def test_stop_returns_one(self):
        self.git("config", "user.email", "")
        p = self.run_bootstrap()
        self.assertIn("STOP", p.stderr)
        self.assertEqual(p.returncode, 1)

    def test_both_versions(self):
        for module, command in (("check", "ai-check"), ("bootstrap", "ai-bootstrap")):
            with self.subTest(command=command):
                p = subprocess.run([sys.executable, "-m", "ai_protocol." + module, "--version"],
                                   cwd=self.root, env=self.env, capture_output=True, text=True)
                self.assertEqual(p.returncode, 0)
                self.assertEqual(p.stdout.strip(), command + " 0.2.0")

    def test_concurrent_user_change_stops_before_staging(self):
        self.seed()
        self.write("project.txt", b"user")
        previous = Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, previous)
        real = bootstrap.fingerprint
        calls = []
        def changed(name):
            calls.append(name)
            if len(calls) == 2:
                Path(name).write_bytes(b"concurrent edit")
            return real(name)
        with patch.object(bootstrap, "fingerprint", side_effect=changed):
            with self.assertRaisesRegex(bootstrap.Stop, "Pre-existing user path changed"):
                bootstrap.run("test")
        self.assertFalse((self.root / "AGENTS.md").exists())
        self.assertEqual(self.git("diff", "--cached", "--name-only"), b"")


if __name__ == "__main__":
    unittest.main()
