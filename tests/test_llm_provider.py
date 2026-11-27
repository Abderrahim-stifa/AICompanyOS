"""Tests for the optional LLM provider boundary (no live API key required)."""
import json
import unittest
from unittest.mock import Mock, patch

from core.llm_provider import (
    OfflineProvider, OpenAIProvider, ProviderConfig, ProviderError,
    create_supervised_plan, get_provider, validate_output,
)


VALID = {
    "summary": "خطة أولية",
    "deliverables": ["تحليل المتطلبات"],
    "assumptions": ["توفر الميزانية"],
    "risks": ["تغير النطاق"],
    "questions": ["ما الموعد؟"],
    "provenance": {"source": "model_draft"},
}


class LLMProviderTests(unittest.TestCase):
    def test_offline_is_default_and_does_not_need_credentials(self):
        with patch.dict("os.environ", {}, clear=True):
            provider = get_provider()
        self.assertIsInstance(provider, OfflineProvider)
        result = create_supervised_plan("أريد تطوير منصة لإدارة العملاء", provider)
        self.assertEqual(result["provider"], "offline")
        self.assertFalse(result["approved"])
        self.assertFalse(result["execution_performed"])
        self.assertTrue(result["requires_human_approval"])

    def test_environment_configuration_uses_secret_env_var(self):
        env = {
            "AICOS_LLM_PROVIDER": "openai",
            "AICOS_LLM_API_KEY": "test-secret",
            "AICOS_LLM_MODEL": "test-model",
            "AICOS_LLM_TIMEOUT": "999",
        }
        with patch.dict("os.environ", env, clear=True):
            config = ProviderConfig.from_env()
        self.assertEqual(config.model, "test-model")
        self.assertEqual(config.timeout, 60.0)
        self.assertEqual(config.api_key, "test-secret")

    def test_missing_key_fails_without_exposing_secret(self):
        with patch.dict("os.environ", {"AICOS_LLM_PROVIDER": "openai"}, clear=True):
            with self.assertRaisesRegex(ProviderError, "مفتاح API"):
                ProviderConfig.from_env()

    def test_unknown_provider_rejected(self):
        with patch.dict("os.environ", {"AICOS_LLM_PROVIDER": "unknown"}, clear=True):
            with self.assertRaises(ProviderError):
                ProviderConfig.from_env()

    def test_openai_adapter_parses_mocked_response(self):
        body = {"choices": [{"message": {"content": json.dumps(VALID, ensure_ascii=False)}}]}
        response = Mock()
        response.read.return_value = json.dumps(body).encode("utf-8")
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        with patch("core.llm_provider.urllib.request.urlopen", return_value=response) as call:
            provider = OpenAIProvider("secret", "mock-model", 5)
            result = create_supervised_plan("أريد دراسة جدوى لمشروع", provider)
        self.assertEqual(result["summary"], VALID["summary"])
        self.assertEqual(result["model"], "mock-model")
        self.assertTrue(result["requires_human_approval"])
        request = call.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.openai.com/v1/chat/completions")
        self.assertIn("Bearer secret", request.get_header("Authorization"))

    def test_invalid_structured_output_rejected(self):
        with self.assertRaises(ProviderError):
            validate_output({"summary": "ناقص"})

    def test_non_string_list_items_rejected(self):
        invalid = dict(VALID, risks=[{"execute": "danger"}])
        with self.assertRaises(ProviderError):
            validate_output(invalid)

    def test_brief_length_is_bounded(self):
        with self.assertRaises(ValueError):
            create_supervised_plan("قصير")
        with self.assertRaises(ValueError):
            create_supervised_plan("x" * 4001)

    def test_provider_error_is_sanitized(self):
        with patch("core.llm_provider.urllib.request.urlopen", side_effect=TimeoutError()):
            with self.assertRaisesRegex(ProviderError, "تعذر الاتصال"):
                OpenAIProvider("do-not-leak").generate("طلب اختبار")


if __name__ == "__main__":
    unittest.main()
