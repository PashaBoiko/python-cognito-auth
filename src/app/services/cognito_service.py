"""Service for interacting with the AWS Cognito OAuth 2.0 endpoints.

Wraps the two HTTP calls required for the authorization-code flow:

1. ``exchange_code_for_token`` — POST to ``/oauth2/token`` to obtain tokens.
2. ``get_user_info`` — GET from ``/oauth2/userInfo`` to resolve identity.

``httpx.AsyncClient`` is used for all I/O so that this service integrates
cleanly into the async FastAPI request lifecycle without blocking the event
loop.
"""

from __future__ import annotations

import logging

import httpx
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

    async def exchange_code_for_token(self, code: str) -> dict:

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
                    detail=f"Cognito token exchange failed ({response.status_code}): {error_body}",
                )

            return response.json()

        except HTTPException:
            raise
        except httpx.TimeoutException:
            logger.error("Cognito token exchange timed out for code exchange")
            raise HTTPException(
                status_code=401,
                detail="Authorization code is invalid or expired",
            )
        except httpx.HTTPError as exc:
            logger.error("Cognito token exchange HTTP error: %s", exc)
            raise HTTPException(
                status_code=401,
                detail="Authorization code is invalid or expired",
            )

    async def get_user_info(self, access_token: str) -> dict:
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

            return response.json()

        except HTTPException:
            raise
        except httpx.TimeoutException:
            logger.error("Cognito userInfo request timed out")
            raise HTTPException(
                status_code=401,
                detail="Failed to get user information",
            )
        except httpx.HTTPError as exc:
            logger.error("Cognito userInfo HTTP error: %s", exc)
            raise HTTPException(
                status_code=401,
                detail="Failed to get user information",
            )
