from datetime import datetime
from uuid import uuid4
from typing import List
from sqlalchemy import String, TIMESTAMP, ARRAY
from sqlalchemy.dialects.postgresql import UUID, BYTEA
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class OAuthToken(Base, TimestampMixin):
    __tablename__ = "oauth_tokens"

    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    user_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    access_token_enc: Mapped[bytes] = mapped_column(BYTEA, nullable=False)
    refresh_token_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        nullable=False,
    )
    scopes: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False, default=list)

    # Unique constraint on user_id + provider
    __table_args__ = ({"schema": None},)