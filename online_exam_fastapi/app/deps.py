"""Shared FastAPI dependencies for database access and authentication."""

from typing import Optional

from app.database import get_session
from app.models import User
from fastapi import Depends, HTTPException, Request
from sqlmodel import Session


def get_current_user(
    request: Request, session: Session = Depends(get_session)
) -> Optional[User]:
    """Return the currently logged-in user based on the session cookie, if any."""
    user_id = request.session.get("user_id")
    if not user_id:
        return None

    user = session.get(User, user_id)
    if not user or not user.is_active:
        # Clear any stale session
        request.session.clear()
        return None
    # Check status field if it exists
    if hasattr(user, "status") and user.status == "suspended":
        request.session.clear()
        return None
    return user


def require_login(current_user: User = Depends(get_current_user)) -> User:
    """Ensure that a user is logged in; otherwise redirect to login."""
    if current_user is None:
        # Use 303 redirect to the login page
        raise HTTPException(status_code=303, headers={"Location": "/auth/login"})
    return current_user


def require_role(required_roles: list[str]):
    """Dependency factory that enforces one of the given roles."""

    def wrapper(current_user: User = Depends(require_login)) -> User:
        if current_user.role not in required_roles:
            raise HTTPException(status_code=403, detail="Forbidden")
        return current_user

    return wrapper
