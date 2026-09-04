"""Authentication and coarse-grained authorization.

Two static bearer tokens (`API_BEARER_TOKEN`, `REVIEWER_BEARER_TOKEN`) are
enough to demonstrate the shape of the control — a caller can submit and
read cases, only a reviewer-scoped caller can act on the human-in-the-loop
endpoint — without pulling in a real identity provider for a portfolio
project. Swapping this for OAuth2/OIDC (Auth0, Cognito, an internal IdP)
touches only this module: every router depends on `Principal`, never on a
raw token.
"""

from __future__ import annotations

import hmac
from dataclasses import dataclass
from typing import Literal

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from underwriting.config import settings

_bearer_scheme = HTTPBearer(auto_error=False)

Role = Literal["caller", "reviewer"]


@dataclass(frozen=True)
class Principal:
    role: Role


def _constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def get_current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> Principal:
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing bearer token.")

    token = credentials.credentials
    if _constant_time_eq(token, settings.reviewer_bearer_token):
        return Principal(role="reviewer")
    if _constant_time_eq(token, settings.api_bearer_token):
        return Principal(role="caller")

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid bearer token.")


def require_reviewer(principal: Principal = Depends(get_current_principal)) -> Principal:
    if principal.role != "reviewer":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "This action requires the reviewer role."
        )
    return principal
