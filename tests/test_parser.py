import tempfile
import unittest
from pathlib import Path

from envguard.exceptions import ParseError
from envguard.parser import parse_env_content, parse_env_file


class TestEnvParser(unittest.TestCase):
    def test_basic_key_value(self):
        content = "PORT=8080\nHOST=localhost\nDEBUG=true"
        env = parse_env_content(content)
        self.assertEqual(env.get("PORT"), "8080")
        self.assertEqual(env.get("HOST"), "localhost")
        self.assertEqual(env.get("DEBUG"), "true")

    def test_quoted_values(self):
        content = 'GREETING="Hello, World!"\nSECRET=\'super$ecret#123\''
        env = parse_env_content(content)
        self.assertEqual(env.get("GREETING"), "Hello, World!")
        self.assertEqual(env.get("SECRET"), "super$ecret#123")

    def test_comments_and_blank_lines(self):
        content = """
        # Server settings
        PORT=3000 # Default app port
        
        # Database
        DB_NAME=mydb
        """
        env = parse_env_content(content)
        self.assertEqual(env.get("PORT"), "3000")
        self.assertEqual(env.entries["PORT"].comment, "Default app port")
        self.assertEqual(env.get("DB_NAME"), "mydb")

    def test_export_prefix(self):
        content = "export API_URL=https://api.example.com\nNODE_ENV=production"
        env = parse_env_content(content)
        self.assertTrue(env.entries["API_URL"].is_exported)
        self.assertFalse(env.entries["NODE_ENV"].is_exported)
        self.assertEqual(env.get("API_URL"), "https://api.example.com")

    def test_multiline_string(self):
        content = 'PRIVATE_KEY="line1\nline2\nline3"\nAPP=demo'
        env = parse_env_content(content)
        self.assertEqual(env.get("PRIVATE_KEY"), "line1\nline2\nline3")
        self.assertEqual(env.get("APP"), "demo")

    def test_unclosed_quote_raises_parse_error(self):
        content = 'BROKEN_KEY="unclosed string value\nOTHER=1'
        with self.assertRaises(ParseError):
            parse_env_content(content)

    def test_invalid_key_identifier(self):
        content = "123INVALID=foo"
        with self.assertRaises(ParseError):
            parse_env_content(content)

    def test_bom_prefix(self):
        content = "\ufeffPORT=8080\nHOST=localhost"
        env = parse_env_content(content)
        self.assertEqual(env.get("PORT"), "8080")
        self.assertEqual(env.get("HOST"), "localhost")

    def test_escaped_quotes_in_double_quoted(self):
        content = 'MSG="say \\"hi\\" now"'
        env = parse_env_content(content)
        self.assertEqual(env.get("MSG"), 'say "hi" now')

    def test_equals_in_unquoted_value(self):
        content = "PLAN=A=B=C"
        env = parse_env_content(content)
        self.assertEqual(env.get("PLAN"), "A=B=C")

    def test_windows_path_in_double_quotes_is_preserved(self):
        env = parse_env_content(r'PATH="C:\Users\dev\bin"')
        self.assertEqual(env.get("PATH"), r"C:\Users\dev\bin")

    def test_windows_path_with_escape_letters_is_preserved(self):
        env = parse_env_content(r'PATH="C:\new\table\bin"')
        self.assertEqual(env.get("PATH"), r"C:\new\table\bin")

    def test_non_ascii_double_quoted_value_is_preserved(self):
        env = parse_env_content('CITY="München"')
        self.assertEqual(env.get("CITY"), "München")

    def test_named_escape_sequences_are_preserved_in_paths(self):
        env = parse_env_content(r'MSG="line1\nline2\tdone"')
        self.assertEqual(env.get("MSG"), r"line1\nline2\tdone")

    def test_unknown_escape_is_preserved_literally(self):
        env = parse_env_content(r'PATTERN="\d{3}"')
        self.assertEqual(env.get("PATTERN"), r"\d{3}")

    def test_hash_without_whitespace_is_part_of_value(self):
        env = parse_env_content("PASSWORD=abc#123")
        self.assertEqual(env.get("PASSWORD"), "abc#123")
        self.assertIsNone(env.entries["PASSWORD"].comment)

    def test_hash_after_whitespace_starts_a_comment(self):
        env = parse_env_content("PORT=3000 # Default app port")
        self.assertEqual(env.get("PORT"), "3000")
        self.assertEqual(env.entries["PORT"].comment, "Default app port")

    def test_comment_only_value_is_empty(self):
        env = parse_env_content("TOKEN= # fill me in")
        self.assertEqual(env.get("TOKEN"), "")
        self.assertEqual(env.entries["TOKEN"].comment, "fill me in")

    def test_multiline_escaped_quote_does_not_close_early(self):
        content = 'PRIVATE_KEY="line1\nline2\\"tail"\nNEXT=1'
        env = parse_env_content(content)
        self.assertEqual(env.get("PRIVATE_KEY"), 'line1\nline2"tail')
        self.assertEqual(env.get("NEXT"), "1")

    def test_single_quoted_value_is_literal_even_with_trailing_backslash(self):
        env = parse_env_content("SOURCE='C:\\'")
        self.assertEqual(env.get("SOURCE"), "C:\\")

    def test_double_quoted_path_ending_with_escaped_backslash(self):
        env = parse_env_content(r'PATH="C:\dev\\"')
        self.assertEqual(env.get("PATH"), "C:\\dev\\")

    def test_double_quoted_path_ending_with_single_backslash_is_rejected(self):
        # "C:\dev\" is ambiguous: the final \" is an escaped quote, so the value
        # never closes. Users must double the separator or use single quotes.
        with self.assertRaises(ParseError):
            parse_env_content(r'PATH="C:\dev\"')

    def test_non_utf8_file_raises_parse_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / ".env"
            path.write_bytes(b"NAME=caf\xe9\n")

            with self.assertRaises(ParseError) as cm:
                parse_env_file(path)
            self.assertIn("not valid UTF-8", str(cm.exception))

    def test_content_after_closing_quote_is_rejected(self):
        # An unterminated double-quoted value must not swallow the next key.
        with self.assertRaises(ParseError):
            parse_env_content('ROOT="C:\\projects\\"\nNAME="app"\n')



if __name__ == "__main__":
    unittest.main()
