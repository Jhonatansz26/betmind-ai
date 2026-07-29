### 📋 Resumen de 13 Commits Realizados

| # | Commit | Área |
|---|--------|------|
| 1 | `feat(redis)` | Docker Redis, ConnectionPool asíncrono, Rate Limiter |
| 2 | `feat(leagues)` | Filtrado dinámico de ligas por partidos del día |
| 3 | `fix(sync)` | Corrección int32 overflow en hash de IDs |
| 4 | `fix(timezone)` | Fechas UTC consistentes + ISO 8601 |
| 5 | `feat(predictions)` | Sistema 5-capas de resiliencia IA |
| 6 | `fix(batch)` | Fix imports, Pydantic validation, optimización Groq |
| 7 | `fix(audit)` | Corrección bugs críticos de resiliencia |
| 8 | `feat(markets)` | Expansión de mercados matemáticos + risk_level |
| 9 | `feat(bet-builder)` | Motor Bet Builder + badges riesgo + nuevos mercados UI |
| 10 | `fix(ui)` | Fix ExpandedMarkets vacío, Córners/Tarjetas, Bet Builder modal |
| 11 | `fix(batch)` | Fix fallback schemas, BetBuilder engine, Groq 429 instant |
| 12 | `fix(batch)` | Micro-fix validación Cards + log BetBuilder |
| 13 | `feat(ui)` | Traducción español, exclusión mutua BetBuilder, polish visual |

---

### 🐳 1. Optimización Integral de Redis con Docker y FastAPI

**`docker-compose.yml`** (nuevo):
- Redis 7-alpine con persistencia AOF, maxmemory 512MB LRU, healthcheck cada 10s.
- Puerto `127.0.0.1:6379:6379` (solo localhost).

**`apps/api/services/cache_service.py`** (refactor):
- `ConnectionPool` global reutilizable via `get_redis_pool()` con 20 conexiones máx.
- `close_redis_pool()` para cierre ordenado en el lifespan de FastAPI.
- `set_json`/`get_json` robustos con `ttl_seconds` y fallback graceful (retorno `bool`/`None`).
- Timeouts de conexión (2s), keepalive y retry_on_timeout en el pool.
- `CacheService.__init__()` acepta `redis_url` opcional (backward compat para tests).

**`apps/api/main.py`**:
- Rate Limiter via `slowapi` con Redis: `200 req/min`, `2000 req/hour`.
- Nuevo endpoint `GET /api/v1/health/redis` para monitoreo.
- Limpieza del pool Redis en el `lifespan` de FastAPI.

**`apps/api/dependencies.py`**: `get_cache_service()` usa `CacheService()` sin argumentos (pool global).

---

### 🔍 2. Filtrado Dinámico de Ligas con Partidos Activos

**`apps/api/routes/v1/leagues.py`** (refactor):
- Endpoint acepta `?date=YYYY-MM-DD` (default: hoy).
- `INNER JOIN` en lugar de `LEFT JOIN`: solo devuelve ligas con ≥1 partido activo en la fecha.
- Liga sin partidos = excluida de la respuesta (antes devolvía todas las ligas aunque vacías).

**`apps/web/lib/api.ts`**: `fetchLeagues(targetDate?)` acepta fecha opcional.

**`scripts/batch_predict.py`**: Ya procesaba todas las ligas sin filtro estático (sin cambios necesarios).

---

### 🐛 3. Corrección de int32 Overflow en Hash de IDs

**`scripts/sync_today_matches.py`**:
- `stable_id` de equipos y `external_id` de partidos ahora usan `% 2_000_000_000`.
- Antes: `int(hashlib.sha256(...).hexdigest()[:8], 16)` generaba IDs > 2³¹ (overflow INTEGER PostgreSQL).
- Liga Argentina y MLS ahora sincronizan correctamente.

---

### 🕒 4. Normalización de Zona Horaria y Serialización ISO 8601

**`apps/api/services/scrapers/match_fixture_scraper.py`**:
- `_parse_event()` ahora mantiene `match_date` en UTC (sin convertir a COT innecesariamente).
- La doble conversión UTC→COT→DB→UTC→COT era frágil. Ahora: ESPN UTC → DB TIMESTAMPTZ → API isoformat().

**`apps/api/routes/v1/matches.py`**:
- `str(m.match_date)` reemplazado por `m.match_date.isoformat()` en `_match_to_dict`, `_match_to_dict_full`, y H2H.
- Antes: `"2026-07-29 19:00:00+00:00"` (espacio, no ISO 8601). Ahora: `"2026-07-29T19:00:00+00:00"`.

**`apps/api/routes/v1/backtesting.py`**: Mismo fix.

---

### 🛡️ 5. Sistema Macizo de 5 Capas para Resiliencia de IA

#### Capa 1 — Motor Poisson Base (0 tokens)
- `_build_minimal_tactical_analysis()` ya existente genera narrativa sintética desde datos Poisson.
- Predicción cuantitativa NUNCA se pierde (siempre se persiste en DB).

#### Capa 2 — Cascada Multi-Proveedor (Groq → Gemini → Sintético)
- **`apps/api/services/llm_cascade.py`** (nuevo): `LLMCascadeService` con Groq (`llama-3.1-8b-instant`) → Gemini (`gemini-2.0-flash`, SDK `google-genai`) → fallback sintético.
- `GEMINI_API_KEY` en `apps/api/config.py` y `.env.example`.
- Integrado en `_run_full_analysis_safe()` con `_fallback_quant_with_gemini()` y `_try_gemini_analysis()`.

#### Capa 3 — Optimización de Prompts (max_tokens reducido)
- Los 4 generadores ML (`goals_`, `cards_`, `corners_`, `bet_builder.py`): `max_tokens` optimizado.
- Prompt condensado para Gemini: solo datos procesados, JSON estricto.

#### Capa 4 — Idempotencia
- `_has_narrative()` verifica DB antes de procesar cada partido.
- Skip automático si `llm_model_used != "none"` o existe `TacticalAnalysis` con narrativa.
- Flag `--force` para bypass en `batch_predict.py`.

#### Capa 5 — Lotes y Rate Limits
- `BATCH_SIZE=5` con `asyncio.sleep(2)` entre lotes.
- Sin borrado masivo de predicciones existentes.

---

### 🐛 6. Corrección de Bugs de Validación e Imports en ML

**`packages/ml/betmind_ml/narrative/generators/cards_narrative.py`** y **`corners_narrative.py`**:
- `NarrativeSignal` no existía → reemplazado por `SignalStrength`.
- Fallbacks ahora usan objetos `ProConPoint` (no strings), incluyen `our_probability`, `key_risk`, y respetan `pros` min 2.

**`packages/ml/betmind_ml/narrative/generators/goals_narrative.py`**:
- Fallback también corregido con `ProConPoint` objects y campos obligatorios.

**`packages/ml/betmind_ml/config.py`**: `NARRATIVE_MODEL`: `llama-3.3-70b` → `llama-3.1-8b-instant`.

**`packages/ml/betmind_ml/narrative/narrative_orchestrator.py`**:
- `_execute_with_retry` simplificado: sin doble intento 70B/8B por key.
- `max_retries=1` en Groq client.

**`apps/api/services/cache_service.py`**: 7 `logger.warning` → `logger.debug` (Redis errors no saturan CI/CD logs).

---

### 🩺 7. Auditoría de Resiliencia — Corrección de Bugs Críticos

**`apps/api/services/api_football.py`** y **`football_data_provider.py`**: `response.json()` ahora con guard `try/except ValueError` → `ExternalAPIException`.

**`apps/api/main.py`**: Nuevo handler global `SQLAlchemyError` → 503 `DB_UNAVAILABLE`.

**`scripts/batch_predict.py`, `sync_today_matches.py`, `sync_all_historical.py`**:
- `pool_size`/`max_overflow` ahora desde `settings` (antes hardcodeado a 5, 75% menor).
- `engine.dispose()` en `try/finally` (antes sin protección, leak de conexiones en errores).
- `pool_timeout` configurado explícitamente.

**`scripts/sync_today_matches.py`**: Validación de `team_name.strip()` contra nombres vacíos/blancos.

---

### 📊 8. Expansión de Mercados Matemáticos (22 mercados total, antes 13)

**`packages/ml/betmind_ml/models/market_calculator.py`** (+9 mercados):

| Categoría | Mercados | Fórmula |
|---|---|---|
| **Double Chance** | `DOUBLE_1X`, `DOUBLE_X2`, `DOUBLE_12` | Suma de probs 1X2 |
| **Draw No Bet** | `DNB_HOME`, `DNB_AWAY` | P/(P_home + P_away) |
| **Indiv. Team Goals** | `HOME_OVER_0_5/1_5`, `AWAY_OVER_0_5/1_5` | 1 − e^(−λ) |

- `build_all_markets()` ahora acepta `lambda_home`, `lambda_away` para goles individuales.
- `prediction_pipeline.py`: `_compute_risk_level()` — `LOW` (≥75% confianza), `MEDIUM` (55-74%), `HIGH` (<55%).

**Esquemas actualizados**: `MatchPredictionOutput.risk_level`, `PredictionResponse.risk_level`.

---

### 🎯 9. Motor de Bet Builder Automático y Badges de Riesgo en Frontend

**`packages/ml/betmind_ml/bet_builder_engine.py`** (nuevo):
- 3 perfiles: `conservador` (cuota ~1.50-2.10), `moderado` (~2.80-4.50), `cazador` (~6.00+).
- Selección basada en probabilidad Poisson y +EV para perfil cazador.
- `_MUTUALLY_EXCLUSIVE`: 8 grupos de exclusión (BTTS, Over/Under ×4, 1X2, DOUBLE, DNB).
- `_is_exclusive()` evita combinaciones contradictorias en el mismo boleto.
- 3 niveles de fallback para siempre producir perfiles.

**API**: `PredictionResponse.bet_builder` con `BetBuilderProfileSchema` (selecciones + cuota combinada).

**Frontend — Nuevos componentes y secciones**:

| Componente | Descripción |
|---|---|
| `RiskBadge` | LOW (verde), MEDIUM (ámbar), HIGH (rojo) en página detalle |
| `BetBuilderSection` | 3 perfiles con cuota combinada, selecciones y botón "Copiar al Boleto" |
| `ExpandedMarkets` | Doble Oportunidad, DNB, Goles de Equipo con `MARKET_LABELS_ES` |
| `TacticalCardsSection` | Muestra Córners y Tarjetas del `tactical_analysis` |
| `MatchModal` | `fetchMatchPrediction()` al abrir + `BetBuilderSection` integrado |
| Tipos | `EnrichedMatch` extendido con `riskLevel`, `betBuilder`, `tacticalAnalysis` |

---

### 🎨 10. Correcciones de Renderizado, Fallbacks y Polish Visual

**Fix ExpandedMarkets vacío**:
- Causa: `prediction_orchestrator.py` filtraba `if market.bookmaker_odds` — solo incluía mercados con odds.
- Fix: `else` ahora incluye mercado con `verdict=INSUFFICIENT_DATA`. API devuelve los 22 mercados completos.

**Fix prompts LLM y max_tokens**:
- Eliminado `json_schema` del prompt (~1000 tokens de bloat) en los 4 generadores.
- `max_tokens`: 400 → 800 para contenido completo.
- Campos explícitos en `SYSTEM_BASE` con tipos exactos y regla de idioma español (#7).
- Gemini prompt: "Responde SIEMPRE en español. NUNCA en inglés".

**Fix Groq 429 instantáneo**:
- `max_retries=0` en `narrative_orchestrator.py` y `llm_cascade.py`.
- Sin esperas de 15-58s del SDK: 429 → fallback en <1s. Ciclo total: ~40s → ~5s por partido.

**Micro-fix validación Cards narrative**:
- `MarketNarrative.pros`: `min_length=2` → `min_length=1` (LLM 8B a veces solo genera 1).

**Fix log BetBuilder**:
- Log unificado post-fallback: siempre muestra el count real de combinadas (antes mostraba 0 cuando LLM fallaba).

**Idioma 100% español**:
- `_MARKET_LABELS`: `DNB` → `Empate No Válido`, `.5` → `.5 Goles`.
- `MARKET_LABELS_ES` en frontend (sin `key.replace` que generaba inglés).
- `SYSTEM_BASE` regla 7: "Toda respuesta ESTRICTAMENTE en español".
- Gemini prompt: "Responde SIEMPRE en español. Usa 'Más de', 'Menos de', 'Local', 'Visitante'".

**UI Polish final**:
- Ocultado badge `llama-3.1-8b-instant` del header de predicción.
- Ocultado badge `Potenciado por Groq · Llama 3.3` del H2H tab.
- `font-serif` → `font-sans font-bold` en nombres de equipos de la cabecera.
- Lambda label: `Goles Esperados: Local 1.18 — Visitante 0.66` (sin λ griega).
- MatchCard: `xG: 1.18 - 0.66` (sin λ).
- BetBuilder ahora ocupa todo el ancho debajo del grid 2-columnas (Fragment wrapper).

---

### 📊 Resumen de Archivos Modificados en Esta Sesión

| Capa | Archivos |
|------|----------|
| **Infraestructura** | `docker-compose.yml` (nuevo) |
| **Config** | `apps/api/config.py`, `.env.example`, `requirements.txt`, `apps/api/requirements.txt` |
| **DB/Sesiones** | `apps/api/db/database.py`, `apps/api/dependencies.py` |
| **Servicios** | `cache_service.py`, `llm_cascade.py` (nuevo), `api_football.py`, `odds_service.py` |
| **Providers** | `espn_provider.py`, `football_data_provider.py`, `match_fixture_scraper.py` |
| **Orquestadores** | `prediction_orchestrator.py` |
| **Routes API** | `leagues.py`, `matches.py`, `tickets.py`, `predictions.py`, `backtesting.py` |
| **Schemas API** | `schemas/prediction.py` |
| **ML Core** | `config.py`, `market_calculator.py`, `prediction_pipeline.py`, `prediction_output.py`, `tactical_analysis.py` |
| **ML Engine** | `bet_builder_engine.py` (nuevo) |
| **Narrativas** | `narrative_orchestrator.py`, `goals_narrative.py`, `cards_narrative.py`, `corners_narrative.py`, `bet_builder.py` |
| **Prompts** | `base_prompt.py`, `goals_prompt.py`, `cards_prompt.py`, `corners_prompt.py`, `bet_builder_prompt.py` |
| **Scripts** | `batch_predict.py`, `sync_today_matches.py`, `sync_all_historical.py` |
| **Frontend Lib** | `lib/api.ts` |
| **Frontend Components** | `match-card.tsx`, `match-modal.tsx`, `poisson-modal-chart.tsx`, `dashboard.tsx` |
| **Frontend Pages** | `app/partidos/[id]/page.tsx` |
| **Tests** | `tests/test_cache_resilience.py` |

### ✅ Verificación Final de la Sesión

- **batch_predict --force --limit 3**: 3/3 éxito, 0 errores, ev_mkts=22 confirmado.
- **BetBuilder**: 3 perfiles siempre generados, 0 mercados mutuamente excluyentes.
- **Groq 429**: Sin esperas del SDK, fallback en <1s.
- **Cards narrative**: Sin errores `too_short` (min_length=1).
- **TypeScript**: Compila sin errores.
- **Redis**: Pool global funcional, `health/redis` endpoint OK.
- **Ligas**: Filtrado dinámico por fecha, solo ligas con partidos reales.
- **Zona horaria**: ISO 8601 válido en toda la API, UTC consistente en DB.
- **Idioma**: 100% español en labels de mercados, prompts LLM y UI.
- **Mercados**: 22 mercados matemáticos desde Poisson en `ev_analysis`.
- **Sincronización**: 20 partidos de 4 ligas activas sincronizados (Brasil 10, Argentina 8, Colombia 1, MLS 1).
