from datetime import datetime

from pydantic import BaseModel, Field

from app.models.commitment import CommitmentStatus


class AICommitmentDraft(BaseModel):
    """Structured output expected from the LLM."""

    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    project_name: str | None = None
    executor_name: str | None = None
    reviewer_name: str | None = None
    deadline: datetime | None = None
    status: CommitmentStatus = CommitmentStatus.TO_CHECK


class CommitmentFormPrefill(BaseModel):
    """Resolved IDs ready for the HTML form."""

    title: str = ""
    description: str = ""
    project_id: int | None = None
    executor_id: int | None = None
    reviewer_id: int | None = None
    deadline: str = ""
    status: str = CommitmentStatus.TO_CHECK.value
