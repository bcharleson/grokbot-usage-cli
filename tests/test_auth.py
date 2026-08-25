"""Auth ladder, cookie normalization, login/logout, IDE paths."""
from __future__ import annotations

import io
import os
import stat
import unittest
from pathlib import Path
from unittest.mock import patch

from helpers import make_cookie, make_jwt, usage, write_grok_auth, write_vscdb


class NormalizeCookieTests(unittest.TestCase):
    def test_jwt_becomes_workos_cookie(self):
        token = make_jwt("example-user|user_01EXAMPLE")
        cookie = usage.normalize_session_cookie(token)
        self.assertTrue(cookie.startswith("user_01EXAMPLE%3A%3A"))
        self.assertTrue(cookie.endswith(token))

    def test_percent_encoded_cookie_passthrough(self):
        raw = "user_01EXAMPLE%3A%3Aabc.def.ghi"
        self.assertEqual(usage.normalize_session_cookie(raw), raw)

    def test_double_colon_cookie_normalized(self):
        self.assertEqual(
            usage.normalize_session_cookie("user_01EXAMPLE::abc.def.ghi"),
            "user_01EXAMPLE%3A%3Aabc.def.ghi",
        )

    def test_named_cookie_header_stripped(self):
        body = "user_01EXAMPLE%3A%3Aabc.def.ghi"
        raw = "WorkosCursorSessionToken=" + body
        self.assertEqual(usage.normalize_session_cookie(raw), body)

    def test_empty_rejected(self):
        with self.assertRaises(RuntimeError):
            usage.normalize_session_cookie("   ")

    def test_garbage_rejected_without_echoing_secret(self):
        with self.assertRaises(RuntimeError) as ctx:
            usage.normalize_session_cookie("not-a-cookie-or-jwt")
        self.assertNotIn("not-a-cookie-or-jwt", str(ctx.exception))


class AuthLadderTests(unittest.TestCase):
    def test_env_wins_over_file_and_ide(self):
        token = make_jwt()
        env_cookie = make_cookie("from_env", token)
        home = Path(self._home())
        write_vscdb(
            home / ".config/Cursor/User/globalStorage/state.vscdb",
            make_jwt("example-user|from_ide"),
        )
        usage.write_secret_file(
            home / ".secrets/cursor-session-cookie",
            make_cookie("from_file"),
        )
        with patch.dict(os.environ, {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "CURSOR_SESSION_COOKIE": env_cookie,
        }, clear=False):
            self.assertEqual(usage.resolve_cursor_cookie(), env_cookie)

    def test_file_wins_over_ide(self):
        home = Path(self._home())
        file_cookie = make_cookie("from_file")
        write_vscdb(
            home / ".config/Cursor/User/globalStorage/state.vscdb",
            make_jwt("example-user|from_ide"),
        )
        usage.write_secret_file(home / ".secrets/cursor-session-cookie", file_cookie)
        env = {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
        }
        os.environ.pop("CURSOR_SESSION_COOKIE", None)
        with patch.dict(os.environ, env, clear=False):
            self.assertEqual(usage.resolve_cursor_cookie(), file_cookie)

    def test_linux_vscdb_used_when_no_env_or_file(self):
        home = Path(self._home())
        token = make_jwt("example-user|from_linux")
        write_vscdb(
            home / ".config/Cursor/User/globalStorage/state.vscdb",
            token,
        )
        os.environ.pop("CURSOR_SESSION_COOKIE", None)
        with patch.dict(os.environ, {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
        }, clear=False):
            cookie = usage.resolve_cursor_cookie()
        self.assertEqual(cookie, f"from_linux%3A%3A{token}")

    def test_macos_vscdb_used(self):
        home = Path(self._home())
        token = make_jwt("example-user|from_macos")
        write_vscdb(
            home / "Library/Application Support/Cursor/User/globalStorage/state.vscdb",
            token,
        )
        os.environ.pop("CURSOR_SESSION_COOKIE", None)
        with patch.dict(os.environ, {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".empty-xdg"),
        }, clear=False):
            cookie = usage.resolve_cursor_cookie()
        self.assertEqual(cookie, f"from_macos%3A%3A{token}")

    def test_missing_auth_raises_without_secret(self):
        home = Path(self._home())
        os.environ.pop("CURSOR_SESSION_COOKIE", None)
        with patch.dict(os.environ, {
            "HOME": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
        }, clear=False):
            with self.assertRaises(RuntimeError) as ctx:
                usage.resolve_cursor_cookie()
        self.assertNotIn("%3A%3A", str(ctx.exception))

    def _home(self) -> str:
        tmp = self._tmp = getattr(self, "_tmp", None)
        if tmp is None:
            import tempfile
            self._cm = tempfile.TemporaryDirectory()
            self.addCleanup(self._cm.cleanup)
            tmp = self._tmp = self._cm.name
        return tmp


class LoginLogoutTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._cm = tempfile.TemporaryDirectory()
        self.addCleanup(self._cm.cleanup)
        self.home = self._cm.name
        self.env = patch.dict(os.environ, {
            "HOME": self.home,
            "XDG_CONFIG_HOME": str(Path(self.home) / ".config"),
        }, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)
        os.environ.pop("CURSOR_SESSION_COOKIE", None)

    def test_login_from_stdin_writes_0600(self):
        cookie = make_cookie("login_user")
        stdin = io.StringIO(cookie + "\n")
        stdin.isatty = lambda: False  # type: ignore[method-assign]
        with patch.object(usage.sys, "stdin", stdin), \
                patch("sys.stdout", io.StringIO()):
            code = usage.cmd_login(from_ide=False)
        self.assertEqual(code, 0)
        path = Path(self.home) / ".secrets" / "cursor-session-cookie"
        self.assertEqual(path.read_text(encoding="utf-8"), cookie)
        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)

    def test_login_from_ide(self):
        token = make_jwt("example-user|ide_user")
        write_vscdb(
            Path(self.home) / ".config/Cursor/User/globalStorage/state.vscdb",
            token,
        )
        with patch("sys.stdout", io.StringIO()):
            code = usage.cmd_login(from_ide=True)
        self.assertEqual(code, 0)
        stored = (Path(self.home) / ".secrets" / "cursor-session-cookie").read_text()
        self.assertEqual(stored, f"ide_user%3A%3A{token}")

    def test_login_does_not_print_cookie(self):
        cookie = make_cookie("hidden_user")
        buf = io.StringIO()
        stdin = io.StringIO(cookie)
        stdin.isatty = lambda: False  # type: ignore[method-assign]
        with patch.object(usage.sys, "stdin", stdin):
            with patch("sys.stdout", buf), patch("sys.stderr", io.StringIO()):
                usage.cmd_login(from_ide=False)
        out = buf.getvalue()
        self.assertNotIn(cookie, out)
        self.assertNotIn("hidden_user", out)

    def test_logout_removes_file(self):
        path = Path(self.home) / ".secrets" / "cursor-session-cookie"
        usage.write_secret_file(path, make_cookie())
        self.assertTrue(path.is_file())
        with patch("sys.stdout", io.StringIO()):
            self.assertEqual(usage.cmd_logout(), 0)
        self.assertFalse(path.exists())
        with patch("sys.stdout", io.StringIO()):
            self.assertEqual(usage.cmd_logout(), 0)

    def test_login_cookie_file(self):
        cookie = make_cookie("file_user")
        src = Path(self.home) / "cursor-cookie.txt"
        src.write_text(cookie + "\n", encoding="utf-8")
        with patch("sys.stdout", io.StringIO()) as out:
            code = usage.cmd_login(from_ide=False, cookie_file=str(src))
        self.assertEqual(code, 0)
        stored = Path(self.home) / ".secrets" / "cursor-session-cookie"
        self.assertEqual(stored.read_text(encoding="utf-8"), cookie)
        self.assertEqual(stat.S_IMODE(stored.stat().st_mode), 0o600)
        self.assertNotIn(cookie, out.getvalue())

    def test_login_cookie_file_via_main(self):
        cookie = make_cookie("main_file")
        src = Path(self.home) / "cursor-cookie.txt"
        src.write_text("WorkosCursorSessionToken=" + cookie, encoding="utf-8")
        with patch("sys.stdout", io.StringIO()):
            self.assertEqual(usage.main(["login", "--cookie-file", str(src)]), 0)
        stored = (Path(self.home) / ".secrets" / "cursor-session-cookie").read_text()
        self.assertEqual(stored, cookie)

    def test_cookie_file_and_from_ide_conflict(self):
        err = io.StringIO()
        with patch("sys.stderr", err):
            code = usage.cmd_login(from_ide=True, cookie_file="x")
        self.assertEqual(code, 2)
        self.assertIn("not both", err.getvalue())

    def test_main_login_logout(self):
        cookie = make_cookie("main_user")
        stdin = io.StringIO(cookie)
        stdin.isatty = lambda: False  # type: ignore[method-assign]
        with patch.object(usage.sys, "stdin", stdin), \
                patch("sys.stdout", io.StringIO()):
            self.assertEqual(usage.main(["login"]), 0)
        self.assertTrue((Path(self.home) / ".secrets" / "cursor-session-cookie").is_file())
        with patch("sys.stdout", io.StringIO()):
            self.assertEqual(usage.main(["logout"]), 0)


class GrokBearerTests(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._cm = tempfile.TemporaryDirectory()
        self.addCleanup(self._cm.cleanup)
        self.home = self._cm.name
        self.env = patch.dict(os.environ, {"HOME": self.home}, clear=False)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_missing_file(self):
        with self.assertRaises(RuntimeError) as ctx:
            usage.grok_bearer()
        self.assertIn("auth.json", str(ctx.exception))
        self.assertIn("device-auth", str(ctx.exception))

    def test_reads_access_token_without_echo(self):
        token = make_jwt("example-user|grok_auth")
        write_grok_auth(Path(self.home) / ".grok" / "auth.json", token)
        self.assertEqual(usage.grok_bearer(), token)
        empty = usage.find_bearer({"note": "no token here"})
        self.assertIsNone(empty)

    def test_nested_xai_oauth_prefix(self):
        token = "xai-" + "oauth" + "EXAMPLETOKENVALUE"
        blob = {"session": {"nested": {"access_token": token}}}
        self.assertEqual(usage.find_bearer(blob), token)

    def test_empty_file_is_error(self):
        path = Path(self.home) / ".grok" / "auth.json"
        path.parent.mkdir(parents=True)
        path.write_text("{}\n", encoding="utf-8")
        with self.assertRaises(RuntimeError) as ctx:
            usage.grok_bearer()
        self.assertIn("no bearer", str(ctx.exception))


class SafeErrorTests(unittest.TestCase):
    def test_redacts_jwt_and_cookie(self):
        token = make_jwt()
        cookie = make_cookie("leak", token)
        text = usage.safe_error(RuntimeError(
            f"WorkosCursorSessionToken={cookie} also {token}"
        ))
        self.assertNotIn(token, text)
        self.assertNotIn(cookie, text)
        self.assertIn("<redacted>", text)


if __name__ == "__main__":
    unittest.main()
