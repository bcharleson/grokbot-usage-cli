"""Meter parsing and mocked HTTP."""
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch

from helpers import (
    CURSOR_SUMMARY,
    GROKBOT_STATUS,
    SUPERGROK_BILLING,
    make_cookie,
    make_jwt,
    usage,
)


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

    def test_meter_supergrok_maps_credits(self):
        token = make_jwt("example-user|sg")
        with patch.object(usage, "http_json", return_value=SUPERGROK_BILLING) as http:
            result = usage.meter_supergrok(token)
        args, kwargs = http.call_args
        self.assertEqual(args[0], "GET")
        self.assertIn("billing?format=credits", args[1])
        self.assertEqual(kwargs["bearer"], token)
        self.assertEqual(
            kwargs["extra_headers"][usage.XAI_TOKEN_AUTH_HEADER],
            usage.XAI_TOKEN_AUTH_VALUE,
        )
        self.assertNotIn("cookie", kwargs)
        self.assertIsNone(kwargs.get("cookie"))
        self.assertEqual(result["weeklyPercentUsed"], 22.0)
        self.assertEqual(result["resetsAt"], "2026-01-16T12:00:00.000Z")
        self.assertNotIn("error", result)

    def test_supergrok_meter_is_optional_choice(self):
        parser = usage.build_parser()
        args = parser.parse_args(["--meter", "supergrok"])
        self.assertEqual(args.meter, "supergrok")


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

    def test_supergrok_headers_without_cursor_cookie(self):
        token = make_jwt("example-user|sg")
        body = json.dumps({"ok": True}).encode()
        resp = MagicMock()
        resp.read.return_value = body
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = False
        captured = {}

        def fake_urlopen(req, data=None, timeout=15):
            captured["headers"] = {k.lower(): v for k, v in req.header_items()}
            captured["cookie"] = req.get_header("Cookie")
            return resp

        with patch.object(usage.urllib.request, "urlopen", side_effect=fake_urlopen):
            usage.http_json(
                "GET",
                "https://cli-chat-proxy.grok.com/v1/billing?format=credits",
                bearer=token,
                extra_headers={usage.XAI_TOKEN_AUTH_HEADER: usage.XAI_TOKEN_AUTH_VALUE},
            )
        headers = captured["headers"]
        self.assertEqual(headers.get("authorization"), f"Bearer {token}")
        self.assertEqual(headers.get("x-xai-token-auth"), usage.XAI_TOKEN_AUTH_VALUE)
        self.assertIsNone(captured["cookie"])
        self.assertNotIn("cookie", headers)


if __name__ == "__main__":
    unittest.main()
