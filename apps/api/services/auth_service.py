"""
auth_service.py
~~~~~~~~~~~~~~~
Lógica de autenticación: hashing de contraseñas, emisión/verificación de JWTs
y envío de emails de recuperación (stub — ver nota de producción más abajo).

NOTA DE PRODUCCIÓN — EMAIL:
    No hay proveedor de email configurado en el proyecto. La función
    `send_password_reset_email` loguea el link en consola y NUNCA
    envía un email real. Antes de lanzar el flujo de recuperación a
    usuarios reales, reemplazar esta función con una integración de
    Resend (recomendado) o SMTP, y agregar las variables de entorno
    correspondientes (RESEND_API_KEY o SMTP_HOST/PORT/USER/PASS).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from apps.api.config import settings

logger = logging.getLogger(__name__)

# ── Password hashing ───────────────────────────────────────────────────────────

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

PASSWORD_RESET_TOKEN_EXPIRE_MINUTES = 30
PASSWORD_RESET_PURPOSE = "password_reset"


def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


# ── JWT helpers ────────────────────────────────────────────────────────────────

def _jwt_secret() -> str:
    """Use SUPABASE_JWT_SECRET when present (Supabase path), else SECRET_KEY."""
    return settings.SUPABASE_JWT_SECRET or settings.SECRET_KEY


def create_access_token(user_id: int) -> str:
    """Emit a session JWT valid for ACCESS_TOKEN_EXPIRE_MINUTES (7 days)."""
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=settings.ALGORITHM)


def create_reset_token(user_id: int) -> str:
    """Emit a short-lived JWT for password reset (30 min, purpose-scoped).

    Known limitation: JWT-based tokens cannot be invalidated server-side
    without a used-tokens table.  Acceptable for MVP given the 30-min TTL.
    """
    now = datetime.now(tz=timezone.utc)
    expire = now + timedelta(minutes=PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(user_id),
        "purpose": PASSWORD_RESET_PURPOSE,
        "iat": now,
        "exp": expire,
    }
    return jwt.encode(payload, _jwt_secret(), algorithm=settings.ALGORITHM)


def decode_reset_token(token: str) -> int:
    """Validate a password-reset JWT and return the user_id.

    Raises ValueError on any validation failure (expired, wrong purpose,
    bad signature, etc.) so callers can map it to a 400 response.
    """
    try:
        payload = jwt.decode(token, _jwt_secret(), algorithms=[settings.ALGORITHM])
    except JWTError as exc:
        raise ValueError("Token inválido o expirado") from exc

    if payload.get("purpose") != PASSWORD_RESET_PURPOSE:
        raise ValueError("Token no es de recuperación de contraseña")

    sub = payload.get("sub")
    if not isinstance(sub, str) or not sub:
        raise ValueError("Token sin identificador de usuario")

    try:
        return int(sub)
    except (TypeError, ValueError) as exc:
        raise ValueError("Identificador de usuario inválido en el token") from exc


# ── Email stub ─────────────────────────────────────────────────────────────────

def send_password_reset_email(email: str, reset_link: str) -> None:
    """
    ⚠️  STUB — no email is sent.

    In development this logs the reset link to stdout so you can copy-paste
    it manually.  Replace with a real email provider before going to
    production (see module docstring above).
    """
    logger.warning(
        "[EMAIL-STUB] Password reset requested for %s\n"
        "[EMAIL-STUB] Reset link (valid 30 min): %s\n"
        "[EMAIL-STUB] Configure a real email provider before production.",
        email,
        reset_link,
    )
