from calendar import monthrange
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.commitment import Commitment, CommitmentStatus
from app.models.project import Project
from app.schemas.commitment import (
    CommitmentCreate,
    CommitmentResponse,
    CommitmentStatusUpdate,
    CommitmentUpdate,
    ProjectResponse,
)


def to_naive_utc(dt: datetime | None) -> datetime | None:
    """SQLite stores datetimes as naive UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(UTC).replace(tzinfo=None)


def utc_now_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def apply_expired_status(commitment: Commitment) -> None:
    if commitment.status in (
        CommitmentStatus.DONE,
        CommitmentStatus.NOT_ACTUAL,
        CommitmentStatus.EXPIRED,
    ):
        return
    if commitment.deadline is None:
        return
    deadline = to_naive_utc(commitment.deadline)
    if deadline and deadline < utc_now_naive():
        commitment.status = CommitmentStatus.EXPIRED


def status_display_color(status: CommitmentStatus) -> str:
    return {
        CommitmentStatus.TO_CHECK: "bg-blue-500",
        CommitmentStatus.EXPIRED: "bg-red-500",
        CommitmentStatus.DONE: "bg-green-500",
        CommitmentStatus.NOT_ACTUAL: "bg-gray-400",
        CommitmentStatus.IDEAS_BACKLOG: "bg-purple-500",
    }.get(status, "bg-gray-500")


def status_border_color(status: CommitmentStatus) -> str:
    return {
        CommitmentStatus.TO_CHECK: "border-blue-500",
        CommitmentStatus.EXPIRED: "border-red-500",
        CommitmentStatus.DONE: "border-green-500",
        CommitmentStatus.NOT_ACTUAL: "border-gray-400",
        CommitmentStatus.IDEAS_BACKLOG: "border-purple-500",
    }.get(status, "border-gray-500")


class CommitmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _base_query(self):
        return select(Commitment).options(
            selectinload(Commitment.author),
            selectinload(Commitment.executor),
            selectinload(Commitment.reviewer),
            selectinload(Commitment.project),
        )

    def _to_response(self, commitment: Commitment) -> CommitmentResponse:
        apply_expired_status(commitment)
        return CommitmentResponse.model_validate(commitment)

    async def list_projects(self) -> list[ProjectResponse]:
        result = await self.session.execute(select(Project).order_by(Project.name))
        return [ProjectResponse.model_validate(p) for p in result.scalars().all()]

    async def refresh_expired_statuses(self) -> None:
        now = utc_now_naive()
        await self.session.execute(
            update(Commitment)
            .where(
                Commitment.deadline < now,
                Commitment.status != CommitmentStatus.DONE,
                Commitment.status != CommitmentStatus.NOT_ACTUAL,
                Commitment.status != CommitmentStatus.EXPIRED,
                Commitment.deadline.isnot(None),
            )
            .values(status=CommitmentStatus.EXPIRED)
        )

    async def list_for_month(
        self,
        year: int,
        month: int,
        *,
        project_id: int | None = None,
        reviewer_id: int | None = None,
    ) -> list[CommitmentResponse]:
        await self.refresh_expired_statuses()
        _, last_day = monthrange(year, month)
        start = datetime(year, month, 1)
        end = datetime(year, month, last_day, 23, 59, 59)

        query = self._base_query().where(
            Commitment.deadline >= start,
            Commitment.deadline <= end,
        )
        if project_id is not None:
            query = query.where(Commitment.project_id == project_id)
        if reviewer_id is not None:
            query = query.where(Commitment.reviewer_id == reviewer_id)
        query = query.order_by(Commitment.deadline.asc())

        result = await self.session.execute(query)
        return [self._to_response(c) for c in result.scalars().all()]

    async def get_commitment(self, commitment_id: int) -> CommitmentResponse | None:
        await self.refresh_expired_statuses()
        result = await self.session.execute(
            self._base_query().where(Commitment.id == commitment_id)
        )
        item = result.scalar_one_or_none()
        if not item:
            return None
        return self._to_response(item)

    async def create_commitment(
        self, data: CommitmentCreate, author_id: int
    ) -> CommitmentResponse:
        status = data.status
        if data.deadline is None and status == CommitmentStatus.TO_CHECK:
            status = CommitmentStatus.IDEAS_BACKLOG

        commitment = Commitment(
            title=data.title,
            description=data.description,
            author_id=author_id,
            executor_id=data.executor_id,
            reviewer_id=data.reviewer_id,
            project_id=data.project_id,
            deadline=to_naive_utc(data.deadline),
            status=status,
        )
        self.session.add(commitment)
        await self.session.flush()
        return await self.get_commitment(commitment.id)  # type: ignore[arg-type]

    async def update_commitment(
        self,
        commitment_id: int,
        data: CommitmentUpdate,
    ) -> CommitmentResponse | None:
        result = await self.session.execute(
            select(Commitment).where(Commitment.id == commitment_id)
        )
        commitment = result.scalar_one_or_none()
        if not commitment:
            return None

        for field, value in data.model_dump(exclude_unset=True).items():
            if field == "deadline":
                value = to_naive_utc(value)
            setattr(commitment, field, value)
        commitment.updated_at = utc_now_naive()
        await self.session.flush()
        return await self.get_commitment(commitment_id)

    async def update_status(
        self, commitment_id: int, data: CommitmentStatusUpdate
    ) -> CommitmentResponse | None:
        return await self.update_commitment(
            commitment_id, CommitmentUpdate(status=data.status)
        )

    async def delete_commitment(self, commitment_id: int) -> bool:
        result = await self.session.execute(
            select(Commitment).where(Commitment.id == commitment_id)
        )
        commitment = result.scalar_one_or_none()
        if not commitment:
            return False
        await self.session.delete(commitment)
        return True
