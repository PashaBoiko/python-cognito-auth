import uuid
from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import jwt_settings
from app.core.database import async_session_maker
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.cognito_service import CognitoService


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:

    async with async_session_maker() as session:
        yield session


async def get_user_repository(
    session: AsyncSession = Depends(get_db_session),
) -> UserRepository:
    return UserRepository(session)


def get_cognito_service() -> CognitoService:
    return CognitoService()


async def get_auth_service(
    session: AsyncSession = Depends(get_db_session),
    cognito_service: CognitoService = Depends(get_cognito_service),
    user_repository: UserRepository = Depends(get_user_repository),
) -> AuthService:
    return AuthService(cognito_service, user_repository, session)


async def get_current_user(
    request: Request,
    user_repository: UserRepository = Depends(get_user_repository),
) -> User:
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header",
        )

    token = auth_header.removeprefix("Bearer ").strip()

    try:
        payload = jwt.decode(token, jwt_settings.JWT_SECRET, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        # ``sub`` was present but not a valid UUID — treat as a malformed token.
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = await user_repository.get_by_id_and_token(user_id, token)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Token has been revoked or user not found",
        )

    return user
