from collections.abc import AsyncGenerator

from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings
from app.core.security import get_password_hash

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
)


@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:
    if engine.dialect.name == "sqlite":
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    from app.models import Commitment, Project, User  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed_if_empty(session: AsyncSession) -> None:
    from app.models.project import Project
    from app.models.user import User
    from app.services.auth_service import AuthService

    auth = AuthService(session)
    if await auth.get_by_email("user@example.com"):
        return

    session.add_all(
        [
            User(
                email="user@example.com",
                password_hash=get_password_hash("user123"),
                full_name="Demo User",
            ),
            User(
                email="reviewer@example.com",
                password_hash=get_password_hash("reviewer123"),
                full_name="Demo Reviewer",
            ),
        ]
    )
    await session.flush()

    existing = await session.execute(select(Project).limit(1))
    if existing.scalar_one_or_none():
        return

    session.add_all(
        [
            Project(name="Platform", description="Core platform work"),
            Project(name="Mobile", description="Mobile app"),
        ]
    )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
