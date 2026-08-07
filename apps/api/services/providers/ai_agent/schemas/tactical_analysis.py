from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TacticalAnalysisOutput(BaseModel):
    """Strict boundary contract for raw provider output.

    The provider may only return a short analysis grounded in the metrics
    included by the orchestrator. Invalid or incomplete JSON is rejected so
    the cascade can try the next provider or deterministic synthesis.
    """

    resumen_tactico: str = Field(..., min_length=1, max_length=600)
    puntos_clave: list[str] = Field(default_factory=list, max_length=5)
    nivel_riesgo: Literal["BAJO", "MODERADO", "ALTO"] = "MODERADO"

    @field_validator("nivel_riesgo", mode="before")
    @classmethod
    def normalize_risk(cls, value: object) -> str:
        normalized = str(value).strip().upper()
        aliases = {"LOW": "BAJO", "MEDIUM": "MODERADO", "MODERATE": "MODERADO", "HIGH": "ALTO"}
        return aliases.get(normalized, normalized)
