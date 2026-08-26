from __future__ import annotations

from abc import ABC, abstractmethod

from fastapi import Header, HTTPException, status


class AuthenticationError(Exception):
    """Raised when a request cannot be authenticated. Carries no stack
    trace-worthy detail - just enough to build a structured 401 response."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message)
        self.message = message


class AuthenticationService(ABC):
    """Abstraction the Gateway depends on. Swappable later for:

        AuthenticationService
                v
        JWTAuthenticationService
                v
        OAuthAuthenticationService

    without touching routes.py, controller.py, or anything downstream.
    """

    @abstractmethod
    def authenticate(self, authorization: str | None, user_id: str | None) -> str:
        """Validate the caller's credentials and return an authenticated
        principal/user identifier. Raises AuthenticationError on failure.
        """
        raise NotImplementedError


class DevAuthenticationService(AuthenticationService):
    """MVP development authentication.

    Accepts any request that carries a non-empty `Authorization` header and
    a `userId`, and simply echoes the userId back as the authenticated
    principal. This is deliberately minimal - it exists so the Gateway has a
    real authentication *seam* from day one, without hard-coupling to JWT/
    OAuth before those providers are actually chosen. Not suitable for
    production use as-is.
    """

    def __init__(self, require_header: bool = True):
        self._require_header = require_header

    def authenticate(self, authorization: str | None, user_id: str | None) -> str:
        if self._require_header and not authorization:
            raise AuthenticationError("Missing Authorization header")

        if not user_id or not user_id.strip():
            raise AuthenticationError("Missing userId")

        return user_id


def get_authorization_header(authorization: str | None = Header(default=None)) -> str | None:
    """FastAPI dependency: extracts the raw Authorization header without
    ever logging it (see gateway/middleware.py, which explicitly excludes
    this value from structured logs)."""
    return authorization


def raise_http_authentication_error(error: AuthenticationError) -> None:
    raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=error.message)
