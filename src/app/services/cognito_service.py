"""Service for interacting with the AWS Cognito OAuth 2.0 endpoints.

Wraps the two HTTP calls required for the authorization-code flow:

1. ``exchange_code_for_token`` — POST to ``/oauth2/token`` to obtain tokens.
2. ``get_user_info`` — GET from ``/oauth2/userInfo`` to resolve identity.

``httpx.AsyncClient`` is used for all I/O so that this service integrates
cleanly into the async FastAPI request lifecycle without blocking the event
loop.
"""

from __future__ import annotations

import asyncio
import logging

import boto3
import httpx
from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.core.config import cognito_settings

logger = logging.getLogger(__name__)

# Seconds to wait for a response from Cognito before raising a timeout error.
_COGNITO_TIMEOUT = 5.0


class CognitoService:
    """HTTP client wrapper around the Cognito hosted-UI OAuth endpoints.

    A single ``httpx.AsyncClient`` is created per service instance.  Callers
    that want connection reuse across requests should manage the client
    lifetime (e.g. via FastAPI lifespan) and inject a shared instance;
    creating a short-lived instance per request is also safe.
    """

    async def exchange_code_for_token(self, code: str) -> dict[str, object]:

        token_url = f"{cognito_settings.COGNITO_URL}/oauth2/token"
        payload = {
            "grant_type": "authorization_code",
            "client_id": cognito_settings.COGNITO_CLIENT_ID,
            "code": code,
            "redirect_uri": cognito_settings.COGNITO_LOGIN_REDIRECT_URL,
            "scope": cognito_settings.COGNITO_SCOPE,
        }

        try:
            async with httpx.AsyncClient(timeout=_COGNITO_TIMEOUT) as client:
                response = await client.post(
                    token_url,
                    data=payload,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )

            if not response.is_success:
                error_body = response.text
                logger.error(
                    "Cognito token exchange failed (status=%s): %s",
                    response.status_code,
                    error_body,
                )
                raise HTTPException(
                    status_code=401,
                    detail=(
                        f"Cognito token exchange failed "
                        f"({response.status_code}): {error_body}"
                    ),
                )

            result: dict[str, object] = response.json()
            return result

        except HTTPException:
            raise
        except httpx.TimeoutException as err:
            logger.error("Cognito token exchange timed out for code exchange")
            raise HTTPException(
                status_code=401,
                detail="Authorization code is invalid or expired",
            ) from err
        except httpx.HTTPError as exc:
            logger.error("Cognito token exchange HTTP error: %s", exc)
            raise HTTPException(
                status_code=401,
                detail="Authorization code is invalid or expired",
            ) from exc

    async def get_user_info(self, access_token: str) -> dict[str, object]:
        """Retrieve identity claims for the authenticated user from Cognito.

        Sends a ``GET`` to ``{COGNITO_URL}/oauth2/userInfo`` with the access
        token supplied as a ``Bearer`` credential.

        Returns a ``dict`` containing at minimum:

        - ``sub`` — Cognito unique user identifier
        - ``email`` — user's email address

        Raises:
            HTTPException: 401 when Cognito returns a non-2xx response or the
                HTTP call itself fails.
        """
        userinfo_url = f"{cognito_settings.COGNITO_URL}/oauth2/userInfo"

        try:
            async with httpx.AsyncClient(timeout=_COGNITO_TIMEOUT) as client:
                response = await client.get(
                    userinfo_url,
                    headers={"Authorization": f"Bearer {access_token}"},
                )

            if not response.is_success:
                error_body = response.text
                logger.error(
                    "Cognito userInfo failed (status=%s): %s",
                    response.status_code,
                    error_body,
                )
                raise HTTPException(
                    status_code=401,
                    detail="Failed to get user information from Cognito",
                )

            result: dict[str, object] = response.json()
            return result

        except HTTPException:
            raise
        except httpx.TimeoutException as err:
            logger.error("Cognito userInfo request timed out")
            raise HTTPException(
                status_code=401,
                detail="Failed to get user information",
            ) from err
        except httpx.HTTPError as exc:
            logger.error("Cognito userInfo HTTP error: %s", exc)
            raise HTTPException(
                status_code=401,
                detail="Failed to get user information",
            ) from exc

    async def admin_disable_user(self, cognito_sub: str) -> None:
        """Disable a user account in the Cognito User Pool.

        Uses the boto3 ``AdminDisableUser`` API to prevent the user from
        signing in.  The synchronous boto3 call is offloaded to a thread
        via ``asyncio.to_thread`` so the FastAPI event loop is not blocked.

        Args:
            cognito_sub: The Cognito ``sub`` (unique user identifier) of the
                user to disable.

        Raises:
            HTTPException: 502 when the Cognito admin API call fails.
        """
        cognito_client = boto3.client(
            "cognito-idp",
            region_name=cognito_settings.COGNITO_REGION,
        )

        try:
            await asyncio.to_thread(
                cognito_client.admin_disable_user,
                UserPoolId=cognito_settings.COGNITO_USER_POOL_ID,
                Username=cognito_sub,
            )
        except ClientError as exc:
            error_message = exc.response["Error"]["Message"]
            logger.error(
                "Failed to disable user %s in Cognito: %s",
                cognito_sub,
                error_message,
            )
            raise HTTPException(
                status_code=502,
                detail=f"Failed to disable user in Cognito: {error_message}",
            ) from exc
