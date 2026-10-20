import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from envguard.exceptions import ParseError
from envguard.parser import parse_env_content
from envguard.syncer import compare_env_files, generate_example_template, sync_env_files


class TestEnvSyncer(unittest.TestCase):
    def test_compare_env_files(self):
        tmpl = parse_env_content("PORT=3000\nDB_URL=postgres://...\nDEBUG=true")
        target = parse_env_content("PORT=3000\nEXTRA_VAR=123\nDEBUG=<YOUR_DEBUG_HERE>")

        diff = compare_env_files(tmpl, target)
        self.assertEqual(diff.missing_in_target, ["DB_URL"])
        self.assertEqual(diff.extra_in_target, ["EXTRA_VAR"])
        self.assertEqual(diff.empty_in_target, ["DEBUG"])
        self.assertEqual(diff.matching_keys, ["PORT"])

    def test_sync_env_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpl_file = Path(tmpdir) / ".env.example"
            target_file = Path(tmpdir) / ".env"

            tmpl_file.write_text("PORT=3000\nNEW_FEATURE_FLAG=false # Enable v2", encoding="utf-8")
            target_file.write_text("PORT=8080", encoding="utf-8")

            updated, added = sync_env_files(tmpl_file, target_file)
            self.assertTrue(updated)
            self.assertEqual(added, ["NEW_FEATURE_FLAG"])

            synced_content = target_file.read_text(encoding="utf-8")
            self.assertIn("PORT=8080", synced_content)
            self.assertIn("NEW_FEATURE_FLAG=false", synced_content)

    def test_generate_example_template(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src_file = Path(tmpdir) / ".env"
            src_file.write_text("PORT=3000\nAPI_SECRET=my_ultra_secret_key_12345", encoding="utf-8")

            template = generate_example_template(src_file, mask_secrets=True)
            self.assertIn("PORT=3000", template)
            self.assertIn("API_SECRET=<YOUR_API_SECRET_HERE>", template)
            self.assertNotIn("my_ultra_secret_key_12345", template)

    def test_sync_creates_missing_target_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpl_file = Path(tmpdir) / ".env.example"
            target_file = Path(tmpdir) / ".env"
            tmpl_file.write_text("PORT=3000\n", encoding="utf-8")
            updated, added = sync_env_files(tmpl_file, target_file)
            self.assertTrue(updated)
            self.assertEqual(added, ["PORT"])
            self.assertIn("PORT=3000", target_file.read_text(encoding="utf-8"))

    def test_generate_example_no_mask(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / ".env"
            src.write_text("JWT_SECRET=super_secret\n", encoding="utf-8")
            template = generate_example_template(src, mask_secrets=False)
            self.assertIn("JWT_SECRET=super_secret", template)

    def test_sync_preserves_existing_and_appends_newline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpl_file = Path(tmpdir) / ".env.example"
            target_file = Path(tmpdir) / ".env"
            tmpl_file.write_text("A=1\nB=2\n", encoding="utf-8")
            target_file.write_text("A=1", encoding="utf-8")
            updated, added = sync_env_files(tmpl_file, target_file)
            self.assertEqual(added, ["B"])
            content = target_file.read_text(encoding="utf-8")
            lines = content.splitlines()
            self.assertEqual(lines[0], "A=1")
            self.assertIn("B=2", content)

    def test_generate_example_masks_credential_urls(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / ".env"
            src.write_text(
                "DATABASE_URL=postgres://admin:s3cr3t@db.example.com:5432/app\n"
                "REDIS_URL=redis://default:hunter2@cache.example.com:6379\n"
                "APP_URL=https://app.example.com\n",
                encoding="utf-8",
            )

            template = generate_example_template(src, mask_secrets=True)
            self.assertIn("DATABASE_URL=<YOUR_DATABASE_URL_HERE>", template)
            self.assertIn("REDIS_URL=<YOUR_REDIS_URL_HERE>", template)
            self.assertNotIn("s3cr3t", template)
            self.assertNotIn("hunter2", template)
            self.assertIn("APP_URL=https://app.example.com", template)

    def test_generate_example_masks_common_secret_key_names(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / ".env"
            src.write_text("API_PWD=letmein\nSESSION_ID=abc123\n", encoding="utf-8")

            template = generate_example_template(src, mask_secrets=True)
            self.assertIn("API_PWD=<YOUR_API_PWD_HERE>", template)
            self.assertIn("SESSION_ID=<YOUR_SESSION_ID_HERE>", template)
            self.assertNotIn("letmein", template)
            self.assertNotIn("abc123", template)

    def test_generate_example_no_mask_keeps_credential_urls(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / ".env"
            src.write_text("DATABASE_URL=postgres://admin:s3cr3t@db.example.com/app\n", encoding="utf-8")

            template = generate_example_template(src, mask_secrets=False)
            self.assertIn("postgres://admin:s3cr3t@db.example.com/app", template)

    def test_generate_example_masks_credential_urls_without_username(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / ".env"
            src.write_text(
                "REDIS_URL=redis://:s3cr3t@cache.example.com:6379/0\n"
                "DATABASE_URL=jdbc:postgresql://admin:s3cr3t@db.example.com:5432/app\n"
                "BROKER_URL=amqp://user:pa/ss@broker.example.com/\n",
                encoding="utf-8",
            )

            template = generate_example_template(src, mask_secrets=True)
            self.assertIn("REDIS_URL=<YOUR_REDIS_URL_HERE>", template)
            self.assertIn("DATABASE_URL=<YOUR_DATABASE_URL_HERE>", template)
            self.assertIn("BROKER_URL=<YOUR_BROKER_URL_HERE>", template)
            self.assertNotIn("s3cr3t", template)
            self.assertNotIn("pa/ss", template)

    def test_generate_example_masks_plural_creds_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / ".env"
            src.write_text("AWS_CREDS=AKIAIOSFODNN7EXAMPLE\nDB_CREDS=letmein\n", encoding="utf-8")

            template = generate_example_template(src, mask_secrets=True)
            self.assertIn("AWS_CREDS=<YOUR_AWS_CREDS_HERE>", template)
            self.assertIn("DB_CREDS=<YOUR_DB_CREDS_HERE>", template)
            self.assertNotIn("AKIAIOSFODNN7EXAMPLE", template)
            self.assertNotIn("letmein", template)

    def test_generate_example_masks_pat_and_sk_keys_without_over_masking(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / ".env"
            src.write_text(
                "GITHUB_PAT=ghp_secretvalue\n"
                "STRIPE_SK=sk_live_secretvalue\n"
                "PATH=/usr/local/bin\n"
                "TASK=build\n",
                encoding="utf-8",
            )

            template = generate_example_template(src, mask_secrets=True)
            self.assertIn("GITHUB_PAT=<YOUR_GITHUB_PAT_HERE>", template)
            self.assertIn("STRIPE_SK=<YOUR_STRIPE_SK_HERE>", template)
            self.assertNotIn("ghp_secretvalue", template)
            self.assertNotIn("sk_live_secretvalue", template)
            self.assertIn("PATH=/usr/local/bin", template)
            self.assertIn("TASK=build", template)


    def test_generate_example_preserves_values_that_need_quoting(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            src = Path(tmpdir) / ".env"
            src.write_text(
                'FLAG="#fff"\n'
                'GREETING="  spaced  "\n'
                'CERT="-----BEGIN-----\nABC\n-----END-----"\n'
                'URLS="https://a.test/#frag"\n',
                encoding="utf-8",
            )

            template = generate_example_template(src, mask_secrets=False)
            reparsed = parse_env_content(template)

            self.assertEqual(reparsed.get("FLAG"), "#fff")
            self.assertEqual(reparsed.get("GREETING"), "  spaced  ")
            self.assertEqual(reparsed.get("CERT"), "-----BEGIN-----\nABC\n-----END-----")
            self.assertEqual(reparsed.get("URLS"), "https://a.test/#frag")


    def test_sync_uses_a_single_blank_separator_line(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpl_file = Path(tmpdir) / ".env.example"

            for original in ("A=1", "A=1\n"):
                with self.subTest(original=repr(original)):
                    target_file = Path(tmpdir) / "case.env"
                    target_file.write_text(original, encoding="utf-8")
                    tmpl_file.write_text("A=1\nB=2\n", encoding="utf-8")

                    sync_env_files(tmpl_file, target_file)
                    content = target_file.read_text(encoding="utf-8")

                    self.assertTrue(
                        content.startswith("A=1\n\n# --- Added by envguard sync ---\nB=2\n"),
                        msg=repr(content),
                    )
                    self.assertNotIn("\n\n\n", content)

    def test_sync_preserves_existing_file_mode(self):
        if os.name == "nt":
            self.skipTest("POSIX permission bits are not available on Windows")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpl_file = Path(tmpdir) / ".env.example"
            target_file = Path(tmpdir) / ".env"
            tmpl_file.write_text("A=1\nB=2\n", encoding="utf-8")
            target_file.write_text("A=1\n", encoding="utf-8")
            target_file.chmod(0o600)

            sync_env_files(tmpl_file, target_file)

            self.assertEqual(target_file.stat().st_mode & 0o777, 0o600)

    def test_sync_leaves_no_temporary_files_behind(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpl_file = Path(tmpdir) / ".env.example"
            target_file = Path(tmpdir) / ".env"
            tmpl_file.write_text("A=1\nB=2\n", encoding="utf-8")
            target_file.write_text("A=1\n", encoding="utf-8")

            sync_env_files(tmpl_file, target_file)

            self.assertEqual(sorted(p.name for p in Path(tmpdir).iterdir()), [".env", ".env.example"])

    def test_sync_failure_leaves_original_content_untouched(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpl_file = Path(tmpdir) / ".env.example"
            target_file = Path(tmpdir) / ".env"
            tmpl_file.write_text("A=1\nB=2\n", encoding="utf-8")
            original = "A=1\nSECRET=keep-me\n"
            target_file.write_text(original, encoding="utf-8")

            with mock.patch("envguard.syncer.os.replace", side_effect=OSError("disk full")):
                with self.assertRaises(OSError):
                    sync_env_files(tmpl_file, target_file)

            self.assertEqual(target_file.read_text(encoding="utf-8"), original)
            self.assertEqual(sorted(p.name for p in Path(tmpdir).iterdir()), [".env", ".env.example"])

    def test_new_target_file_is_private(self):
        if os.name == "nt":
            self.skipTest("POSIX permission bits are not available on Windows")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpl_file = Path(tmpdir) / ".env.example"
            target_file = Path(tmpdir) / ".env"
            tmpl_file.write_text("PORT=3000\n", encoding="utf-8")

            sync_env_files(tmpl_file, target_file)

            self.assertEqual(target_file.stat().st_mode & 0o777, 0o600)

    def test_sync_follows_symlinked_target(self):
        if os.name == "nt":
            self.skipTest("symlink creation needs elevated privileges on Windows")

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpl_file = Path(tmpdir) / ".env.example"
            real_file = Path(tmpdir) / "shared.env"
            link_file = Path(tmpdir) / ".env"
            tmpl_file.write_text("A=1\nB=2\n", encoding="utf-8")
            real_file.write_text("A=1\n", encoding="utf-8")
            link_file.symlink_to(real_file)

            sync_env_files(tmpl_file, link_file)

            self.assertTrue(link_file.is_symlink())
            self.assertIn("B=2", real_file.read_text(encoding="utf-8"))

    def test_sync_preserves_crlf_line_endings(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpl_file = Path(tmpdir) / ".env.example"
            target_file = Path(tmpdir) / ".env"
            tmpl_file.write_text("A=1\nB=2\n", encoding="utf-8")
            target_file.write_bytes(b"A=1\r\n")

            sync_env_files(tmpl_file, target_file)

            raw = target_file.read_bytes()
            self.assertIn(b"A=1\r\n", raw)
            self.assertIn(b"B=2\r\n", raw)
            self.assertNotIn(b"\r\r\n", raw)
            self.assertNotIn(b"\n", raw.replace(b"\r\n", b""))

    def test_sync_preserves_utf8_bom(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpl_file = Path(tmpdir) / ".env.example"
            target_file = Path(tmpdir) / ".env"
            tmpl_file.write_text("A=1\nB=2\n", encoding="utf-8")
            target_file.write_bytes(b"\xef\xbb\xbfA=1\n")

            sync_env_files(tmpl_file, target_file)

            raw = target_file.read_bytes()
            self.assertTrue(raw.startswith(b"\xef\xbb\xbf"), msg=raw[:8])
            parsed = parse_env_content(raw.decode("utf-8-sig"))
            self.assertEqual(parsed.get("A"), "1")
            self.assertEqual(parsed.get("B"), "2")


    def test_sync_refuses_non_utf8_target_and_leaves_it_untouched(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpl_file = Path(tmpdir) / ".env.example"
            target_file = Path(tmpdir) / ".env"
            tmpl_file.write_text("A=1\nB=2\n", encoding="utf-8")
            original = b"A=1\nNAME=caf\xe9\n"
            target_file.write_bytes(original)

            with self.assertRaises(ParseError):
                sync_env_files(tmpl_file, target_file)

            self.assertEqual(target_file.read_bytes(), original)

    def test_sync_does_not_create_missing_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpl_file = Path(tmpdir) / ".env.example"
            tmpl_file.write_text("A=1\n", encoding="utf-8")
            target_file = Path(tmpdir) / "missing-dir" / ".env"

            with self.assertRaises(OSError):
                sync_env_files(tmpl_file, target_file)

            self.assertFalse((Path(tmpdir) / "missing-dir").exists())

    def test_sync_quotes_values_that_would_change_meaning(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpl_file = Path(tmpdir) / ".env.example"
            target_file = Path(tmpdir) / ".env"
            tmpl_file.write_text('FLAG="#fff"\nNOTE="a #b"\n', encoding="utf-8")
            target_file.write_text("OTHER=1\n", encoding="utf-8")

            sync_env_files(tmpl_file, target_file)
            reparsed = parse_env_content(target_file.read_text(encoding="utf-8"))

            self.assertEqual(reparsed.get("FLAG"), "#fff")
            self.assertEqual(reparsed.get("NOTE"), "a #b")


if __name__ == "__main__":
    unittest.main()
