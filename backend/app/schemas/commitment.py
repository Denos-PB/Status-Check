from datetime import UTC, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.commitment import CommitmentStatus


class ProjectResponse(BaseModel):
    id: int
    name: str
    description: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CommitmentCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = None
    executor_id: int | None = None
    reviewer_id: int | None = None
    project_id: int | None = None
    deadline: datetime | None = None
    status: CommitmentStatus = CommitmentStatus.TO_CHECK

    @field_validator("deadline")
    @classmethod
    def deadline_not_in_past(cls, v: datetime | None) -> datetime | None:
        if v is None:
            return v
        now = datetime.now(UTC)
        deadline = v if v.tzinfo else v.replace(tzinfo=UTC)
        if deadline < now:
            raise ValueError("Deadline cannot be in the past")
        return deadline

    @model_validator(mode="after")
    def backlog_without_deadline(self) -> "CommitmentCreate":
        if (
            self.status == CommitmentStatus.IDEAS_BACKLOG
            and self.deadline is not None
        ):
            raise ValueError("Ideas backlog items should not have a deadline")
        return self


class CommitmentUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=500)
    description: str | None = None
    executor_id: int | None = None
    reviewer_id: int | None = None
    project_id: int | None = None
    deadline: datetime | None = None
    status: CommitmentStatus | None = None


class CommitmentStatusUpdate(BaseModel):
    status: CommitmentStatus


class UserBrief(BaseModel):
    id: int
    full_name: str
    email: str

    model_config = {"from_attributes": True}


class ProjectBrief(BaseModel):
    id: int
    name: str

    model_config = {"from_attributes": True}


class CommitmentResponse(BaseModel):
    id: int
    title: str
    description: str | None
    author_id: int
    executor_id: int | None
    reviewer_id: int | None
    project_id: int | None
    deadline: datetime | None
    status: CommitmentStatus
    created_at: datetime
    updated_at: datetime
    author: UserBrief | None = None
    executor: UserBrief | None = None
    reviewer: UserBrief | None = None
    project: ProjectBrief | None = None

    model_config = {"from_attributes": True}
