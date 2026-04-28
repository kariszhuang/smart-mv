import unittest

from smv import providers


class ProvidersTest(unittest.TestCase):
    def test_provider_order_starts_with_ollama(self):
        ordered_ids = [provider.id for provider in providers.ordered_providers()]
        self.assertGreaterEqual(len(ordered_ids), 1)
        self.assertEqual(ordered_ids[0], "ollama")

    def test_list_models_includes_suggestions(self):
        models = providers.list_models("openai")
        self.assertIn("gpt-4.1-mini", models)

    def test_get_provider_rejects_unknown(self):
        with self.assertRaises(ValueError):
            providers.get_provider("unknown-provider")


if __name__ == "__main__":
    unittest.main()
