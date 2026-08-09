from __future__ import annotations

import hashlib
import logging
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
