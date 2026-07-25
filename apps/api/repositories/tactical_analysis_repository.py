# apps/api/repositories/tactical_analysis_repository.py
"""
SRP: Persistencia de análisis tácticos generados por el Cerebro Táctico (Fase 4).
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from apps.api.models.tactical_analysis import TacticalAnalysis


class TacticalAnalysisRepository:
    """
    Encapsula TODA la interacción con la DB para análisis tácticos.
    Recibe la sesión por DI — nunca la crea internamente.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_match_id(self, match_id: int) -> TacticalAnalysis | None:
        """Obtiene el análisis táctico de un partido específico."""
        stmt = select(TacticalAnalysis).where(TacticalAnalysis.match_id == match_id)
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def save(self, analysis: TacticalAnalysis) -> TacticalAnalysis:
        """Persiste un análisis táctico. Retorna el objeto con ID asignado."""
        self._session.add(analysis)
        await self._session.flush()
        await self._session.refresh(analysis)
        return analysis

    async def upsert(
        self,
        match_id: int,
        model_version: str,
        goals_narrative: dict | None,
        cards_narrative: dict | None,
        corners_narrative: dict | None,
        player_props_narratives: list | None,
        bet_builder_suggestions: list | None,
        overall_confidence: int,
        match_preview_headline: str,
        llm_model_used: str,
        generation_tokens_used: int,
        data_completeness_score: float,
    ) -> TacticalAnalysis:
        """
        Inserta o actualiza un análisis táctico.
        Si existe por match_id, actualiza. Si no, inserta.
        """
        existing = await self.get_by_match_id(match_id)
        
        if existing:
            existing.model_version = model_version
            existing.goals_narrative = goals_narrative
            existing.cards_narrative = cards_narrative
            existing.corners_narrative = corners_narrative
            existing.player_props_narratives = player_props_narratives
            existing.bet_builder_suggestions = bet_builder_suggestions
            existing.overall_confidence = overall_confidence
            existing.match_preview_headline = match_preview_headline
            existing.llm_model_used = llm_model_used
            existing.generation_tokens_used = generation_tokens_used
            existing.data_completeness_score = data_completeness_score
            await self._session.flush()
            await self._session.refresh(existing)
            return existing
        else:
            analysis = TacticalAnalysis(
                match_id=match_id,
                model_version=model_version,
                goals_narrative=goals_narrative,
                cards_narrative=cards_narrative,
                corners_narrative=corners_narrative,
                player_props_narratives=player_props_narratives,
                bet_builder_suggestions=bet_builder_suggestions,
                overall_confidence=overall_confidence,
                match_preview_headline=match_preview_headline,
                llm_model_used=llm_model_used,
                generation_tokens_used=generation_tokens_used,
                data_completeness_score=data_completeness_score,
            )
            self._session.add(analysis)
            await self._session.flush()
            await self._session.refresh(analysis)
            return analysis
