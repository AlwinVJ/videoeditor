import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR))

from core.config import (
    get_secret,
    get_required_secret,
    get_groq_api_key,
    mask_secret,
)
from core.transcription import load_groq_api_key


class TestCentralizedConfig(unittest.TestCase):
    """Test suite for core/config.py environment variable and secrets management."""

    def setUp(self):
        # Save original environ for clean isolation
        self.original_groq = os.environ.get("GROQ_API_KEY")
        if "GROQ_API_KEY" in os.environ:
            del os.environ["GROQ_API_KEY"]
        if "groq_api_key" in os.environ:
            del os.environ["groq_api_key"]

    def tearDown(self):
        # Restore original environ
        if self.original_groq is not None:
            os.environ["GROQ_API_KEY"] = self.original_groq
        elif "GROQ_API_KEY" in os.environ:
            del os.environ["GROQ_API_KEY"]

    def test_1_env_variable_precedence(self):
        """Test that get_secret retrieves from environment variables first."""
        os.environ["GROQ_API_KEY"] = "gsk_env_test_val_1234"
        val = get_secret("GROQ_API_KEY")
        self.assertEqual(val, "gsk_env_test_val_1234")

    def test_2_lowercase_env_variable(self):
        """Test fallback to lowercase environment variable."""
        os.environ["groq_api_key"] = "gsk_lower_env_val_5678"
        val = get_secret("GROQ_API_KEY")
        self.assertEqual(val, "gsk_lower_env_val_5678")

    def test_3_streamlit_secrets_fallback_direct(self):
        """Test fallback to st.secrets top-level key when env var is absent."""
        mock_secrets = {"GROQ_API_KEY": "gsk_secrets_top_level_9999"}
        with patch("streamlit.secrets", mock_secrets):
            val = get_secret("GROQ_API_KEY")
            self.assertEqual(val, "gsk_secrets_top_level_9999")

    def test_4_streamlit_secrets_fallback_lowercase(self):
        """Test fallback to st.secrets lowercase key when env var is absent."""
        mock_secrets = {"groq_api_key": "gsk_secrets_lower_8888"}
        with patch("streamlit.secrets", mock_secrets):
            val = get_secret("GROQ_API_KEY")
            self.assertEqual(val, "gsk_secrets_lower_8888")

    def test_5_streamlit_secrets_fallback_nested(self):
        """Test fallback to st.secrets nested TOML section [groq] api_key = '...'."""
        mock_secrets = {"groq": {"api_key": "gsk_secrets_nested_7777"}}
        with patch("streamlit.secrets", mock_secrets):
            val = get_secret("GROQ_API_KEY")
            self.assertEqual(val, "gsk_secrets_nested_7777")

    def test_6_default_fallback_when_missing(self):
        """Test that get_secret returns default when key is nowhere to be found."""
        with patch("streamlit.secrets", {}):
            val = get_secret("NON_EXISTENT_KEY", default="fallback_val")
            self.assertEqual(val, "fallback_val")

    def test_7_get_required_secret_error_message(self):
        """Test that get_required_secret raises actionable ValueError mentioning both .env and Streamlit Secrets."""
        with patch("streamlit.secrets", {}):
            with self.assertRaises(ValueError) as ctx:
                get_required_secret("GROQ_API_KEY", friendly_name="Groq API key")
            err = str(ctx.exception)
            self.assertIn("Groq API key not found", err)
            self.assertIn(".env", err)
            self.assertIn("Streamlit Cloud Secrets", err)

    def test_8_load_groq_api_key_delegation(self):
        """Test that core.transcription.load_groq_api_key delegates to get_groq_api_key."""
        os.environ["GROQ_API_KEY"] = "gsk_transcription_delegated_key"
        val = load_groq_api_key()
        self.assertEqual(val, "gsk_transcription_delegated_key")

    def test_9_mask_secret(self):
        """Test that secret masking never leaks full payload."""
        self.assertEqual(mask_secret(None), "<not set>")
        self.assertEqual(mask_secret(""), "<not set>")
        self.assertEqual(mask_secret("short"), "********")
        masked = mask_secret("gsk_1234567890abcdef")
        self.assertTrue(masked.startswith("gsk_"))
        self.assertTrue(masked.endswith("cdef"))
        self.assertNotIn("1234567890ab", masked)

    def test_10_env_example_safety(self):
        """Verify .env.example exists and contains no genuine secrets."""
        example_path = ROOT_DIR / ".env.example"
        self.assertTrue(example_path.exists(), ".env.example must exist")
        content = example_path.read_text(encoding="utf-8")
        self.assertIn("GROQ_API_KEY", content)
        self.assertIn("your_groq_api_key_here", content)
        # Ensure no accidental API key was copied
        self.assertNotIn("gsk_", content)

    def test_11_gitignore_rules(self):
        """Verify .gitignore properly protects .env while permitting .env.example."""
        gitignore_path = ROOT_DIR / ".gitignore"
        content = gitignore_path.read_text(encoding="utf-8")
        self.assertIn(".env\n", content)
        self.assertIn(".env.*", content)
        self.assertIn("!.env.example", content)


if __name__ == "__main__":
    unittest.main()
