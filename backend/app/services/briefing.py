"""Briefing service - placeholder for Phase 1 implementation."""

from uuid import UUID


class BriefingService:
    async def generate(self, user_id: UUID) -> dict:
        # Phase 1: Implement briefing generation
        return {"markdown": "Briefing not yet implemented - Phase 1"}

    async def get_today(self, user_id: UUID) -> dict:
        # Phase 1: Implement cached briefing retrieval
        return {"markdown": "Briefing not yet implemented - Phase 1"}