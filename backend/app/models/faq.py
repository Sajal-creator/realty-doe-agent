"""
FAQ entry model — stores question/answer pairs with vector embeddings
for semantic search via pgvector.
"""

import uuid

from sqlalchemy import DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDPrimaryKeyMixin


class FAQEntry(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """FAQ question/answer with a vector embedding for semantic search."""

    __tablename__ = "faq_entries"

    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    domain: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    embedding = mapped_column(nullable=True)  # pgvector VECTOR type — added via extension

    def __repr__(self) -> str:
        return f"<FAQEntry {self.id} domain={self.domain}>"
