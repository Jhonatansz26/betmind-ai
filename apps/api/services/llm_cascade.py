"""
Cascade LLM Service — Groq → Gemini → Synthetic fallback.

Capa 2 del sistema de resiliencia: si Groq falla (429, timeout, error),
automáticamente conmuta a Gemini. Si ambos fallan, genera narrativa sintética
desde datos estadísticos sin consumir tokens.
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from apps.api.config import settings
from apps.api.services.providers.ai_agent.schemas.tactical_analysis import TacticalAnalysisOutput

logger = logging.getLogger(__name__)

_GEMINI_AVAILABLE = False
try:
    from google import genai as google_genai
    _GEMINI_AVAILABLE = True
except ImportError:
    logger.info("google-genai no instalado. Gemini no disponible como fallback.")


class LLMCascadeResult:
    __slots__ = ("content", "model_used", "tokens_used", "provider")

    def __init__(self, content: dict | None, model_used: str, tokens_used: int, provider: str):
        self.content = content
        self.model_used = model_used
        self.tokens_used = tokens_used
        self.provider = provider


class LLMCascadeService:
    """
    Servicio de cascada multi-proveedor para generación de análisis táctico.

    Flujo:
        1. Groq (llama-3.1-8b-instant) — primera opción
        2. Gemini (gemini-2.0-flash) — fallback automático
        3. None — el caller genera narrativa sintética (Capa 1)
    """

    GROQ_MODEL = "llama-3.1-8b-instant"
    GEMINI_MODEL = "gemini-2.0-flash"
    MAX_TOKENS = 400

    def __init__(self) -> None:
        self._groq_client = None
        self._gemini_model = None
        self._init_groq()
        self._init_gemini()

    def _init_groq(self) -> None:
        keys = settings.get_groq_api_keys()
        if not keys:
            logger.warning("Sin GROQ_API_KEY configurada")
            return
        try:
            from groq import Groq
            self._groq_client = Groq(api_key=keys[0], max_retries=0)
            logger.info("Groq client inicializado")
        except Exception as e:
            logger.error(f"Error inicializando Groq: {e}")

    def _init_gemini(self) -> None:
        if not _GEMINI_AVAILABLE:
            return
        api_key = getattr(settings, "GEMINI_API_KEY", None)
        if not api_key:
            logger.warning("Sin GEMINI_API_KEY configurada")
            return
        try:
            self._gemini_model = google_genai.Client(api_key=api_key)
            logger.info("Gemini client inicializado")
        except Exception as e:
            logger.error(f"Error inicializando Gemini: {e}")

    async def generate_tactical_json(
        self,
        system_prompt: str,
        user_prompt: str,
    ) -> LLMCascadeResult:
        """
        Genera análisis táctico en JSON usando cascada Groq → Gemini → None.

        Returns:
            LLMCascadeResult con content=None si ambas APIs fallan
            (el caller debe usar Capa 1: narrativa sintética).
        """

        try:
            result = await asyncio.wait_for(
                self._try_groq(system_prompt, user_prompt),
                timeout=settings.GROQ_SINGLE_CALL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("Groq superó el timeout de una llamada; conmutando a Gemini")
            result = None
        if result is not None:
            return result

        logger.warning("Groq falló. Conmutando a Gemini...")
        try:
            result = await asyncio.wait_for(
                self._try_gemini(system_prompt, user_prompt),
                timeout=settings.GROQ_SINGLE_CALL_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning("Gemini superó el timeout de una llamada; usando síntesis")
            result = None
        if result is not None:
            return result

        logger.error("Gemini también falló. Usar Capa 1 (narrativa sintética).")
        return LLMCascadeResult(
            content=None,
            model_used="none",
            tokens_used=0,
            provider="synthetic",
        )

    async def _try_groq(self, system_prompt: str, user_prompt: str) -> LLMCascadeResult | None:
        if self._groq_client is None:
            return None
        try:
            from groq import Groq

            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self._groq_client.chat.completions.create(
                    model=self.GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=self.MAX_TOKENS,
                    temperature=0.3,
                    response_format={"type": "json_object"},
                ),
            )

            content_str = response.choices[0].message.content or "{}"
            parsed = _validate_tactical_output(_safe_parse_json(content_str))
            if parsed is None:
                logger.warning("Groq devolviÃ³ JSON fuera del contrato TacticalAnalysisOutput")
                return None
            tokens = response.usage.total_tokens if response.usage else 0

            logger.info("Groq generó análisis (%d tokens)", tokens)
            return LLMCascadeResult(
                content=parsed,
                model_used=self.GROQ_MODEL,
                tokens_used=tokens,
                provider="groq",
            )

        except Exception as e:
            logger.warning("Groq error: %s", str(e)[:120])
            return None

    async def _try_gemini(self, system_prompt: str, user_prompt: str) -> LLMCascadeResult | None:
        if self._gemini_model is None:
            return None
        try:
            loop = asyncio.get_event_loop()
            full_prompt = f"{system_prompt}\n\n{user_prompt}"

            response = await loop.run_in_executor(
                None,
                lambda: self._gemini_model.models.generate_content(
                    model=self.GEMINI_MODEL,
                    contents=full_prompt,
                    config={
                        "max_output_tokens": self.MAX_TOKENS,
                        "temperature": 0.3,
                    },
                ),
            )

            content_str = response.text or "{}"
            parsed = _validate_tactical_output(_safe_parse_json(content_str))
            if parsed is None:
                logger.warning("Gemini devolviÃ³ JSON fuera del contrato TacticalAnalysisOutput")
                return None
            tokens = response.usage_metadata.total_token_count if hasattr(response, "usage_metadata") and response.usage_metadata else 0

            logger.info("Gemini generó análisis (%d tokens)", tokens)
            return LLMCascadeResult(
                content=parsed,
                model_used=self.GEMINI_MODEL,
                tokens_used=tokens,
                provider="gemini",
            )

        except Exception as e:
            logger.warning("Gemini error: %s", str(e)[:120])
            return None


def _safe_parse_json(raw: str) -> dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("```json"):
        raw = raw[7:]
    if raw.startswith("```"):
        raw = raw[3:]
    if raw.endswith("```"):
        raw = raw[:-3]
    try:
        return json.loads(raw.strip())
    except json.JSONDecodeError:
        try:
            raw_clean = raw.strip()
            start = raw_clean.find("{")
            end = raw_clean.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(raw_clean[start:end])
        except json.JSONDecodeError:
            pass
        return {}


def _validate_tactical_output(payload: dict[str, Any]) -> dict[str, Any] | None:
    try:
        return TacticalAnalysisOutput.model_validate(payload).model_dump()
    except Exception as exc:
        logger.warning("Respuesta tÃ¡ctica invÃ¡lida: %s", str(exc)[:160])
        return None
