import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
