"""Slamtec Cloud API client for BlitzWolf Vacuum."""
from __future__ import annotations

import asyncio
import base64
import logging
import time
from typing import Any

import aiohttp

from .const import CLOUD_URL, OAUTH_CLIENT_ID, OAUTH_CLIENT_SECRET

_LOGGER = logging.getLogger(__name__)


class AuthError(Exception):
    """Authentication error."""


class ApiError(Exception):
    """API error."""


class SlamtecApi:
    """Client for the Slamtec Cloud REST API."""

    def __init__(
        self,
        email: str,
        password: str,
        session: aiohttp.ClientSession | None = None,
    ) -> None:
        self._email = email
        self._password = password
        self._session = session
        self._owns_session = session is None
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._token_expires: float = 0
        self._user_id: str | None = None
        self._basic_auth = base64.b64encode(
            f"{OAUTH_CLIENT_ID}:{OAUTH_CLIENT_SECRET}".encode()
        ).decode()

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    @property
    def access_token(self) -> str | None:
        return self._access_token

    @property
    def user_id(self) -> str | None:
        return self._user_id

    async def authenticate(self) -> dict[str, Any]:
        """Authenticate with email/password, return token data."""
        session = await self._ensure_session()
        data = {
            "grant_type": "password",
            "username": self._email,
            "password": self._password,
        }
        headers = {
            "Authorization": f"Basic {self._basic_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        async with session.post(
            f"{CLOUD_URL}/oauth/token", data=data, headers=headers
        ) as resp:
            if resp.status == 400:
                raise AuthError("Invalid credentials")
            if resp.status == 401:
                raise AuthError("Unauthorized")
            resp.raise_for_status()
            result = await resp.json()

        self._access_token = result["access_token"]
        self._refresh_token = result.get("refresh_token")
        self._token_expires = time.time() + result.get("expires_in", 1800) - 60
        return result

    async def refresh_access_token(self) -> dict[str, Any]:
        """Refresh the access token."""
        if not self._refresh_token:
            return await self.authenticate()

        session = await self._ensure_session()
        data = {
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
        }
        headers = {
            "Authorization": f"Basic {self._basic_auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        async with session.post(
            f"{CLOUD_URL}/oauth/token", data=data, headers=headers
        ) as resp:
            if resp.status in (400, 401):
                _LOGGER.warning("Refresh token expired, re-authenticating")
                return await self.authenticate()
            resp.raise_for_status()
            result = await resp.json()

        self._access_token = result["access_token"]
        self._refresh_token = result.get("refresh_token", self._refresh_token)
        self._token_expires = time.time() + result.get("expires_in", 1800) - 60
        return result

    async def ensure_valid_token(self) -> str:
        """Ensure we have a valid access token, refreshing if needed."""
        if not self._access_token or time.time() >= self._token_expires:
            if self._refresh_token:
                await self.refresh_access_token()
            else:
                await self.authenticate()
        return self._access_token

    async def _get(self, path: str, accept: str | None = None) -> Any:
        """Make an authenticated GET request."""
        token = await self.ensure_valid_token()
        session = await self._ensure_session()
        headers = {"Authorization": f"Bearer {token}"}
        if accept:
            headers["Accept"] = accept

        async with session.get(f"{CLOUD_URL}{path}", headers=headers) as resp:
            if resp.status == 401:
                # Token might have been invalidated, try refresh
                token = await self.ensure_valid_token()
                headers["Authorization"] = f"Bearer {token}"
                async with session.get(
                    f"{CLOUD_URL}{path}", headers=headers
                ) as resp2:
                    resp2.raise_for_status()
                    return await resp2.json()
            resp.raise_for_status()
            return await resp.json()

    async def get_user_id(self) -> str:
        """Get the user UUID (needed for MQTT username)."""
        result = await self._get(
            "/api/users", accept="application/vnd.slamtec.user-v1.0+json"
        )
        self._user_id = result["user_id"]
        return self._user_id

    async def get_devices(self) -> list[dict[str, Any]]:
        """Get list of registered devices."""
        result = await self._get(
            "/api/devices", accept="application/vnd.slamtec.devicelist-v1.0+json"
        )
        return result.get("content", [])

    async def get_device(self, device_id: str) -> dict[str, Any]:
        """Get a single device info."""
        return await self._get(
            f"/api/devices/{device_id}",
            accept="application/vnd.slamtec.device-v1.0+json",
        )
