"""AI Orchestrator - placeholder for Phase 1 implementation."""

from typing import AsyncGenerator, Optional
from uuid import UUID

from app.services.ai_providers.base import AIProvider, ChatChunk, ToolDefinition
from app.services.prompt_defense import PromptDefense


class ToolRegistry:
    def get_definitions(self, categories: list[str]) -> list[ToolDefinition]:
        # Phase 1: Implement tool registry with READ and DRAFT tools
        return []


class ContextBuilder:
    async def build(self, user_id: UUID) -> str:
        # Phase 1: Implement context building
        return ""


class AIOrchestrator:
    def __init__(
        self,
        provider: AIProvider,
        tool_registry: ToolRegistry,
        context_builder: ContextBuilder,
        prompt_defense: PromptDefense,
    ):
        self.provider = provider
        self.tool_registry = tool_registry
        self.context_builder = context_builder
        self.prompt_defense = prompt_defense

    async def chat(
        self,
        user_id: UUID,
        message: str,
        conversation_id: Optional[UUID] = None,
    ) -> AsyncGenerator[ChatChunk, None]:
        # Phase 1: Implement AI chat orchestration
        yield ChatChunk(type="content", content="AI chat not yet implemented - Phase 1")
        yield ChatChunk(type="done", usage={"prompt_tokens": 0, "completion_tokens": 0})