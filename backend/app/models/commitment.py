import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CommitmentStatus(str, enum.Enum):
    TO_CHECK = "to_check"
    EXPIRED = "expired"
    DONE = "done"
    NOT_ACTUAL = "not_actual"
    IDEAS_BACKLOG = "ideas_backlog"


class Commitment(Base):
    __tablename__ = "commitments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    executor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    reviewer_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id"), nullable=True
    )
    deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[CommitmentStatus] = mapped_column(
        Enum(CommitmentStatus, native_enum=False, length=30),
        default=CommitmentStatus.TO_CHECK,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    author = relationship(
        "User", foreign_keys=[author_id], back_populates="authored_commitments"
    )
    executor = relationship(
        "User", foreign_keys=[executor_id], back_populates="executed_commitments"
    )
    reviewer = relationship(
        "User", foreign_keys=[reviewer_id], back_populates="reviewed_commitments"
    )
    project = relationship("Project", back_populates="commitments")
