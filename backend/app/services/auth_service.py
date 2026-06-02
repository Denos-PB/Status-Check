from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, verify_password
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def list_users(self) -> list[User]:
        result = await self.session.execute(select(User).order_by(User.full_name))
        return list(result.scalars().all())

    async def authenticate(self, data: LoginRequest) -> TokenResponse | None:
        user = await self.get_by_email(data.email)
        if not user or not verify_password(data.password, user.password_hash):
            return None
        return TokenResponse(access_token=create_access_token(user.id))
