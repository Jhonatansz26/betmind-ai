# 04 — Historial de Auditorías y Migraciones de BetMind AI

> Bitácora técnica de la evolución del esquema de base de datos y de los fixes críticos de integridad aplicados al código fuente. Fuentes: `apps/api/migrations/*.sql`, `PROJECT_LOG.md`, `apps/api/models/*.py`.

---

## 1. Historial de Migraciones SQL

La carpeta `apps/api/migrations/` conserva las migraciones **004 → 012**. Las migraciones **001–003** (esquema inicial: `teams`, `leagues`, `matches`, `predictions`, `users`) se crearon en la Fase 0 del proyecto (ver PROJECT_LOG §Fase 0: "DB status: 200 OK … 5 tablas creadas (`teams`, `leagues`, `matches`, `predictions`, `users`)") y su evolución está reflejada en los archivos ORM; el repositorio versiona a partir de 004. `Base.metadata.create_all` en `apps/api/db/database.py` complementa la creación de tablas al arranque.

### Registro completo

| Migración | Archivo | Contenido |
|---|---|---|
| 001–003 | (esquema inicial, Fase 0) | Tablas base `teams`, `leagues`, `matches`, `predictions`, `users` (documentado en PROJECT_LOG §Fase 0) |
| 004 | `004_create_tactical_analyses.sql` | Tabla `tactical_analyses` (Fase 4 / Cerebro Táctico): `match_id` UNIQUE FK→`matches(id)` ON DELETE CASCADE, `model_version` (`narrative_v1.0`), `goals_narrative`, `cards_narrative`, `corners_narrative`, `player_props_narratives`, `bet_builder_suggestions` (JSONB), `overall_confidence`, `match_preview_headline`, `llm_model_used`, `generation_tokens_used`, `data_completeness_score`. **RLS habilitado** + política `Allow public read access to tactical_analyses`; índices (`match_id`, `created_at DESC`, `overall_confidence DESC`); trigger `trigger_tactical_analyses_updated_at` para `updated_at`; COMMENTs de documentación |
| 005 | `005_create_bookmaker_odds.sql` | Tabla `bookmaker_odds`: `id BIGSERIAL`, `match_id` FK, `market_name VARCHAR(50)`, `bookmaker_name` default `'api_football'`, `odds_value DOUBLE PRECISION`, `external_fixture_id BIGINT`, `fetched_at`, `created_at`, `updated_at`; **UNIQUE `(match_id, market_name, bookmaker_name)`**; índices `match_id`, `fetched_at`; **RLS** + política `Allow public read access on bookmaker_odds` |
| 006 | `006_expand_predictions_table.sql` | Expande `predictions` con el output del motor cuantitativo: `lambda_home`, `lambda_away`, `home_attack_index`, `away_attack_index`, `home_defense_index`, `away_defense_index` (DOUBLE PRECISION) y `markets_json TEXT`; índice compuesto `idx_predictions_match_created (match_id, created_at DESC)` para LEFT JOIN desde `matches`; COMMENTs |
| 007 | `007_add_match_statistics_columns.sql` | Columnas de estadísticas en `matches`: `home_corners`, `away_corners` (INTEGER), `home_yellows`, `away_yellows`, `home_reds`, `away_reds`, `home_fouls`, `away_fouls`, `home_shots_on_target`, `away_shots_on_target` (FLOAT) — habilitan mercados de córneres, tarjetas y remates |
| 008 | `008_create_sofascore_statistics.sql` | `match_events` (`event_type CHECK IN ('goal','card','sub')`, `minute`, `added_time`, `is_home`, `player_name`, UNIQUE compuesto), `match_advanced_stats` (`match_id` PK FK, `home_xg`, `away_xg`, `home_shots`, …, `home_fouls`), `referee_profiles` (`referee_id BIGINT PK`, `name`, `matches_count`, `yellow_cards`, `red_cards`, promedios); añade `matches.sofascore_event_id BIGINT UNIQUE` y `matches.referee_id BIGINT REFERENCES referee_profiles(referee_id)`; índices (`matches_referee_id`, `matches_sofascore_event_id`, `match_events_match_id`) |
| 009 | `009_enable_rls_statistics.sql` | **RLS** en `match_events`, `match_advanced_stats`, `referee_profiles`: políticas `*_public_read` para `anon, authenticated` (SELECT USING true) y `*_service_role_all` para `service_role` (ALL WITH CHECK true) — lecturas públicas, escritura solo server-side |
| 010 | `010_enable_rls_global.sql` | **RLS global**: `matches`, `predictions`, `teams`, `leagues`, `users` → políticas `*_public_read` (SELECT para anon/authenticated) y `*_service_role_all` (ALL para service_role). **Nota de seguridad:** `users` contiene `hashed_password` y deliberadamente **no** tiene política pública de SELECT |
| 011 | `011_add_match_type.sql` | `matches.match_type VARCHAR(20) NOT NULL DEFAULT 'LEAGUE'`; backfill de `KNOCKOUT_CUP` para copas: `{241 Copa Colombia, 130 Copa de la Liga Profesional, 73 Copa do Brasil, 254 US Open Cup, 13 Libertadores, 11 Sudamericana, 2 UCL, 3 UEL, 848 UECL}`; índice `idx_matches_match_type` |
| 012 | `012_create_saved_tickets.sql` | **Tabla `saved_tickets`** (persistencia de boletos para tracking): `id SERIAL PRIMARY KEY`, **`ticket_data JSONB NOT NULL`**, `status VARCHAR(10) NOT NULL DEFAULT 'PENDING'` con **`CHECK (status IN ('PENDING','WON','LOST','VOID'))`**, `total_odds DOUBLE PRECISION`, `total_ev DOUBLE PRECISION`, `created_at TIMESTAMPTZ DEFAULT NOW()`; **índice `idx_saved_tickets_created_at ON saved_tickets (created_at DESC)`** (consulta del historial). **RLS activado en Supabase** vía política global de migración 010 (la tabla hereda el modelo `saved_tickets` público-lectura + service_role escritura; el ORM `SavedTicket` está registrado en `init_db()`) |

### Espejo ORM de `saved_tickets` (`apps/api/models/ticket.py`)

```python
class SavedTicket(Base):
    __tablename__ = "saved_tickets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    ticket_data: Mapped[dict] = mapped_column(JSON().with_variant(JSONB(), "postgresql"), nullable=False)
    status: Mapped[str] = mapped_column(String(10), default="PENDING", server_default="PENDING")
    total_odds: Mapped[float] = mapped_column(Float, nullable=False)
    total_ev: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
```

### Capa de acceso (repo + API)

- `TicketRepository`: `create()`, `list_history(limit=100)` (orden `created_at DESC`), `get_by_id()`, `update_status()`.
- Endpoints: `POST /api/v1/tickets/save` (201), `GET /api/v1/tickets/history`, `PATCH /api/v1/tickets/{id}/status` (404 si no existe). Schemas en `apps/api/schemas/ticket.py`: `SavedTicketStatus` (`PENDING/WON/LOST/VOID`), `SaveTicketRequest` (`ticket_data: dict`, `total_odds > 1.0`, `total_ev`), `SavedTicketResponse` (`from_attributes=True`).
- El generador `POST /api/v1/tickets/generate` NO inventa datos: construye legs desde `predictions.markets_json` + cuotas reales de `bookmaker_odds`, y clasifica `NO_ODDS_AVAILABLE` cuando no hay cuota (ver doc 02).

---

## 2. Registro de Fixes Críticos Aplicados

Fuente: PROJECT_LOG §"🔴 Fixes Críticos de Backend: EV Fantasma, Mapeo de Ligas ML y Configuración de Entornos" + pasos posteriores de resiliencia HTTP y persistencia.

### 2.1 Eliminación total de cuotas sintéticas y EV falso (5%/8%)

**Problema:** el sistema fabricaba cuotas cuando no existían (ej. `bm_odds = 1.0 / (prob / 1.05)` con overround genérico del 5%, o `_derive_markets_from_probabilities()` con overround sintético del **8%**), generando tickets con "+EV fantasma" que no era real.

**Fixes aplicados (en código actual):**

1. `apps/api/engine/ticket_builder.py` — eliminada la síntesis de cuotas. Un mercado **solo es candidato a ticket si** `bookmaker_odds > 1.0` **y** `implied_probability is not None` **y** `expected_value is not None`:
   ```python
   if bm_odds <= 1.0 or implied is None or ev is None:
       continue   # "A model probability is not a bookmaker price."
   ```
2. `apps/api/routes/v1/tickets.py` — eliminada `_derive_markets_from_probabilities()`. Los mercados sin cuotas reales se serializan con `verdict: "NO_ODDS_AVAILABLE"`, `bookmaker_odds: null`, sin `expected_value`. `total_ev_opportunities` solo cuenta EV numérico real (`expected_value > 0.05`).
3. **Centralización del cálculo EV:** `calculate_ev_metrics()` en `packages/ml/betmind_ml/ev/ev_calculator.py` (probabilidad implícita **desmarquinizada** + edge + EV), importada por el orquestador y la ruta de tickets — elimina reimplementaciones locales de la fórmula.
4. **Nuevo estado API:** `Verdict.NO_ODDS_AVAILABLE = "NO_ODDS_AVAILABLE"` en `apps/api/schemas/prediction.py`.
5. `_build_response()` del orquestador (`prediction_orchestrator.py:756`): mercado sin cuota → `EVAnalysis(..., bookmaker_odds=None, expected_value=None, kelly_stake=None, verdict=NO_ODDS_AVAILABLE)`. Con cuota: verdict `POSITIVE_VALUE` solo si `EV > 0.05` **y** `odds >= 1.20` (cuotas < 1.20 → `NO_VALUE`).
6. `estimate_lambdas_from_odds()` marcado `DeprecationWarning` (predicción tautológica): el pipeline retorna `INSUFFICIENT` cuando los datos históricos no son confiables.
7. Filtros anti-datos-basura en cuotas reales (`odds_service.py`): bloqueo de Doble Oportunidad/DNB/Handicap por nombre y por valor (`1x/x2/12`), y validación estricta `1X2_DRAW >= 2.10`.

**Verificación registrada:** dos partidos sin odds reales no generan tickets ni badges EV+ falsos; suite backend `118 passed`.

### 2.2 Mapeo completo de las 26 ligas en el orquestador ML

**Problema:** `_get_league_key()` solo cubría 3 ligas (39, 140, 239); el resto caía en `"default"` con parámetros genéricos (ventaja de local, líneas de tarjetas/córneres, baselines de calibración).

**Fix aplicado:** `apps/api/orchestrators/prediction_orchestrator.py:30`:

```python
LEAGUE_EXTERNAL_ID_TO_KEY = {
    info["api_football_id"]: league_key
    for league_key, info in FEATURED_LEAGUES.items()
}
```

- Diccionario **derivado automáticamente de `FEATURED_LEAGUES`** (fuente única de verdad en `apps/api/config.py`).
- Las **26 ligas** mapean a su clave Poisson correcta (`premier_league`, `liga_betplay`, `copa_colombia`, `libertadores`, `uecl`, …); ninguna cae en el rango genérico `"default"`.
- Espejo en `MatchRepository.LEAGUE_KEY_TO_EXTERNAL_ID` (filtros, backtesting) y `KNOCKOUT_CUP_LEAGUE_IDS` (tipo de partido) — mapeos idénticos de 26 claves (ver doc 02 §1).

### 2.3 Seguridad: guard de `SECRET_KEY` y CORS por `ALLOWED_ORIGINS`

1. **Bloqueo de arranque en producción** (`apps/api/config.py:130`):
   ```python
   if not self.DEBUG and self.SECRET_KEY == "change-me-in-production":
       raise ValueError("SECRET_KEY must be changed when DEBUG=False; refusing to start in production")
   ```
   Con `DEBUG=False` (como en el workflow de GitHub Actions), una `SECRET_KEY` por defecto impide el arranque del servicio.
2. **CORS configurable** (`apps/api/main.py:57`): `CORSMiddleware(allow_origins=settings.ALLOWED_ORIGINS, allow_credentials=True, ...)` — se eliminó el hardcode de `localhost:3000`. `ALLOWED_ORIGINS` soporta **JSON** o **lista separada por comas** (validator `normalize_allowed_origins`), default `["http://localhost:3000", "http://127.0.0.1:3000"]`.
3. Complementos de seguridad: políticas RLS en Supabase (migraciones 009–010; `users` sin SELECT público por contener `hashed_password`), rate limiting slowapi (200/min, 2000/h) respaldado en Redis, y `require_admin_key` (header `X-Admin-Key` vs `ADMIN_API_KEY`) para `/backtesting/*` (503 si no está configurada, 403 si es inválida).

### 2.4 Persistencia remota de tickets en PostgreSQL con fallback local

1. **Backend:** tabla `saved_tickets` (migración 012, JSONB + índice por fecha + RLS), modelo `SavedTicket`, `TicketRepository` y endpoints `/tickets/save|history|{id}/status`.
2. **Frontend (`apps/web/lib/api.ts`):** `apiFetch<T>()` como frontera única — **timeout de 12 s** (`AbortController`), respuestas estructuradas `ApiResult<T> = {ok:true,data} | {ok:false,error:{code,message}}` con códigos `NETWORK_ERROR`/`REQUEST_TIMEOUT`/`HTTP_<status>` y mensajes seguros en español. Clientes de tickets: `saveTicket()`, `fetchTicketHistory()`, `updateTicketStatus()`.
3. **Fallback local (`tracking-panel.tsx`):** `addToTracking()` primero intenta la API; solo si falla escribe en `localStorage` (`betmind_tracked_tickets`, máx. 10 entradas, `remote: false`). El panel carga historial remoto como fuente primaria y cae a local cuando la API no responde; los cambios de estado en entradas remotas se reenvían por `PATCH` y si la red falla se persisten localmente.
4. **Manejo defensivo adicional:** `fetchMatchPrediction()` degrada con elegancia (si la predicción falla, devuelve el match base con probabilidades en cero); deduplicación de partidos en cliente (`dedupeMatches`, ventana 2h, Jaccard ≥ 0.85) para evitar duplicados cross-proveedor; caché Redis con TTLs (predicciones 6h, tickets 30 min, vacío 30 s).

---

## 3. Evidencia de verificación (auditoría)

| Auditoría | Resultado registrado |
|---|---|
| Suite de tests backend | `118 passed` (post-fixes críticos) |
| Frontend TypeScript | `npm run build` / `npx tsc --noEmit` 0 errores (Next.js 16.2.6) |
| Tests ML (Fase 3 + Fase 4) | `8 passed` (`test_poisson_engine.py`, `test_full_analysis.py`) |
| Sincronización Supabase (Fase 1.7) | Conexión OK con `postgresql+asyncpg://` + PgBouncer (`statement_cache_size=0`); integridad referencial verificada |
| Cobertura E2E visual | Capturas Puppeteer de cartelera con banners EV+, jerarquía de cuotas y filtros |
