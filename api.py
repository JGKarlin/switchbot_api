"""SwitchBot API client utilities."""

from __future__ import annotations

from asyncio import TimeoutError
import base64
import hashlib
import hmac
import time
import uuid
from typing import Any

from aiohttp import ClientError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_BASE_URL


def generate_auth_headers(token: str, secret: str) -> dict[str, str]:
    """Generate SwitchBot API auth headers."""
    t = str(int(round(time.time() * 1000)))
    nonce = str(uuid.uuid4())
    string_to_sign = f"{token}{t}{nonce}"
    sign = base64.b64encode(
        hmac.new(
            secret.encode("utf-8"),
            msg=string_to_sign.encode("utf-8"),
            digestmod=hashlib.sha256,
        ).digest()
    ).decode("utf-8")
    return {
        "Authorization": token,
        "t": t,
        "nonce": nonce,
        "sign": sign,
    }


def generate_auth_payload(token: str, secret: str, *, ttl_seconds: int) -> dict[str, str | int]:
    """Generate auth headers with metadata for diagnostics and service responses."""
    headers = generate_auth_headers(token, secret)
    generated_at = int(headers["t"])

    return {
        "authorization": headers["Authorization"],
        "t": headers["t"],
        "nonce": headers["nonce"],
        "sign": headers["sign"],
        "generated_at": generated_at,
        "expires_at": generated_at + (ttl_seconds * 1000),
        "ttl_seconds": ttl_seconds,
    }


class SwitchBotApiError(Exception):
    """Raised when the SwitchBot API returns an error."""

    def __init__(self, message: str, *, auth_failed: bool = False) -> None:
        """Initialize the API error."""
        super().__init__(message)
        self.auth_failed = auth_failed


async def async_request(
    hass: HomeAssistant,
    method: str,
    path: str,
    token: str,
    secret: str,
    *,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute a SwitchBot API request and return the response body."""
    headers = generate_auth_headers(token, secret)
    headers["Content-Type"] = "application/json"
    session = async_get_clientsession(hass)

    try:
        async with session.request(
            method,
            f"{API_BASE_URL}{path}",
            headers=headers,
            json=payload,
        ) as response:
            try:
                data = await response.json()
            except (ValueError, TypeError):
                text = await response.text()
                raise SwitchBotApiError(
                    f"Unexpected response from SwitchBot API: {text or response.reason}"
                ) from None
    except (ClientError, TimeoutError) as exc:
        raise SwitchBotApiError("Could not connect to the SwitchBot API") from exc

    if response.status == 401:
        raise SwitchBotApiError("Invalid token or secret", auth_failed=True)

    if response.status != 200:
        message = data.get("message") or response.reason or f"HTTP {response.status}"
        raise SwitchBotApiError(
            f"SwitchBot API returned HTTP {response.status}: {message}"
        )

    if data.get("statusCode") != 100:
        message = data.get("message", "Unknown error")
        auth_failed = "unauthor" in message.lower() or "invalid token" in message.lower()
        raise SwitchBotApiError(message, auth_failed=auth_failed)

    body = data.get("body")
    if isinstance(body, dict):
        return body

    return {"items": body}
