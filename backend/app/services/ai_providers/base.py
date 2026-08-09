"""AI Provider abstraction base class."""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, List, Dict, Any, Optional
from pydantic import BaseModel


class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]


class ChatMessage(BaseModel):
    role: str  # system, user, assistant, tool
    content: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


class ChatChunk(BaseModel):
    type: str  # content, tool_call, tool_result, done, error
    content: Optional[str] = None
    tool_call: Optional[Dict] = None
    tool_result: Optional[Dict] = None
    usage: Optional[Dict] = None
    error: Optional[str] = None


class AIProvider(ABC):
    @abstractmethod
    async def stream_chat(
        self,
        system_prompt: str,
        messages: List[ChatMessage],
        tools: List[ToolDefinition],
        tool_choice: str = "auto",
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> AsyncGenerator[ChatChunk, None]:
        """Stream chat response with tool calling."""
        pass

    @abstractmethod
    async def count_tokens(self, text: str) -> int:
        """Estimate token count for context management."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Provider-specific model identifier."""
        pass