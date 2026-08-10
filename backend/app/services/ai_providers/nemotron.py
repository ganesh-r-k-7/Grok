"""Nemotron AI Provider - OpenAI SDK implementation for NVIDIA NIM/TGI."""

from typing import AsyncGenerator, List, Optional

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletionChunk

from app.services.ai_providers.base import AIProvider, ChatMessage, ChatChunk, ToolDefinition
from app.config import get_settings

settings = get_settings()


class NemotronProvider(AIProvider):
    """Nemotron provider via OpenAI SDK (NVIDIA NIM, local TGI)."""

    def __init__(self):
        self._api_url = settings.NEMOTRON_API_URL
        self._api_key = settings.NEMOTRON_API_KEY
        self._model = settings.NEMOTRON_MODEL
        self._client: Optional[AsyncOpenAI] = None

    @property
    def model_name(self) -> str:
        return self._model

    def _get_client(self) -> AsyncOpenAI:
        if self._client is None:
            self._client = AsyncOpenAI(
                base_url=self._api_url,
                api_key=self._api_key or "dummy-key",
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

        client = self._get_client()

        # Convert to OpenAI format
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

        try:
            stream = await client.chat.completions.create(
                model=self._model,
                messages=api_messages,
                tools=api_tools if tools else None,
                tool_choice=tool_choice if tools else None,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )

            last_chunk = None
            async for chunk in stream:
                last_chunk = chunk
                delta = chunk.choices[0].delta if chunk.choices else None
                if delta:
                    if delta.content:
                        yield ChatChunk(type="content", content=delta.content)
                    if delta.tool_calls:
                        for tc in delta.tool_calls:
                            # Convert OpenAI tool call to dict
                            tool_call_dict = {
                                "id": tc.id,
                                "type": "function",
                                "function": {
                                    "name": tc.function.name,
                                    "arguments": tc.function.arguments,
                                },
                            }
                            yield ChatChunk(type="tool_call", tool_call=tool_call_dict)

            # Send done chunk with usage if available
            usage = last_chunk.usage if last_chunk and last_chunk.usage else None
            yield ChatChunk(type="done", usage={
                "prompt_tokens": usage.prompt_tokens if usage else 0,
                "completion_tokens": usage.completion_tokens if usage else 0,
                "total_tokens": usage.total_tokens if usage else 0,
            })

        except Exception as e:
            yield ChatChunk(type="error", error=f"Nemotron provider error: {str(e)}")

    async def close(self):
        if self._client:
            await self._client.close()
            self._client = None