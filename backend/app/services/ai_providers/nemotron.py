"""Nemotron AI Provider - HTTP API implementation."""

import httpx
from typing import AsyncGenerator, List, Optional

from app.services.ai_providers.base import AIProvider, ChatMessage, ChatChunk, ToolDefinition
from app.config import get_settings

settings = get_settings()


class NemotronProvider(AIProvider):
    """Nemotron provider via HTTP API (e.g., NVIDIA NIM, local TGI)."""

    def __init__(self):
        self._api_url = settings.NEMOTRON_API_URL
        self._api_key = settings.NEMOTRON_API_KEY
        self._model = settings.NEMOTRON_MODEL
        self._client: Optional[httpx.AsyncClient] = None

    @property
    def model_name(self) -> str:
        return self._model

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            headers = {"Content-Type": "application/json"}
            if self._api_key:
                headers["Authorization"] = f"Bearer {self._api_key}"
            self._client = httpx.AsyncClient(
                base_url=self._api_url,
                headers=headers,
                timeout=60.0,
            )
        return self._client

    async def count_tokens(self, text: str) -> int:
        # Rough approximation
        return len(text) // 4

    async def stream_chat(
        self,
        system_prompt: str,
        messages: List[ChatMessage],
        tools: List[ToolDefinition],
        tool_choice: str = "auto",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[ChatChunk, None]:
        if not self._api_url:
            yield ChatChunk(
                type="error",
                error="Nemotron API URL not configured. Set NEMOTRON_API_URL environment variable."
            )
            return

        client = await self._get_client()

        # Convert to OpenAI-compatible format
        api_messages = [{"role": "system", "content": system_prompt}]
        for msg in messages:
            if msg.role == "tool":
                api_messages.append({
                    "role": "tool",
                    "content": msg.content,
                    "tool_call_id": msg.tool_call_id,
                })
            else:
                api_messages.append({
                    "role": msg.role,
                    "content": msg.content,
                })

        api_tools = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in tools
        ]

        payload = {
            "model": self._model,
            "messages": api_messages,
            "tools": api_tools if tools else None,
            "tool_choice": tool_choice,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

        try:
            async with client.stream("POST", "/chat/completions", json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        yield ChatChunk(type="done")
                        return
                    import json
                    try:
                        chunk = json.loads(data)
                        delta = chunk.get("choices", [{}])[0].get("delta", {})
                        if "content" in delta and delta["content"]:
                            yield ChatChunk(type="content", content=delta["content"])
                        if "tool_calls" in delta:
                            for tc in delta["tool_calls"]:
                                yield ChatChunk(type="tool_call", tool_call=tc)
                    except json.JSONDecodeError:
                        continue
        except httpx.HTTPStatusError as e:
            yield ChatChunk(type="error", error=f"API error: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            yield ChatChunk(type="error", error=f"Nemotron provider error: {str(e)}")

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None