from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class WebExtractedMatch(BaseModel):
    home_team: str = Field(..., description="Nombre del equipo local", min_length=1)
    away_team: str = Field(..., description="Nombre del equipo visitante", min_length=1)
    match_date: Optional[str] = Field(None, description="Fecha del partido (ISO 8601 o formato legible)")
    match_time: Optional[str] = Field(None, description="Hora del partido (HH:MM)")
    stadium: Optional[str] = Field(None, description="Estadio o venue del partido")
    matchday: Optional[int] = Field(None, description="Número de jornada", ge=1, le=50)
    status: str = Field("SCHEDULED", description="Estado del partido", pattern="^(SCHEDULED|FINISHED|LIVE|POSTPONED|CANCELLED)$")
    home_score: Optional[int] = Field(None, description="Goles equipo local (solo si FINISHED)", ge=0, le=20)
    away_score: Optional[int] = Field(None, description="Goles equipo visitante (solo si FINISHED)", ge=0, le=20)
    source_url: str = Field(..., description="URL de donde se extrajo el dato", min_length=1)
    confidence: float = Field(0.5, description="Confianza de la extracción (0.0-1.0)", ge=0.0, le=1.0)
    went_to_extra_time: bool = Field(False, description="Si el partido fue a tiempo extra")
    regulation_time_only: bool = Field(True, description="Si los goles son solo de tiempo reglamentario (90 min)")

    @field_validator("home_team", "away_team")
    @classmethod
    def validate_team_names(cls, v: str) -> str:
        v = v.strip()
        if len(v) < 2:
            raise ValueError("Team name must be at least 2 characters")
        if len(v) > 100:
            raise ValueError("Team name must be less than 100 characters")
        return v

    @field_validator("match_date")
    @classmethod
    def validate_date_format(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            return None
        return v

    def is_finished(self) -> bool:
        return self.status == "FINISHED"

    def has_scores(self) -> bool:
        return self.home_score is not None and self.away_score is not None


class WebExtractionResult(BaseModel):
    league_key: str = Field(..., description="Código de la liga (ej: liga_betplay)")
    season: int = Field(..., description="Temporada (año)", ge=2020, le=2030)
    matches: list[WebExtractedMatch] = Field(default_factory=list, description="Partidos extraídos")
    extraction_timestamp: datetime = Field(default_factory=datetime.utcnow, description="Timestamp de la extracción")
    total_sources: int = Field(0, description="Número de fuentes procesadas", ge=0)
    successful_extractions: int = Field(0, description="Número de extracciones exitosas", ge=0)
    warnings: list[str] = Field(default_factory=list, description="Advertencias durante la extracción")

    def get_finished_matches(self) -> list[WebExtractedMatch]:
        return [m for m in self.matches if m.is_finished()]

    def get_scheduled_matches(self) -> list[WebExtractedMatch]:
        return [m for m in self.matches if m.status == "SCHEDULED"]

    def get_high_confidence_matches(self, threshold: float = 0.7) -> list[WebExtractedMatch]:
        return [m for m in self.matches if m.confidence >= threshold]

    def summary(self) -> dict:
        return {
            "league_key": self.league_key,
            "season": self.season,
            "total_matches": len(self.matches),
            "finished_matches": len(self.get_finished_matches()),
            "scheduled_matches": len(self.get_scheduled_matches()),
            "high_confidence_matches": len(self.get_high_confidence_matches()),
            "total_sources": self.total_sources,
            "successful_extractions": self.successful_extractions,
            "warnings_count": len(self.warnings),
        }
