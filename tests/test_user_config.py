import os
import tempfile
import unittest
from unittest.mock import patch

from smv import user_config


class UserConfigTest(unittest.TestCase):
    def test_defaults_when_no_config_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp_dir}, clear=False):
                cfg = user_config.load_user_config()
                self.assertEqual(cfg["provider"], "ollama")
                self.assertTrue(cfg["model"])

    def test_plaintext_api_key_storage(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp_dir}, clear=False):
                cfg = user_config.load_user_config()
                cfg["provider"] = "openai"
                user_config.save_user_config(cfg)
                storage = user_config.set_api_key(
                    cfg,
                    "test-key-123",
                    storage="plaintext",
                    allow_plaintext_fallback=True,
                )
                self.assertEqual(storage, "plaintext")
                loaded = user_config.load_user_config()
                self.assertEqual(loaded["api_key"], "test-key-123")
                self.assertEqual(loaded["api_key_storage"], "plaintext")

    def test_effective_config_resolves_values(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": tmp_dir}, clear=False):
                cfg = user_config.load_user_config()
                cfg["provider"] = "openai"
                cfg["model"] = "gpt-4.1-mini"
                cfg["base_url"] = "https://api.openai.com/v1"
                cfg["api_key_storage"] = "plaintext"
                cfg["api_key"] = "abc123"
                user_config.save_user_config(cfg)

                effective = user_config.get_effective_ai_config()
                self.assertEqual(effective["provider"], "openai")
                self.assertEqual(effective["model"], "gpt-4.1-mini")
                self.assertEqual(effective["api_key"], "abc123")


if __name__ == "__main__":
    unittest.main()
