import argparse
import tempfile
import unittest
from pathlib import Path

from envguard.cli import cmd_check, cmd_diff, cmd_init, cmd_sync


class TestEnvCLI(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_cmd_check_clean(self):
        tmpl = self.base / ".env.example"
        env = self.base / ".env"
        tmpl.write_text("PORT=3000\nAPP_NAME=App\n", encoding="utf-8")
        env.write_text("PORT=8000\nAPP_NAME=MyService\n", encoding="utf-8")

        args = argparse.Namespace(env=str(env), example=str(tmpl), strict=False)
        code = cmd_check(args)
        self.assertEqual(code, 0)

    def test_cmd_check_missing_variable(self):
        tmpl = self.base / ".env.example"
        env = self.base / ".env"
        tmpl.write_text("PORT=3000\nREDIS_URL=redis://localhost\n", encoding="utf-8")
        env.write_text("PORT=8000\n", encoding="utf-8")

        args = argparse.Namespace(env=str(env), example=str(tmpl), strict=False)
        code = cmd_check(args)
        self.assertEqual(code, 1)

    def test_cmd_sync_and_diff(self):
        tmpl = self.base / ".env.example"
        env = self.base / ".env"
        tmpl.write_text("PORT=3000\nAUTH_KEY=123\n", encoding="utf-8")
        env.write_text("PORT=3000\n", encoding="utf-8")

        sync_args = argparse.Namespace(env=str(env), example=str(tmpl), empty=False, dry_run=False)
        self.assertEqual(cmd_sync(sync_args), 0)

        diff_args = argparse.Namespace(env=str(env), example=str(tmpl))
        self.assertEqual(cmd_diff(diff_args), 0)

    def test_cmd_init(self):
        env = self.base / ".env"
        tmpl = self.base / ".env.example"
        env.write_text("PORT=5000\nJWT_SECRET=super_secret_jwt\n", encoding="utf-8")

        args = argparse.Namespace(env=str(env), out=str(tmpl), force=False, no_mask=False)
        self.assertEqual(cmd_init(args), 0)
        self.assertTrue(tmpl.exists())
        self.assertIn("<YOUR_JWT_SECRET_HERE>", tmpl.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
