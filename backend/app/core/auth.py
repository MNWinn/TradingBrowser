from collections.abc import Callable

from fastapi import Depends, Header, HTTPException

from app.core.config import settings


def _resolve_role_from_token(token: str) -> str | None:
    if token and token == settings.admin_api_token:
        return "admin"
    if token and token == settings.trader_api_token:
        return "trader"
    if token and token == settings.analyst_api_token:
        return "analyst"
    return None


def get_current_role(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = authorization.split(" ", 1)[1].strip()
    role = _resolve_role_from_token(token)
    if not role:
        raise HTTPException(status_code=401, detail="Invalid token")
    return role


def require_roles(*allowed: str) -> Callable:
    def _dep(role: str = Depends(get_current_role)) -> str:
        if role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return role

    return _dep
