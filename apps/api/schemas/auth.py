from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, model_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: Optional[str] = None
    age_confirmed: bool = False

    @model_validator(mode="after")
    def check_age_confirmed(self) -> "UserCreate":
        if not self.age_confirmed:
            raise ValueError("Debés confirmar que sos mayor de 18 años.")
        return self


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str] = None
    is_active: bool = True

    model_config = {"from_attributes": True}


class UserMeResponse(BaseModel):
    """Full user profile returned by GET /api/v1/users/me."""

    id: int
    email: str
    full_name: Optional[str] = None
    is_active: bool
    is_pro: bool
    pro_expires_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ── Password reset flow ────────────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    message: str = (
        "Si el email existe en nuestro sistema, vas a recibir un link "
        "para restablecer tu contraseña."
    )


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class ResetPasswordResponse(BaseModel):
    message: str = "Contraseña actualizada correctamente."
