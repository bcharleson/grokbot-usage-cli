"""CLI flags: --json --write, --quiet --threshold, fail-open, no secret leakage."""
from __future__ import annotations

import io
import json
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import (
    CURSOR_SUMMARY,
    GROKBOT_STATUS,
    make_cookie,
    make_jwt,
    usage,
)


class CliTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._cm = tempfile.TemporaryDirectory()
        self.addCleanup(self._cm.cleanup)
        self.home = self._cm.name
        self.cookie = make_cookie("cli_user", make_jwt("example-user|cli_user"))
        self.env = patch.dict(os.environ, {
            "HOME": self.home,
            "XDG_CONFIG_HOME": str(Path(self.home) / ".config"),
            "CURSOR_SESSION_COOKIE": self.cookie,
        }, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def _http(self, grokbot=None, cursor=None):
        grokbot = GROKBOT_STATUS if grokbot is None else grokbot
        cursor = CURSOR_SUMMARY if cursor is None else cursor

        def fake(method, url, **kwargs):
            if "usage-summary" in url:
                if isinstance(cursor, Exception):
                    raise cursor
                return cursor
            if "get-sand-usage-status" in url:
                if isinstance(grokbot, Exception):
                    raise grokbot
                return grokbot
            raise AssertionError(f"unexpected url {url}")

        return patch.object(usage, "http_json", side_effect=fake)

    def test_json_write_default(self):
        buf = io.StringIO()
        with self._http(), patch("sys.stdout", buf):
            code = usage.main(["--json", "--write", "default"])
        self.assertEqual(code, 0)
        ledger = Path(self.home) / ".grokbot-usage" / "latest.json"
        data = json.loads(ledger.read_text(encoding="utf-8"))
        self.assertIn("asOf", data)
        self.assertEqual(data["grokbot"]["weeklyPercentUsed"], 55)
        self.assertEqual(data["cursor"]["onDemandUsedUSD"], 8.0)
        printed = json.loads(buf.getvalue())
        self.assertEqual(printed["grokbot"]["weeklyPercentUsed"], 55)
        blob = ledger.read_text() + buf.getvalue()
        self.assertNotIn(self.cookie, blob)
        self.assertNotIn("cli_user", blob)

    def test_write_explicit_path(self):
        dest = Path(self.home) / "out" / "usage.json"
        with self._http(), patch("sys.stdout", io.StringIO()):
            code = usage.main(["--json", "--write", str(dest)])
        self.assertEqual(code, 0)
        data = json.loads(dest.read_text(encoding="utf-8"))
        self.assertEqual(data["cursor"]["planPercentUsed"], 40.0)

    def test_quiet_below_threshold(self):
        with self._http(), patch("sys.stdout", io.StringIO()) as out, \
                patch("sys.stderr", io.StringIO()) as err:
            code = usage.main(["--quiet", "--threshold", "90"])
        self.assertEqual(code, 0)
        self.assertEqual(out.getvalue(), "")
        self.assertEqual(err.getvalue(), "")

    def test_quiet_at_threshold(self):
        grok = dict(GROKBOT_STATUS, usagePercent=90)
        err = io.StringIO()
        with self._http(grokbot=grok), patch("sys.stdout", io.StringIO()), \
                patch("sys.stderr", err):
            code = usage.main(["--quiet", "--threshold", "90"])
        self.assertEqual(code, 1)
        self.assertIn("90%", err.getvalue())
        self.assertNotIn(self.cookie, err.getvalue())

    def test_quiet_error_is_breach(self):
        err = io.StringIO()
        with self._http(grokbot=RuntimeError("nope")), \
                patch("sys.stdout", io.StringIO()), patch("sys.stderr", err):
            code = usage.main(["--quiet"])
        self.assertEqual(code, 1)
        self.assertIn("unavailable", err.getvalue())

    def test_quiet_missing_percent_is_breach(self):
        grok = dict(GROKBOT_STATUS)
        grok.pop("usagePercent")
        with self._http(grokbot=grok), patch("sys.stdout", io.StringIO()), \
                patch("sys.stderr", io.StringIO()):
            self.assertEqual(usage.main(["--quiet", "--threshold", "90"]), 1)

    def test_threshold_from_env(self):
        grok = dict(GROKBOT_STATUS, usagePercent=80)
        with patch.dict(os.environ, {"GROKBOT_USAGE_WEEKLY_BUDGET": "70"}):
            with self._http(grokbot=grok), patch("sys.stdout", io.StringIO()), \
                    patch("sys.stderr", io.StringIO()):
                self.assertEqual(usage.main(["--quiet"]), 1)

    def test_fail_open_per_meter(self):
        buf = io.StringIO()
        with self._http(cursor=RuntimeError("cursor down")), \
                patch("sys.stdout", buf):
            code = usage.main(["--json"])
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertIn("error", data["cursor"])
        self.assertEqual(data["grokbot"]["weeklyPercentUsed"], 55)
        self.assertNotIn("percent", data["cursor"])

    def test_every_meter_failed_exits_1(self):
        buf = io.StringIO()
        with self._http(cursor=RuntimeError("a"), grokbot=RuntimeError("b")), \
                patch("sys.stdout", buf):
            code = usage.main(["--json"])
        self.assertEqual(code, 1)
        data = json.loads(buf.getvalue())
        self.assertIn("error", data["cursor"])
        self.assertIn("error", data["grokbot"])

    def test_meter_filter(self):
        buf = io.StringIO()
        with self._http(), patch("sys.stdout", buf):
            code = usage.main(["--json", "--meter", "grokbot"])
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertIn("grokbot", data)
        self.assertNotIn("cursor", data)

    def test_human_unavailable_wording(self):
        buf = io.StringIO()
        with self._http(grokbot=RuntimeError("gone")), patch("sys.stdout", buf):
            usage.main([])
        self.assertIn("unavailable", buf.getvalue())
        self.assertNotIn(self.cookie, buf.getvalue())

    def test_from_ide_requires_login(self):
        with self.assertRaises(SystemExit) as ctx:
            usage.main(["--from-ide"])
        self.assertEqual(ctx.exception.code, 2)

    def test_help_has_only_two_meters(self):
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            with self.assertRaises(SystemExit):
                usage.main(["--help"])
        text = buf.getvalue().lower()
        self.assertNotIn("super" + "grok", text)
        self.assertNotIn("cli-chat-" + "proxy", text)


if __name__ == "__main__":
    unittest.main()
