"""install.sh: local checkout and piped (tarball) paths."""
from __future__ import annotations

import os
import stat
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class InstallShTests(unittest.TestCase):
    def _run(self, args, *, env, cwd=None, stdin=None):
        return subprocess.run(
            args,
            cwd=cwd or REPO,
            env=env,
            input=stdin,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_local_checkout_copies_cli_and_skill(self):
        with tempfile.TemporaryDirectory() as home:
            env = {**os.environ, "HOME": home, "PATH": os.environ.get("PATH", "")}
            result = self._run(["bash", str(REPO / "install.sh")], env=env)
            self.assertEqual(result.returncode, 0, result.stderr)
            binary = Path(home) / ".local/bin/grokbot-usage"
            skill = Path(home) / ".grok/skills/fleet-usage/SKILL.md"
            self.assertTrue(binary.is_file())
            self.assertTrue(skill.is_file())
            self.assertTrue(stat.S_IMODE(binary.stat().st_mode) & 0o100)
            self.assertIn("Install succeeded.", result.stdout)
            self.assertIn(str(binary), result.stdout)
            self.assertIn(str(skill), result.stdout)
            self.assertIn("Next:", result.stdout)

    def test_piped_install_from_file_tarball(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            home.mkdir()
            tar_path = Path(tmp) / "tree.tar.gz"
            prefix = "grokbot-usage-cli-main"
            with tarfile.open(tar_path, "w:gz") as tar:
                tar.add(
                    REPO / "cli/grokbot_usage.py",
                    arcname=f"{prefix}/cli/grokbot_usage.py",
                )
                tar.add(
                    REPO / "cli/skills/fleet-usage/SKILL.md",
                    arcname=f"{prefix}/cli/skills/fleet-usage/SKILL.md",
                )
            script = (REPO / "install.sh").read_text(encoding="utf-8")
            env = {
                **os.environ,
                "HOME": str(home),
                "PATH": os.environ.get("PATH", ""),
                "GROKBOT_USAGE_TARBALL": tar_path.resolve().as_uri(),
            }
            result = self._run(
                ["bash"],
                env=env,
                cwd=tmp,
                stdin=script,
            )
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            binary = home / ".local/bin/grokbot-usage"
            skill = home / ".grok/skills/fleet-usage/SKILL.md"
            self.assertTrue(binary.is_file())
            self.assertTrue(skill.is_file())
            self.assertIn("Install succeeded.", result.stdout)
            self.assertNotIn("npm", result.stdout.lower())


if __name__ == "__main__":
    unittest.main()
