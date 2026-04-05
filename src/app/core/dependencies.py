import uuid
from collections.abc import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import jwt_settings
from app.core.database import async_session_maker
from app.core.redis import get_redis_client
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.cognito_service import CognitoService
from app.services.token_service import TokenService


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:

    async with async_session_maker() as session:
        yield session


async def get_user_repository(
    session: AsyncSession = Depends(get_db_session),
) -> UserRepository:
    return UserRepository(session)


def get_cognito_service() -> CognitoService:
    return CognitoService()


async def get_token_service(
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> TokenService:
    return TokenService(redis_client)


async def get_auth_service(
    session: AsyncSession = Depends(get_db_session),
    cognito_service: CognitoService = Depends(get_cognito_service),
    user_repository: UserRepository = Depends(get_user_repository),
    token_service: TokenService = Depends(get_token_service),
) -> AuthService:
    return AuthService(cognito_service, user_repository, session, token_service)


async def get_current_user(
    request: Request,
    user_repository: UserRepository = Depends(get_user_repository),
    token_service: TokenService = Depends(get_token_service),
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
    except JWTError as err:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from err

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="Invalid token payload")

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError as err:
        # ``sub`` was present but not a valid UUID — treat as a malformed token.
        raise HTTPException(status_code=401, detail="Invalid token payload") from err

    # Verify the token is active in Redis before trusting it.
    token_data = await token_service.validate_token(token)
    if token_data is None:
        raise HTTPException(
            status_code=401,
            detail="Token has been revoked or user not found",
        )

    # Fetch the full User record from PostgreSQL using the ID embedded in the JWT.
    user = await user_repository.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Token has been revoked or user not found",
        )

    return user
