"""Gmail service - placeholder for Phase 1 implementation."""

from uuid import UUID


class GmailService:
    def __init__(self, user_id: UUID, db, encryption):
        self.user_id = user_id
        self.db = db
        self.encryption = encryption

    async def list_messages(self, query: str = "", max_results: int = 50) -> dict:
        # Phase 1: Implement Gmail list
        return {"messages": [], "next_page_token": None}

    async def get_message(self, message_id: str) -> dict:
        # Phase 1: Implement Gmail get
        return {}

    async def get_thread(self, thread_id: str) -> dict:
        # Phase 1: Implement Gmail thread
        return {}

    async def sync_incremental(self, sync_token: str) -> dict:
        # Phase 1: Implement incremental sync
        return {"synced": 0, "new_sync_token": sync_token}