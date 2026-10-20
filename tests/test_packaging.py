import re
import unittest
from pathlib import Path

import envguard

ROOT = Path(__file__).resolve().parent.parent


def _pyproject() -> str:
    return (ROOT / "pyproject.toml").read_text(encoding="utf-8")


class TestPackaging(unittest.TestCase):
    def test_version_matches_pyproject(self):
        match = re.search(r'^version\s*=\s*"([^"]+)"', _pyproject(), re.MULTILINE)
        self.assertIsNotNone(match, msg="pyproject.toml has no static version")
        self.assertEqual(envguard.__version__, match.group(1))

    def test_py_typed_marker_is_present_and_packaged(self):
        self.assertTrue((ROOT / "envguard" / "py.typed").is_file())
        self.assertIn('envguard = ["py.typed"]', _pyproject())

    def test_console_script_entry_point(self):
        self.assertIn('envguard = "envguard.cli:main"', _pyproject())

    def test_public_api_is_exported(self):
        for name in (
            "EnvValidator",
            "Rule",
            "parse_env_file",
            "parse_env_content",
            "compare_env_files",
            "sync_env_files",
            "generate_example_template",
            "is_placeholder",
        ):
            with self.subTest(name=name):
                self.assertTrue(hasattr(envguard, name))
                self.assertIn(name, envguard.__all__)


if __name__ == "__main__":
    unittest.main()
