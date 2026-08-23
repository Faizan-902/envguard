import unittest
from envguard.parser import parse_env_content
from envguard.validator import EnvValidator, Rule, is_placeholder


class TestEnvValidator(unittest.TestCase):
    def test_is_placeholder(self):
        self.assertTrue(is_placeholder("<YOUR_API_KEY>"))
        self.assertTrue(is_placeholder("your_secret_here"))
        self.assertTrue(is_placeholder("CHANGEME"))
        self.assertTrue(is_placeholder("TODO"))
        self.assertTrue(is_placeholder("xxxx"))
        self.assertFalse(is_placeholder("production_db_pass_9921"))
        self.assertFalse(is_placeholder("https://api.example.com"))

    def test_integer_and_port_validation(self):
        validator = EnvValidator([
            Rule("PORT", type="port"),
            Rule("MAX_WORKERS", type="integer", min_value=1, max_value=16),
        ])
        
        valid_env = parse_env_content("PORT=8080\nMAX_WORKERS=4")
        res = validator.validate(valid_env)
        self.assertTrue(res.is_valid)

        invalid_env = parse_env_content("PORT=999999\nMAX_WORKERS=32")
        res = validator.validate(invalid_env)
        self.assertFalse(res.is_valid)
        self.assertEqual(len(res.issues), 2)

    def test_boolean_and_email_validation(self):
        validator = EnvValidator([
            Rule("DEBUG", type="boolean"),
            Rule("ADMIN_EMAIL", type="email"),
        ])
        
        valid_env = parse_env_content("DEBUG=true\nADMIN_EMAIL=dev@example.com")
        res = validator.validate(valid_env)
        self.assertTrue(res.is_valid)

        invalid_env = parse_env_content("DEBUG=maybe\nADMIN_EMAIL=not-an-email")
        res = validator.validate(invalid_env)
        self.assertFalse(res.is_valid)
        self.assertEqual(len(res.issues), 2)

    def test_url_and_enum_validation(self):
        validator = EnvValidator([
            Rule("DATABASE_URL", type="url"),
            Rule("ENVIRONMENT", type="enum", choices=["development", "staging", "production"]),
        ])
        
        valid_env = parse_env_content("DATABASE_URL=postgres://user:pass@localhost:5432/db\nENVIRONMENT=production")
        res = validator.validate(valid_env)
        self.assertTrue(res.is_valid)

        invalid_env = parse_env_content("DATABASE_URL=invalid_url\nENVIRONMENT=local")
        res = validator.validate(invalid_env)
        self.assertFalse(res.is_valid)

    def test_missing_required_variable(self):
        validator = EnvValidator([
            Rule("JWT_SECRET", required=True),
        ])
        env = parse_env_content("PORT=3000")
        res = validator.validate(env)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.issues[0].issue_type, "missing")


if __name__ == "__main__":
    unittest.main()
