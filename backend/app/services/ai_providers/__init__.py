from app.services.ai_providers.base import AIProvider, ToolDefinition, ChatMessage, ChatChunk
from app.services.ai_providers.mock import MockProvider
from app.services.ai_providers.nemotron import NemotronProvider

__all__ = ["AIProvider", "ToolDefinition", "ChatMessage", "ChatChunk", "MockProvider", "NemotronProvider"]


def get_provider(provider_name: str = "mock") -> AIProvider:
    """Factory function to get AI provider instance."""
    providers = {
        "mock": MockProvider,
        "nemotron": NemotronProvider,
    }
    provider_class = providers.get(provider_name)
    if not provider_class:
        raise ValueError(f"Unknown provider: {provider_name}")
    return provider_class()