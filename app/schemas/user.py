"""Schemas de usuario para GET /users/me."""

from datetime import datetime

from pydantic import BaseModel


class UserMeOut(BaseModel):
    """Response de GET /users/me."""

    id: str
    email: str
    display_name: str
    role: str
    has_team: bool
    team_id: str | None
    auth_methods: list[str]
    created_at: datetime

    class Config:
        from_attributes = True
