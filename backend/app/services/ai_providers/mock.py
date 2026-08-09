"""Mock AI Provider for testing."""

from typing import AsyncGenerator, List, Dict

from app.services.ai_providers.base import AIProvider, ChatMessage, ChatChunk, ToolDefinition


class MockProvider(AIProvider):
    """Deterministic mock provider for testing."""

    def __init__(self, responses: List[Dict] = None):
        self._responses = responses or []
        self._call_count = 0

    @property
    def model_name(self) -> str:
        return "mock-model"

    async def count_tokens(self, text: str) -> int:
        return len(text) // 4  # Rough approximation

    async def stream_chat(
        self,
        system_prompt: str,
        messages: List[ChatMessage],
        tools: List[ToolDefinition],
        tool_choice: str = "auto",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[ChatChunk, None]:
        self._call_count += 1

        # Return predefined responses or a default
        if self._responses and self._call_count <= len(self._responses):
            response = self._responses[self._call_count - 1]
        else:
            response = {
                "type": "content",
                "content": "This is a mock response from the AI provider.",
            }

        if response["type"] == "content":
            yield ChatChunk(type="content", content=response.get("content", ""))
            yield ChatChunk(type="done", usage={"prompt_tokens": 10, "completion_tokens": 20})
        elif response["type"] == "tool_call":
            yield ChatChunk(type="tool_call", tool_call=response.get("tool_call"))
            yield ChatChunk(type="done", usage={"prompt_tokens": 10, "completion_tokens": 5})
        elif response["type"] == "error":
            yield ChatChunk(type="error", error=response.get("error", "Mock error"))
        else:
            yield ChatChunk(type="content", content="Mock response")
            yield ChatChunk(type="done", usage={"prompt_tokens": 10, "completion_tokens": 20})