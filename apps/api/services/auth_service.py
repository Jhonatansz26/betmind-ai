"""
auth_service.py
~~~~~~~~~~~~~~~
Lógica de autenticación: hashing de contraseñas, emisión/verificación de JWTs
y envío de emails de recuperación (SMTP > Resend > fallback a consola).
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


# ── Email ──────────────────────────────────────────────────────────────────────

_RESET_EMAIL_SUBJECT = "Restablecé tu contraseña de BetMind"


def _reset_email_body(reset_link: str) -> str:
    return (
        "Recibiste este correo porque pediste restablecer tu contraseña en BetMind.\n\n"
        f"Hacé clic en el siguiente enlace para crear una nueva contraseña "
        f"(expira en 30 minutos):\n\n{reset_link}\n\n"
        "Si no pediste este cambio, ignorá este mensaje."
    )


def _log_stub(email: str, reset_link: str) -> None:
    masked_email = email.split("@")[0] if "@" in email else email
    if len(masked_email) > 3:
        masked_email = masked_email[:2] + "***"
    else:
        masked_email = masked_email[:1] + "***"
    domain = email[email.index("@") + 1:] if "@" in email else "unknown"
    logger.warning(
        "[EMAIL-STUB] Password reset requested for %s@%s. "
        "Configure SMTP_USERNAME/SMTP_PASSWORD or RESEND_API_KEY to send real emails.",
        masked_email,
        domain,
    )
    show_link = settings.EMAIL_STUB_SHOW_LINK if getattr(settings, "EMAIL_STUB_SHOW_LINK", None) else False
    if show_link:
        logger.warning("[EMAIL-STUB-DEBUG] Reset link (valid 30 min): %s", reset_link)


def _send_via_resend(email: str, reset_link: str) -> None:
    import resend

    resend.api_key = settings.RESEND_API_KEY
    resend.Emails.send({
        "from": settings.EMAIL_FROM_ADDRESS,
        "to": [email],
        "subject": _RESET_EMAIL_SUBJECT,
        "text": _reset_email_body(reset_link),
    })


async def _send_via_smtp(email: str, reset_link: str) -> None:
    from email.mime.text import MIMEText

    import aiosmtplib

    message = MIMEText(_reset_email_body(reset_link))
    message["Subject"] = _RESET_EMAIL_SUBJECT
    message["From"] = settings.SMTP_USERNAME
    message["To"] = email

    await aiosmtplib.send(
        message,
        hostname=settings.SMTP_SERVER,
        port=settings.SMTP_PORT,
        start_tls=True,
        username=settings.SMTP_USERNAME,
        password=settings.SMTP_PASSWORD,
    )


async def send_password_reset_email(email: str, reset_link: str) -> None:
    if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
        try:
            await _send_via_smtp(email, reset_link)
            logger.info("Password reset email sent via SMTP to %s", email)
            return
        except Exception:
            logger.exception("SMTP send failed for %s", email)
            return

    if settings.RESEND_API_KEY:
        try:
            _send_via_resend(email, reset_link)
            logger.info("Password reset email sent via Resend to %s", email)
            return
        except Exception:
            logger.exception("Resend send failed for %s", email)
            return

    _log_stub(email, reset_link)
