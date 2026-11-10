import os
import unittest
from unittest.mock import patch

from backend.engine import llm_client
from backend.engine.llm_client import LLMClient, LLMResponse, _get_config


class FakeProvider:
    name = "fake"

    def __init__(self, text="A short line.", fail=False):
        self.text = text
        self.fail = fail
        self.calls = []

    def complete(self, system, user, *, max_tokens, temperature, timeout):
        self.calls.append({"system": system, "user": user})
        if self.fail:
            raise RuntimeError("provider down")
        return LLMResponse(self.text, prompt_tokens=12, completion_tokens=5)


def make_config(**overrides):
    config = {
        "enabled": True,
        "mode": "all",
        "provider": "fake",
        "api_key": "test-key",
        "base_url": "http://fake.local/v1",
        "model": "fake-model",
        "requires_key": True,
        "max_tokens": 64,
        "temperature": 0.2,
        "timeout": 1.0,
        "max_concurrency": 1,
        "max_calls_per_run": 10,
        "max_input_chars": 2000,
        "cache_size": 16,
    }
    config.update(overrides)
    return config


class LLMClientTests(unittest.TestCase):
    def test_disabled_or_missing_key_never_calls_provider(self):
        provider = FakeProvider()
        client = LLMClient(make_config(enabled=False), provider)
        self.assertFalse(client.available("reflection"))
        self.assertIsNone(client.complete("sys", "user", "reflection"))
        self.assertEqual(provider.calls, [])

        client = LLMClient(make_config(api_key=""), provider)
        self.assertFalse(client.available())
        self.assertIsNone(client.complete("sys", "user", "reflection"))
        self.assertEqual(provider.calls, [])

    def test_mode_gates_capabilities(self):
        provider = FakeProvider()
        client = LLMClient(make_config(mode="reflection"), provider)
        self.assertTrue(client.available("reflection"))
        self.assertFalse(client.available("conversation"))
        self.assertIsNone(client.complete("sys", "chat", "conversation"))
        self.assertEqual(provider.calls, [])
        self.assertEqual(client.complete("sys", "think", "reflection"), "A short line.")

    def test_cache_avoids_duplicate_calls(self):
        provider = FakeProvider()
        client = LLMClient(make_config(), provider)
        self.assertEqual(client.complete("sys", "same", "reflection"), "A short line.")
        self.assertEqual(client.complete("sys", "same", "reflection"), "A short line.")
        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(client.status()["cacheHits"], 1)
        self.assertEqual(client.status()["calls"], 1)

    def test_budget_stops_calls_and_is_visible(self):
        provider = FakeProvider()
        client = LLMClient(make_config(max_calls_per_run=1), provider)
        self.assertEqual(client.complete("sys", "one", "reflection"), "A short line.")
        self.assertIsNone(client.complete("sys", "two", "reflection"))
        self.assertEqual(len(provider.calls), 1)
        status = client.status()
        self.assertEqual(status["calls"], 1)
        self.assertEqual(status["budgetExhausted"], 1)

    def test_provider_failure_falls_back_to_none(self):
        provider = FakeProvider(fail=True)
        client = LLMClient(make_config(), provider)
        self.assertIsNone(client.complete("sys", "user", "reflection"))
        status = client.status()
        self.assertEqual(status["failures"], 1)
        self.assertEqual(status["calls"], 1)

    def test_long_context_is_truncated(self):
        provider = FakeProvider()
        client = LLMClient(make_config(max_input_chars=500), provider)
        self.assertEqual(
            client.complete("system", "x" * 1500, "reflection"),
            "A short line.",
        )
        self.assertIn("[truncated]", provider.calls[0]["user"])
        self.assertEqual(client.status()["truncated"], 1)

    def test_deepseek_preset_and_legacy_mode_derivation(self):
        env = {
            "LLM_PROVIDER": "deepseek",
            "LLM_ENABLED": "true",
            "LLM_API_KEY": "deepseek-test",
            "LLM_CONVERSATIONS": "true",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg = _get_config()
        self.assertEqual(cfg["provider"], "deepseek")
        self.assertEqual(cfg["base_url"], "https://api.deepseek.com/v1")
        self.assertEqual(cfg["model"], "deepseek-chat")
        self.assertTrue(cfg["enabled"])
        self.assertEqual(cfg["mode"], "all")
        self.assertTrue(cfg["requires_key"])

    def test_ollama_does_not_require_a_key(self):
        env = {
            "LLM_PROVIDER": "ollama",
            "LLM_ENABLED": "true",
            "LLM_API_KEY": "",
            "LLM_MODE": "reflection",
        }
        with patch.dict(os.environ, env, clear=False):
            cfg = _get_config()
            client = LLMClient(cfg, FakeProvider())
            self.assertTrue(client.available("reflection"))
        self.assertEqual(cfg["base_url"], "http://localhost:11434/v1")
        self.assertFalse(cfg["requires_key"])

    def test_global_status_never_contains_the_key(self):
        status = llm_client.llm_status()
        self.assertNotIn("api_key", status)
        self.assertIn("apiKeyConfigured", status)


if __name__ == "__main__":
    unittest.main()
