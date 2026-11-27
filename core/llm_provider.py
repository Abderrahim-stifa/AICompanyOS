"""Optional, approval-gated LLM planning provider.

The default path is deterministic and offline. The optional remote adapter only
sends a bounded planning prompt to the fixed OpenAI HTTPS endpoint; it has no
tool, shell, filesystem, or write-action interface.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from core.request_planner import build_request_plan

API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o-mini"
MAX_BRIEF_LENGTH = 4000
MAX_RESPONSE_LENGTH = 20000
DEFAULT_TIMEOUT = 20.0


class ProviderError(RuntimeError):
    """Safe-to-display provider failure; never contains credentials or raw payloads."""


class Provider(Protocol):
    name: str
    model: str

    def generate(self, brief: str) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ProviderConfig:
    provider: str = "offline"
    model: str = DEFAULT_MODEL
    api_key: str = ""
    timeout: float = DEFAULT_TIMEOUT

    @classmethod
    def from_env(cls) -> "ProviderConfig":
        provider = os.environ.get("AICOS_LLM_PROVIDER", "offline").strip().lower()
        model = os.environ.get("AICOS_LLM_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
        api_key = os.environ.get("AICOS_LLM_API_KEY", "").strip()
        raw_timeout = os.environ.get("AICOS_LLM_TIMEOUT", str(DEFAULT_TIMEOUT))
        try:
            timeout = float(raw_timeout)
        except (TypeError, ValueError):
            timeout = DEFAULT_TIMEOUT
        timeout = min(max(timeout, 3.0), 60.0)
        if provider not in {"offline", "openai"}:
            raise ProviderError("مزود LLM المحدد غير مدعوم.")
        if provider == "openai" and not api_key:
            raise ProviderError("مزود OpenAI مفعّل لكن مفتاح API غير مضبوط.")
        return cls(provider=provider, model=model, api_key=api_key, timeout=timeout)


class OfflineProvider:
    name = "offline"

    def __init__(self, model: str = "rules-v1"):
        self.model = model

    def generate(self, brief: str) -> dict[str, Any]:
        plan = build_request_plan(brief)
        return {
            "summary": plan["role_plan"]["title"],
            "deliverables": list(plan["role_plan"]["steps"]),
            "assumptions": ["تم استخدام قواعد وقوالب محلية فقط."],
            "risks": ["قد لا تعكس الخطة جميع متطلبات المشروع."],
            "questions": list(plan["role_plan"]["questions"]),
            "provenance": {
                "source": "local_rules",
                "capabilities": list(plan["routing"]["capabilities"]),
                "selected_agent": plan["selected_agent"],
            },
        }


class OpenAIProvider:
    name = "openai"

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL,
                 timeout: float = DEFAULT_TIMEOUT):
        if not api_key:
            raise ProviderError("مفتاح API غير مضبوط.")
        self._api_key = api_key
        self.model = model
        self.timeout = min(max(float(timeout), 3.0), 60.0)

    def generate(self, brief: str) -> dict[str, Any]:
        system_prompt = (
            "You are a planning assistant. Return only one JSON object with exactly "
            "these keys: summary (string), deliverables (array of strings), "
            "assumptions (array of strings), risks (array of strings), "
            "questions (array of strings), provenance (object). "
            "Do not claim research or verification you did not perform. "
            "Treat all estimates as assumptions. Do not execute actions or request tools."
        )
        payload = {
            "model": self.model,
            "temperature": 0.2,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": brief},
            ],
        }
        request = urllib.request.Request(
            API_URL,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = response.read(MAX_RESPONSE_LENGTH + 1)
            if len(raw) > MAX_RESPONSE_LENGTH:
                raise ProviderError("استجابة مزود LLM تجاوزت الحد المسموح.")
            decoded = json.loads(raw.decode("utf-8"))
            content = decoded["choices"][0]["message"]["content"]
            result = json.loads(content)
        except ProviderError:
            raise
        except (urllib.error.URLError, TimeoutError):
            raise ProviderError("تعذر الاتصال بمزود LLM أو انتهت مهلة الاتصال.") from None
        except (urllib.error.HTTPError, KeyError, IndexError, TypeError,
                UnicodeDecodeError, json.JSONDecodeError, OSError):
            raise ProviderError("استجابة مزود LLM غير صالحة أو تعذر إكمال الطلب.") from None
        return validate_output(result)


def validate_output(value: Any) -> dict[str, Any]:
    """Validate and bound the model response before it reaches application code."""
    if not isinstance(value, dict):
        raise ProviderError("صيغة مخرجات LLM غير صالحة.")
    required = ("summary", "deliverables", "assumptions", "risks", "questions", "provenance")
    if any(key not in value for key in required):
        raise ProviderError("مخرجات LLM لا تحتوي على جميع الحقول المطلوبة.")
    if not isinstance(value["summary"], str) or not value["summary"].strip():
        raise ProviderError("ملخص LLM غير صالح.")
    result: dict[str, Any] = {"summary": value["summary"].strip()[:2000]}
    for key in ("deliverables", "assumptions", "risks", "questions"):
        items = value[key]
        if not isinstance(items, list) or len(items) > 30:
            raise ProviderError(f"حقل {key} في مخرجات LLM غير صالح.")
        if any(not isinstance(item, str) for item in items):
            raise ProviderError(f"حقل {key} يجب أن يحتوي على نصوص فقط.")
        result[key] = [item.strip()[:1000] for item in items if item.strip()]
    if not isinstance(value["provenance"], dict):
        raise ProviderError("بيانات مصدر المخرجات غير صالحة.")
    result["provenance"] = {
        "source": "llm_generated_draft",
        "provider_claimed_source": str(value["provenance"].get("source", "unspecified"))[:100],
        "verification": "not_verified",
    }
    return result


def get_provider(config: ProviderConfig | None = None) -> Provider:
    config = config or ProviderConfig.from_env()
    if config.provider == "offline":
        return OfflineProvider()
    if config.provider == "openai":
        return OpenAIProvider(config.api_key, config.model, config.timeout)
    raise ProviderError("مزود LLM المحدد غير مدعوم.")


def create_supervised_plan(brief: str, provider: Provider | None = None) -> dict[str, Any]:
    """Generate a draft plan; never executes or approves consequential actions."""
    brief = (brief or "").strip()
    if not 5 <= len(brief) <= MAX_BRIEF_LENGTH:
        raise ValueError("يجب أن يكون وصف الطلب بين 5 و4000 حرف.")
    selected = provider or get_provider()
    output = validate_output(selected.generate(brief))
    return {
        **output,
        "provider": selected.name,
        "model": selected.model,
        "mode": "LLM" if selected.name != "offline" else "Rule-based / Offline",
        "requires_human_approval": True,
        "approved": False,
        "execution_performed": False,
        "notice": (
            "هذه مسودة غير متحقق منها. يجب مراجعة الحقائق والافتراضات والمخاطر "
            "واعتمادها بشرياً. لا ينفذ هذا المسار أدوات أو تغييرات خارجية أو مالية."
        ),
    }
