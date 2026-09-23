import unittest
from envguard.exceptions import ParseError
from envguard.parser import parse_env_content


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


if __name__ == "__main__":
    unittest.main()
