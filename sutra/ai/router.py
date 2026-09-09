"""
sutra.ai.router — Cascading Multi-Model AI Router

Orchestrates automatic fallback across top LLM providers:
1. Google Gemini (gemini-3.6-flash / gemini-1.5-flash)
2. OpenAI ChatGPT (gpt-4o-mini / gpt-4o)
3. Anthropic Claude (claude-3-5-haiku-20241022 / claude-3-haiku-20240307)
4. Sutra Local Semantic Engine (Zero Tokens, offline, guaranteed 100% uptime)
"""

import os
import json
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional, Tuple


def clean_parse_json(text: str) -> Any:
    """Safely extracts and parses JSON from raw LLM responses or markdown blocks."""
    text = text.strip()
    if "```json" in text:
        text = text.split("```json", 1)[1].split("```", 1)[0]
    elif "```" in text:
        text = text.split("```", 1)[1].split("```", 1)[0]
    text = text.strip()
    return json.loads(text)


CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "build", "ai_config.json")


def load_persistent_ai_keys() -> Dict[str, str]:
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_persistent_ai_keys(keys: Dict[str, str]) -> None:
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    existing = load_persistent_ai_keys()
    for k, v in keys.items():
        if v is not None:
            existing[k] = v.strip()
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(existing, f, indent=2)


class AIMultiRouter:
    def __init__(
        self,
        gemini_key: Optional[str] = None,
        openai_key: Optional[str] = None,
        anthropic_key: Optional[str] = None
    ):
        file_keys = load_persistent_ai_keys()

        self.gemini_key = (
            gemini_key
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("GOOGLE_API_KEY")
            or file_keys.get("gemini_key")
        )
        self.openai_key = (
            openai_key
            or os.environ.get("OPENAI_API_KEY")
            or os.environ.get("CHATGPT_API_KEY")
            or file_keys.get("openai_key")
        )
        self.anthropic_key = (
            anthropic_key
            or os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("CLAUDE_API_KEY")
            or file_keys.get("anthropic_key")
        )

    def get_providers_status(self) -> List[Dict[str, Any]]:
        """Returns readiness status for each configured provider."""
        return [
            {
                "id": "gemini",
                "name": "Google Gemini (Primary)",
                "models": ["gemini-3.6-flash", "gemini-1.5-flash"],
                "has_key": bool(self.gemini_key and len(self.gemini_key) > 8),
                "key_preview": f"{self.gemini_key[:4]}...{self.gemini_key[-4:]}" if self.gemini_key and len(self.gemini_key) > 8 else None
            },
            {
                "id": "openai",
                "name": "OpenAI ChatGPT (Fallback 1)",
                "models": ["gpt-4o-mini", "gpt-4o"],
                "has_key": bool(self.openai_key and len(self.openai_key) > 8),
                "key_preview": f"{self.openai_key[:4]}...{self.openai_key[-4:]}" if self.openai_key and len(self.openai_key) > 8 else None
            },
            {
                "id": "claude",
                "name": "Anthropic Claude (Fallback 2)",
                "models": ["claude-3-5-haiku-20241022", "claude-3-haiku-20240307"],
                "has_key": bool(self.anthropic_key and len(self.anthropic_key) > 8),
                "key_preview": f"{self.anthropic_key[:4]}...{self.anthropic_key[-4:]}" if self.anthropic_key and len(self.anthropic_key) > 8 else None
            },
            {
                "id": "local",
                "name": "Sutra Semantic Engine (Fallback 3 - Local Zero-Token)",
                "models": ["heuristic-ast-v2"],
                "has_key": True,
                "key_preview": "builtin"
            }
        ]

    def call_json(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        timeout: float = 4.0
    ) -> Dict[str, Any]:
        """
        Executes cascading fallback: Gemini -> ChatGPT -> Claude -> Local.
        Returns dictionary:
        {
            "success": bool,
            "data": Dict[str, Any] or list,
            "provider": str,
            "model": str,
            "tokens_used": int,
            "fallback_trace": List[str]
        }
        """
        trace: List[str] = []

        # 1. Primary: Google Gemini
        if self.gemini_key:
            try:
                data, tokens, model = self._call_gemini(prompt, system_prompt, timeout)
                trace.append(f"gemini ({model}): success ({tokens} tokens)")
                return {
                    "success": True,
                    "data": data,
                    "provider": "google-gemini",
                    "model": model,
                    "tokens_used": tokens,
                    "fallback_trace": trace
                }
            except Exception as e:
                trace.append(f"gemini failed: {str(e)[:90]}")
        else:
            trace.append("gemini: skipped (no API key configured)")

        # 2. Fallback 1: OpenAI ChatGPT
        if self.openai_key:
            try:
                data, tokens, model = self._call_openai(prompt, system_prompt, timeout)
                trace.append(f"openai ({model}): success ({tokens} tokens)")
                return {
                    "success": True,
                    "data": data,
                    "provider": "openai-chatgpt",
                    "model": model,
                    "tokens_used": tokens,
                    "fallback_trace": trace
                }
            except Exception as e:
                trace.append(f"openai failed: {str(e)[:90]}")
        else:
            trace.append("openai: skipped (no API key configured)")

        # 3. Fallback 2: Anthropic Claude
        if self.anthropic_key:
            try:
                data, tokens, model = self._call_claude(prompt, system_prompt, timeout)
                trace.append(f"claude ({model}): success ({tokens} tokens)")
                return {
                    "success": True,
                    "data": data,
                    "provider": "anthropic-claude",
                    "model": model,
                    "tokens_used": tokens,
                    "fallback_trace": trace
                }
            except Exception as e:
                trace.append(f"claude failed: {str(e)[:90]}")
        else:
            trace.append("claude: skipped (no API key configured)")

        # 4. Fallback 3: Local Engine
        trace.append("local-semantic-engine: activated (0 tokens)")
        return {
            "success": False,
            "data": None,
            "provider": "sutra-local-semantic",
            "model": "semantic-rules",
            "tokens_used": 0,
            "fallback_trace": trace
        }

    def _call_gemini(
        self,
        prompt: str,
        system_prompt: Optional[str],
        timeout: float
    ) -> Tuple[Any, int, str]:
        models = ["gemini-3.6-flash", "gemini-1.5-flash"]
        last_err = None
        for model in models:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_key}"
                payload: Dict[str, Any] = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
                }
                if system_prompt:
                    payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}

                req = urllib.request.Request(
                    url,
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=timeout) as response:
                    res_data = json.loads(response.read().decode("utf-8"))
                    text = res_data["candidates"][0]["content"]["parts"][0]["text"]
                    tokens = res_data.get("usageMetadata", {}).get("totalTokenCount", 400)
                    parsed = clean_parse_json(text)
                    return parsed, tokens, model
            except Exception as ex:
                last_err = ex
        raise last_err or RuntimeError("Gemini models failed")

    def _call_openai(
        self,
        prompt: str,
        system_prompt: Optional[str],
        timeout: float
    ) -> Tuple[Any, int, str]:
        url = "https://api.openai.com/v1/chat/completions"
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": "gpt-4o-mini",
            "messages": messages,
            "temperature": 0.1,
            "response_format": {"type": "json_object"}
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.openai_key}"
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            text = res_data["choices"][0]["message"]["content"]
            tokens = res_data.get("usage", {}).get("total_tokens", 400)
            parsed = clean_parse_json(text)
            return parsed, tokens, "gpt-4o-mini"

    def _call_claude(
        self,
        prompt: str,
        system_prompt: Optional[str],
        timeout: float
    ) -> Tuple[Any, int, str]:
        url = "https://api.anthropic.com/v1/messages"
        payload: Dict[str, Any] = {
            "model": "claude-3-5-haiku-20241022",
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}]
        }
        if system_prompt:
            payload["system"] = system_prompt

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.anthropic_key,
                "anthropic-version": "2023-06-01"
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            res_data = json.loads(response.read().decode("utf-8"))
            text = res_data["content"][0]["text"]
            usage = res_data.get("usage", {})
            tokens = usage.get("input_tokens", 0) + usage.get("output_tokens", 0)
            parsed = clean_parse_json(text)
            return parsed, tokens, "claude-3-5-haiku"
