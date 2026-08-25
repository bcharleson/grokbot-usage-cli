"""Meter parsing and mocked HTTP."""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from helpers import CURSOR_SUMMARY, GROKBOT_STATUS, make_cookie, usage


class MeterParseTests(unittest.TestCase):
    def test_meter_cursor_converts_cents(self):
        with patch.object(usage, "http_json", return_value=CURSOR_SUMMARY) as http:
            result = usage.meter_cursor("example-cookie")
        http.assert_called_once()
        self.assertEqual(result["planPercentUsed"], 40.0)
        self.assertEqual(result["autoPercentUsed"], 44.0)
        self.assertEqual(result["apiPercentUsed"], 5.0)
        self.assertEqual(result["onDemandUsedUSD"], 8.0)
        self.assertEqual(result["onDemandLimitUSD"], 100.0)
        self.assertEqual(result["membership"], "pro")
        self.assertNotIn("error", result)

    def test_meter_cursor_null_ondemand(self):
        payload = {
            "individualUsage": {"plan": {}, "onDemand": {}},
            "membershipType": "free",
        }
        with patch.object(usage, "http_json", return_value=payload):
            result = usage.meter_cursor("example-cookie")
        self.assertIsNone(result["planPercentUsed"])
        self.assertIsNone(result["onDemandUsedUSD"])
        self.assertIsNone(result["onDemandLimitUSD"])

    def test_meter_grokbot(self):
        with patch.object(usage, "http_json", return_value=GROKBOT_STATUS) as http:
            result = usage.meter_grokbot("example-cookie")
        args, kwargs = http.call_args
        self.assertEqual(args[0], "POST")
        self.assertIn("get-sand-usage-status", args[1])
        self.assertEqual(kwargs["body"], {})
        self.assertEqual(result["weeklyPercentUsed"], 55)
        self.assertTrue(result["onDemandEnabled"])
        self.assertEqual(result["planLabel"], "Grok Bot Plan")

    def test_removed_third_meter_rejected(self):
        gone = "super" + "grok"
        self.assertFalse(hasattr(usage, "meter_" + gone))
        parser = usage.build_parser()
        with self.assertRaises(SystemExit):
            parser.parse_args(["--meter", gone])


class HttpJsonTests(unittest.TestCase):
    def test_sets_cookie_and_origin_on_post(self):
        cookie = make_cookie()
        body = json.dumps({"ok": True}).encode()
        resp = MagicMock()
        resp.read.return_value = body
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        captured = {}

        def fake_urlopen(req, data=None, timeout=15):
            captured["cookie"] = req.get_header("Cookie")
            captured["origin"] = req.get_header("Origin")
            captured["data"] = data
            return resp

        with patch.object(usage.urllib.request, "urlopen", side_effect=fake_urlopen):
            result = usage.http_json(
                "POST", "https://cursor.com/api/dashboard/get-sand-usage-status",
                cookie=cookie, body={},
            )
        self.assertEqual(result, {"ok": True})
        self.assertEqual(captured["cookie"], f"WorkosCursorSessionToken={cookie}")
        self.assertEqual(captured["origin"], "https://cursor.com")
        self.assertEqual(captured["data"], b"{}")

    def test_http_error_has_no_body(self):
        import urllib.error

        err = urllib.error.HTTPError(
            url="https://cursor.com/api/usage-summary",
            code=401,
            msg="no",
            hdrs=None,
            fp=None,
        )
        with patch.object(usage.urllib.request, "urlopen", side_effect=err):
            with self.assertRaises(RuntimeError) as ctx:
                usage.http_json("GET", "https://cursor.com/api/usage-summary",
                                cookie=make_cookie())
        self.assertIn("HTTP 401", str(ctx.exception))
        self.assertNotIn("%3A%3A", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
