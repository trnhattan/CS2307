from typing import Literal

from pydantic import BaseModel, Field


Role = Literal["admin", "supervisor", "exam_taker"]


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=255)


class AuthenticatedUser(BaseModel):
    user_id: int
    username: str
    display_name: str
    role: Role
    student_id: int | None = None
    student_code: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthenticatedUser
