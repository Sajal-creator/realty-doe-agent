"""Thin LLM client wrapper – routes to the configured provider."""

from __future__ import annotations

import json
from typing import Any, Optional

import httpx
import structlog

from orchestration.config import settings

logger = structlog.get_logger(__name__)

_OPENAI_URL = "https://api.openai.com/v1/chat/completions"


class LLMClient:
    """Async wrapper around the OpenAI Chat Completions API (function-calling capable)."""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None):
        self._api_key = api_key or settings._raw.OPENAI_API_KEY
        self._base_url = base_url or _OPENAI_URL
        self._http: Optional[httpx.AsyncClient] = None

    async def _client(self) -> httpx.AsyncClient:
        if self._http is None or self._http.is_closed:
            self._http = httpx.AsyncClient(timeout=120.0)
        return self._http

    async def _post(self, payload: dict) -> dict:
        client = await self._client()
        resp = await client.post(
            self._base_url,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    async def chat(
        self,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_format: Optional[dict] = None,
    ) -> dict:
        payload: dict[str, Any] = {
            "model": model or settings.LLM_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if response_format:
            payload["response_format"] = response_format
        logger.debug("llm.chat", model=payload["model"], message_count=len(messages))
        return await self._post(payload)

    async def function_call(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        tool_choice: Optional[Any] = None,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> dict:
        payload: dict[str, Any] = {
            "model": model or settings.LLM_MODEL,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
        if tool_choice:
            payload["tool_choice"] = tool_choice
        logger.debug("llm.function_call", model=payload["model"], tools=len(tools or []))
        return await self._post(payload)

    async def close(self) -> None:
        if self._http and not self._http.is_closed:
            await self._http.aclose()
