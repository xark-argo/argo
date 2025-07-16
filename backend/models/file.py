from sqlalchemy import BIGINT, ForeignKey, Index, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from database import db

from .sqlalchemy_types import GUID


class File(db.Base):
    __tablename__ = "file"
    __table_args__ = (
        PrimaryKeyConstraint("file_id", name="file_pkey"),
        Index("idx_file_id", "file_id"),
    )

    file_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255), nullable=True)
    user_id: Mapped[str] = mapped_column(GUID, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    file_size: Mapped[int] = mapped_column(BIGINT, default=0, nullable=True)
