from __future__ import annotations

import hashlib
import hmac
import logging
import time
from typing import Any

import httpx

from apps.api.config import settings

logger = logging.getLogger(__name__)
# httpx logs request URLs at INFO; the merchant lookup URL contains the public
# key, so transport logs must not leak payment credentials.
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


class WompiConfigurationError(RuntimeError):
    pass


class WompiAPIError(RuntimeError):
    def __init__(self, status_code: int, message: str, payload: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def amount_for_plan(plan: str) -> int:
    if plan == "mensual":
        return settings.WOMPI_MONTHLY_AMOUNT_CENTS
    if plan == "anual":
        return settings.WOMPI_ANNUAL_AMOUNT_CENTS
    raise ValueError(f"Unsupported subscription plan: {plan}")


def integrity_signature(reference: str, amount_in_cents: int) -> str:
    if not settings.WOMPI_INTEGRITY_SECRET:
        raise WompiConfigurationError("WOMPI_INTEGRITY_SECRET is not configured")
    raw = f"{reference}{amount_in_cents}COP{settings.WOMPI_INTEGRITY_SECRET}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def recurrence_enabled_from_transaction(data: dict[str, Any]) -> bool | None:
    """Read an explicit COF capability when Wompi includes it in a response."""
    candidates = [
        data.get("recurrent"),
        (data.get("payment_method") or {}).get("recurrent"),
        ((data.get("payment_method") or {}).get("extra") or {}).get("recurrent"),
    ]
    for value in candidates:
        if isinstance(value, bool):
            return value
    return None


def _lookup_path(data: dict[str, Any], path: str) -> Any:
    current: Any = data
    for segment in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(segment)
    return current


def compute_wompi_event_checksum(payload: dict[str, Any], secret: str) -> str | None:
    """Recompute the Wompi event checksum from the signed properties.

    Wompi v1 signs webhook events by concatenating the values of
    `signature.properties` (resolved against `data`), the event `timestamp`
    and the configured `WOMPI_EVENTS_SECRET`, then hashing with SHA-256.
    Returns None when the payload is missing the pieces required to sign.
    """
    signature = payload.get("signature")
    if not isinstance(signature, dict):
        return None
    properties = signature.get("properties")
    timestamp = payload.get("timestamp")
    if not isinstance(properties, list) or timestamp is None:
        return None
    event_data = payload.get("data") or {}
    values = [_lookup_path(event_data, str(path)) for path in properties]
    raw = "".join("" if value is None else str(value) for value in values)
    raw += str(timestamp) + secret
    return hashlib.sha256(raw.encode("utf-8")).hexdigest().lower()


def is_valid_wompi_event_signature(
    payload: dict[str, Any],
    header_checksum: str | None,
    *,
    secret: str | None = None,
) -> bool:
    """Constant-time validation of the Wompi event signature.

    Accepts the checksum delivered in the `X-Event-Checksum` header, in the
    body's `signature.checksum`, or both. A missing WOMPI_EVENTS_SECRET makes
    validation fail closed so events are never trusted by default.
    """
    effective_secret = settings.WOMPI_EVENTS_SECRET if secret is None else secret
    if not effective_secret:
        return False
    computed = compute_wompi_event_checksum(payload, effective_secret)
    if computed is None:
        return False
    signature = payload.get("signature") or {}
    body_checksum = signature.get("checksum")
    provided = [
        value.lower()
        for value in (header_checksum, body_checksum)
        if isinstance(value, str) and value
    ]
    return bool(provided) and all(hmac.compare_digest(computed, value) for value in provided)


# Ventana máxima de aceptación de un evento Wompi (segundos).
WOMPI_EVENT_MAX_AGE_SECONDS = 300


def is_wompi_event_fresh(
    payload: dict[str, Any],
    *,
    max_age_seconds: int = WOMPI_EVENT_MAX_AGE_SECONDS,
    now: float | None = None,
) -> bool:
    """Rechaza eventos antiguos interceptados (protección contra replay).

    Compara el `timestamp` del payload (epoch Unix; soporta milisegundos si
    el valor > 1e12) contra el reloj del servidor. Un evento con
    |now - timestamp| > max_age_seconds se considera expirado.
    """
    raw_timestamp = payload.get("timestamp")
    if raw_timestamp is None:
        return False
    try:
        event_time = float(str(raw_timestamp))
    except (TypeError, ValueError):
        return False
    if event_time > 1e12:
        event_time /= 1000.0
    now_seconds = time.time() if now is None else now
    return abs(now_seconds - event_time) <= max_age_seconds


def extract_wompi_event_transaction(payload: dict[str, Any]) -> dict[str, Any]:
    """Pull the `transaction` object from a `transaction.updated` event."""
    if payload.get("event") != "transaction.updated":
        return {}
    data = payload.get("data")
    if not isinstance(data, dict):
        return {}
    transaction = data.get("transaction")
    return transaction if isinstance(transaction, dict) else {}


class WompiClient:
    def __init__(self) -> None:
        self._base_url = settings.WOMPI_BASE_URL.rstrip("/")

    def _require_private_key(self) -> str:
        if not settings.WOMPI_PRIVATE_KEY:
            raise WompiConfigurationError("WOMPI_PRIVATE_KEY is not configured")
        return settings.WOMPI_PRIVATE_KEY

    def _require_public_key(self) -> str:
        if not settings.WOMPI_PUBLIC_KEY:
            raise WompiConfigurationError("WOMPI_PUBLIC_KEY is not configured")
        return settings.WOMPI_PUBLIC_KEY

    async def _get(self, path: str) -> dict[str, Any]:
        public_key = self._require_public_key()
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    f"{self._base_url}/{path.lstrip('/')}",
                    headers={"Authorization": f"Bearer {public_key}"},
                )
        except httpx.HTTPError as exc:
            raise WompiAPIError(503, "No se pudo conectar con Wompi.") from exc
        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": response.text}
        if not response.is_success:
            message = (
                payload.get("error", {}).get("reason")
                if isinstance(payload.get("error"), dict)
                else None
            ) or payload.get("message") or "Wompi rechazó la operación."
            raise WompiAPIError(response.status_code, str(message), payload)
        return payload

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        private_key = self._require_private_key()
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.post(
                    f"{self._base_url}/{path.lstrip('/')}",
                    headers={
                        "Authorization": f"Bearer {private_key}",
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
        except httpx.HTTPError as exc:
            raise WompiAPIError(503, "No se pudo conectar con Wompi.") from exc

        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": response.text}
        if not response.is_success:
            message = (
                payload.get("error", {}).get("reason")
                if isinstance(payload.get("error"), dict)
                else None
            ) or payload.get("message") or "Wompi rechazó la operación."
            raise WompiAPIError(response.status_code, str(message), payload)
        return payload

    async def get_acceptance_tokens(self) -> tuple[str, str]:
        public_key = self._require_public_key()
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    f"{self._base_url}/merchants/{public_key}",
                    headers={"Authorization": f"Bearer {public_key}"},
                )
        except httpx.HTTPError as exc:
            raise WompiAPIError(503, "No se pudo conectar con Wompi.") from exc
        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": response.text}
        if not response.is_success:
            raise WompiAPIError(response.status_code, "No se pudieron obtener los tokens de aceptación.", payload)
        data = payload.get("data") or {}
        acceptance = (data.get("presigned_acceptance") or {}).get("acceptance_token")
        personal = (data.get("presigned_personal_data_auth") or {}).get("acceptance_token")
        if not acceptance or not personal:
            raise WompiAPIError(502, "Wompi no devolvió tokens de aceptación completos.", payload)
        return str(acceptance), str(personal)

    async def get_tokenization_public_key(self) -> str:
        public_key = self._require_public_key()
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                response = await client.get(
                    f"{self._base_url}/tokens/keys/tokenization",
                    headers={"Authorization": f"Bearer {public_key}"},
                )
        except httpx.HTTPError as exc:
            raise WompiAPIError(503, "No se pudo conectar con Wompi.") from exc
        try:
            payload = response.json()
        except ValueError:
            payload = {"raw": response.text}
        if not response.is_success:
            raise WompiAPIError(response.status_code, "No se pudo obtener la llave de tokenización.", payload)
        tokenization_key = (payload.get("data") or {}).get("publicKey")
        if not tokenization_key:
            raise WompiAPIError(502, "Wompi no devolvió la llave de tokenización.", payload)
        return str(tokenization_key)

    async def create_payment_source(
        self,
        *,
        card_token: str,
        customer_email: str,
        acceptance_token: str,
        accept_personal_auth: str,
    ) -> dict[str, Any]:
        payload = await self._post(
            "/payment_sources",
            {
                "type": "CARD",
                "token": card_token,
                "customer_email": customer_email,
                "acceptance_token": acceptance_token,
                "accept_personal_auth": accept_personal_auth,
            },
        )
        data = payload.get("data")
        if not isinstance(data, dict) or not data.get("id"):
            raise WompiAPIError(502, "Wompi no devolvió una fuente de pago válida.", payload)
        if data.get("status") not in {"AVAILABLE", None}:
            raise WompiAPIError(422, "La fuente de pago no quedó disponible.", payload)
        return data

    async def create_recurrent_transaction(
        self,
        *,
        payment_source_id: str,
        customer_email: str,
        plan: str,
        acceptance_token: str,
        accept_personal_auth: str,
        reference: str,
    ) -> dict[str, Any]:
        amount_in_cents = amount_for_plan(plan)
        payload = await self._post(
            "/transactions",
            {
                "amount_in_cents": amount_in_cents,
                "currency": "COP",
                "customer_email": customer_email,
                "payment_source_id": int(payment_source_id)
                if payment_source_id.isdigit()
                else payment_source_id,
                "payment_method": {"installments": 1},
                "recurrent": True,
                "reference": reference,
                "signature": integrity_signature(reference, amount_in_cents),
                "acceptance_token": acceptance_token,
                "accept_personal_auth": accept_personal_auth,
            },
        )
        data = payload.get("data")
        if not isinstance(data, dict) or not data.get("id"):
            raise WompiAPIError(502, "Wompi no devolvió una transacción válida.", payload)
        return data

    async def get_transaction(self, transaction_id: str) -> dict[str, Any]:
        payload = await self._get(f"/transactions/{transaction_id}")
        data = payload.get("data")
        if not isinstance(data, dict) or not data.get("id"):
            raise WompiAPIError(502, "Wompi no devolvió datos de la transacción.", payload)
        return data
