# 01 — Arquitectura y Stack Técnico de BetMind AI

> Documento maestro generado a partir del código fuente real del monorepo `C:\betmind-ai`.
> Monorepo: `apps/api` (Backend FastAPI) · `apps/web` (Frontend Next.js) · `packages/ml` (Paquete ML) · `scripts/` (automatizaciones) · `.github/workflows/` (CI/CD).

---

## 1. Backend & Base de Datos

### 1.1 Stack

| Componente | Tecnología | Evidencia en código |
|---|---|---|
| Framework HTTP | **FastAPI** (`fastapi>=0.110.0`) con Uvicorn | `apps/api/main.py`, `requirements.txt` |
| Python | **3.11** (fijado por GitHub Actions) | `.github/workflows/daily_predictions.yml` → `actions/setup-python@v5` con `python-version: '3.11'` |
| ORM | **SQLAlchemy 2.0 Async** (`sqlalchemy>=2.0.25`) | `apps/api/db/database.py`, `apps/api/models/` |
| Drivers DB | **asyncpg** (PostgreSQL en prod) + **aiosqlite** (desarrollo local) | `requirements.txt`; `database.py` detecta `sqlite` vs pool para Postgres |
| Base de datos | **PostgreSQL vía Supabase** con **RLS activado** | `apps/api/migrations/009..010` (políticas RLS), `.env.example` |
| Caché | **Redis (Upstash)** con `redis.asyncio` | `apps/api/services/cache_service.py`; `REDIS_URL` en config |
| Rate limiting | **slowapi** (`Limiter` con storage en Redis, 200 req/min, 2000 req/h) | `apps/api/main.py:32-36` |
| Validación | **Pydantic v2 + pydantic-settings** (SDD: Schema-Driven Development) | `apps/api/schemas/`, `apps/api/config.py` |
| Infra local | `docker-compose.yml` con `redis:7-alpine` (512 MB, allkeys-lru, AOF) | `docker-compose.yml` |

### 1.2 Configuración (`apps/api/config.py`)

- Clase `Settings(BaseSettings)` con `model_config = {env_file_encoding: "utf-8", extra: "ignore", case_sensitive: True}`.
- **Búsqueda de `.env`:** `_find_env_files()` prioriza `apps/api/.env` y luego `betmind-ai/.env` (raíz del monorepo).
- **Normalización de `DATABASE_URL`:** `postgres://` y `postgresql://` se convierten automáticamente a `postgresql+asyncpg://` (validator `normalize_database_url`). `sqlite` se deja intacto.
- **`ALLOWED_ORIGINS`:** lista JSON o CSV (validator `normalize_allowed_origins`), default `["http://localhost:3000", "http://127.0.0.1:3000"]`.
- **Guard de seguridad en arranque:** si `DEBUG=False` y `SECRET_KEY == "change-me-in-production"`, `Settings.__init__` lanza `ValueError` y la app se rehúsa a iniciar en producción.
- Variables: `APP_NAME="BetMind AI"`, `APP_VERSION="0.1.0"`, `DEBUG`, `DATABASE_URL`, `REDIS_URL`, `DB_POOL_SIZE=20`, `DB_MAX_OVERFLOW=10`, `DB_POOL_TIMEOUT=30`, `API_FOOTBALL_KEY`, `FOOTBALL_DATA_KEY`, `GROQ_API_KEY`, `GROQ_API_KEYS` (lista separada por comas, con prioridad sobre la single key en `get_groq_api_keys()`), `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`, `SECRET_KEY`, `ALGORITHM="HS256"`, `ACCESS_TOKEN_EXPIRE_MINUTES=30`, `ADMIN_API_KEY`, `GROQ_TIMEOUT_SECONDS=90.0`, `GROQ_SINGLE_CALL_TIMEOUT=25.0`, `GROQ_NARRATIVE_TIMEOUT=80.0`.

### 1.3 Capa de Datos: Motor Async (`apps/api/db/database.py`)

- `create_async_engine(settings.DATABASE_URL)` con kwargs diferenciados:
  - SQLite → `check_same_thread=False`.
  - PostgreSQL → `pool_size=20`, `max_overflow=10`, `pool_pre_ping=True`, `pool_timeout=30`, y `connect_args` con `statement_cache_size=0` y `prepared_statement_cache_size=0` (requerido para **PgBouncer/Supabase**, documentado en PROJECT_LOG Fase 1.7).
- `async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)`.
- `init_db()` crea las tablas con `Base.metadata.create_all` al arranque (lifespan de FastAPI); `dispose_engine()` al apagar.
- `get_async_session()`: yield de sesión + commit automático + rollback en error.
- `ping_db()`: `SELECT 1` + lista de tablas registradas (endpoint `/api/v1/health/db`).

### 1.4 Modelos ORM (SQLAlchemy, `apps/api/models/`)

| Modelo | Tabla | Campos clave |
|---|---|---|
| `Base` / `TimestampMixin` | — | `DeclarativeBase`; `created_at`, `updated_at` (`onupdate`) |
| `Match` | `matches` | `external_id` (único), `league_id`, `home_team_id`, `away_team_id`, `match_date` (index), `status`, `match_type` (`LEAGUE`/`KNOCKOUT_CUP`), `regulation_time_only`, `home_score`/`away_score`, estadísticas (`home_corners`, `away_yellows`, `home_fouls`, `home_shots_on_target`, etc.), `sofascore_event_id`, `referee_id`, `alternate_external_ids` (JSON de IDs cross-provider). Relaciones: `league`, `home_team`, `away_team` (`lazy="noload"`), `predictions`, `bookmaker_odds`, `events`, `advanced_stats`, `referee` |
| `Prediction` | `predictions` | `match_id` FK indexado, `prediction_type`, `confidence`, `value_score`, `reasoning`, `lambda_home`, `lambda_away`, `home/away_attack_index`, `home/away_defense_index`, `markets_json` (TEXT JSON) |
| `Team` | `teams` | `external_id`, `name`, `logo_url`, `country` |
| `League` | `leagues` | `external_id`, `name`, `country`, `logo_url`, `tier` |
| `User` | `users` | (auth futura; contiene `hashed_password` — sin política pública de SELECT, según migration 010) |
| `BookmakerOdd` | `bookmaker_odds` | `match_id`, `market_name`, `bookmaker_name` (default `api_football`), `odds_value`, `external_fixture_id`, `fetched_at`; UNIQUE `(match_id, market_name, bookmaker_name)` |
| `MatchEvent` | `match_events` | `event_type` (`goal|card|sub`), `minute`, `added_time`, `is_home`, `player_name` |
| `MatchAdvancedStats` | `match_advanced_stats` | `home_xg`, `away_xg`, `home_shots`, `away_shots`, `home_corners`, `home_fouls`, etc. |
| `RefereeProfile` | `referee_profiles` | `referee_id` PK, `name`, `matches_count`, `yellow_cards`, `red_cards`, promedios |
| `SavedTicket` | `saved_tickets` | `id` SERIAL PK, `ticket_data` `JSON().with_variant(JSONB(), "postgresql")`, `status` (`PENDING/WON/LOST/VOID`, default `PENDING`), `total_odds`, `total_ev`, `created_at` (timestamptz) |
| `TacticalAnalysis` | `tactical_analyses` | `match_id` UNIQUE FK, `model_version`, `goals_narrative`, `cards_narrative`, `corners_narrative`, `player_props_narratives`, `bet_builder_suggestions` (JSONB), `overall_confidence`, `match_preview_headline`, `llm_model_used`, `generation_tokens_used`, `data_completeness_score` |

### 1.5 Repositorios (patrón Repository + DI, `apps/api/repositories/`)

- `BaseRepository(Generic[ModelType])` — CRUD genérico: `get_by_id`, `get_all`, `create`, `update`, `delete`.
- `MatchRepository` — núcleo del dominio:
  - `get_by_id` (raise `MatchNotFoundException`), `get_recent_form(team_id, last_n)` (solo `status=FINISHED` + `regulation_time_only=True`), `get_h2h(home, away, last_n=6)`, `get_league_matches(league_id)`, `get_all_finished_matches(league_key, season)` (backtesting), `get_by_external_id`, `upsert_match()` con **deduplicación multi-proveedor de 3 niveles** (external_id → pareja exacta en ventana de 2h → fuzzy por nombres canonicalizados ≥ 0.85 Jaccard), `_record_alternate_external_id`, `get_matches_by_date`, `upsert_prediction`, `match_to_dict()` (formato del pipeline ML).
  - Constantes: `DEDUP_WINDOW_HOURS = 2`, `TEAM_PAIR_SIMILARITY_THRESHOLD = 0.85`, `LEAGUE_KEY_TO_EXTERNAL_ID` (26 ligas).
- `TicketRepository` — `create`, `list_history(limit=100)`, `get_by_id`, `update_status`.
- `LeagueRepository`, `TeamRepository` — upsert de catálogos (`create_or_update`, `_find_by_normalized_name`).
- `TacticalAnalysisRepository` — `upsert` / `get_by_match_id` (cache en DB de 6h).
- `BookmakerOddRepository` — `upsert_odds`, `get_odds_for_match(es)`.

### 1.6 Aplicación FastAPI (`apps/api/main.py`)

- `lifespan`: `init_db()` → yield → `close_redis_pool()` + `dispose_engine()`.
- Middleware CORS desde `settings.ALLOWED_ORIGINS`; rate limiter slowapi montado en `app.state.limiter`.
- Handler de excepciones con `code` estructurado:
  - `MATCH_NOT_FOUND` (404), `PREDICTION_NOT_AVAILABLE` (422), `EXTERNAL_API_ERROR` (503 + `service`), `DB_UNAVAILABLE` (503, SQLAlchemyError), `BETMIND_ERROR` (500), `INTERNAL_ERROR` (500).
- Endpoints de health: `GET /`, `GET /health`, `GET /api/v1/health/db`, `GET /api/v1/health/redis`.

### 1.7 Endpoints del API v1 (rutas en `apps/api/routes/v1/`)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/v1/predictions/{match_id}` | Predicción completa: probabilidades 1X2/O-U, análisis EV por mercado (con Kelly quarter), narrativa táctica, `tactical_analysis` (Fase 4) y `bet_builder`. Query params opcionales de cuotas: `home_win_odds`, `draw_odds`, `away_win_odds`, `over_2_5_odds` (todos `gt=1.0`). Si no se pasan cuotas explícitas, las lee de DB vía `OddsService` |
| GET | `/api/v1/matches/` | Lista partidos con `skip`, `limit`, `date`/`date_filter` (`today`/`tomorrow`/`YYYY-MM-DD`, zona COT), `include_upcoming`, `include_finished`. Incluye `odds` (1X2, over25, btts) y `prediction` (lambda, confidence, value_score) por LEFT JOIN |
| GET | `/api/v1/matches/upcoming/` | Próximos partidos en ventana móvil **-2h/+36h** (límite 10) |
| GET | `/api/v1/matches/{match_id}` | Detalle completo: equipos, liga, odds, `match_events`, `match_advanced_stats`, `referee_profile` |
| GET | `/api/v1/matches/{match_id}/h2h` | Historial H2H (límite 10) + `home_form`/`away_form` (últimos 5 FINISHED) |
| POST | `/api/v1/matches/sync/{league_id}` | Sincroniza liga desde API-Football (`season`, `last_matches=50`); requiere `API_FOOTBALL_KEY` |
| POST | `/api/v1/matches/sync-all` | Sincroniza todas las ligas objetivo de `FEATURED_LEAGUES` |
| POST | `/api/v1/tickets/save` | Persiste snapshot de ticket (201). Body: `{ticket_data, total_odds (>1.0), total_ev}` |
| GET | `/api/v1/tickets/history` | Historial de tickets ordenado por `created_at DESC` |
| PATCH | `/api/v1/tickets/{ticket_id}/status` | Actualiza estado `PENDING/WON/LOST/VOID` (404 si no existe) |
| POST | `/api/v1/tickets/generate` | Genera boletos por modo `edge/value/bold` desde predicciones almacenadas. Query `date_filter` (`today`/`tomorrow`/`all`/`YYYY-MM-DD`); cache Redis 30 min con slug de ventana; `force_refresh` para saltar cache |
| GET | `/api/v1/leagues/` | Ligas con ≥1 partido activo en la fecha (ventana -2h/+36h si no hay fecha) + `active_matches` |
| POST | `/api/v1/backtesting/{league_key}` | Backtest walk-forward de una liga/temporada. Requiere `X-Admin-Key` (`require_admin_key`). Mínimo 30 partidos finalizados |
| POST | `/api/v1/scanner/` | Escáner de oportunidades (stub: retorna lista vacía) |
| POST | `/api/v1/auth/register` | Registro (501 NOT IMPLEMENTED — placeholder para Fase SaaS) |
| POST | `/api/v1/auth/login` | Login (501 NOT IMPLEMENTED) |

---

## 2. Frontend (Next.js)

### 2.1 Stack (`apps/web/package.json`)

- **Next.js 16.2.6** (App Router), **React 19**, **TypeScript 5.7.3**.
- **Tailwind CSS 4.3.3** (`@tailwindcss/postcss`), **shadcn/ui** (`components.json`), `class-variance-authority`, `clsx`, `tailwind-merge`, `tw-animate-css`.
- Iconografía: `lucide-react`; notificaciones: `sonner`; animaciones: `framer-motion`; primitivas: `@base-ui/react`.
- Scripts: `dev`, `build`, `start`, `lint` (eslint).
- Páginas: `app/page.tsx` (dashboard) y `app/partidos/[id]/page.tsx` (detalle de partido).

### 2.2 Cliente HTTP `apps/web/lib/api.ts` — función `apiFetch<T>()`

Frontera HTTP única del frontend (todos los demás módulos la usan):

```ts
const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000'
const API_TIMEOUT_MS = 12_000

export type ApiResult<T> =
  | { ok: true; data: T }
  | { ok: false; error: ApiError }        // { code: string, message: string }
```

- **Timeout de 12 s** mediante `AbortController` + `setTimeout` (limpieza en `finally` con `clearTimeout`).
- **Respuestas estructuradas:** nunca lanza excepciones de red; retorna `ApiResult<T>` con código:
  - `REQUEST_TIMEOUT` (AbortError) → "La solicitud tardó demasiado…"
  - `NETWORK_ERROR` → "No se pudo conectar con BetMind AI…"
  - `HTTP_<status>` → extrae `body.detail ?? body.message ??` mensaje genérico por status.
- **Consumidores:** `saveTicket()`, `fetchTicketHistory()`, `updateTicketStatus()`, `fetchTickets(modes, leagueFilter, dateFilter)` (POST `/api/v1/tickets/generate` con body `{modes: [lowercase], league_filter}`), `fetchMatches(dateFilter)` (GET con `limit=200`, `include_upcoming`, `include_finished`), `fetchLeagues(targetDate)`, `fetchMatchH2H(matchId)`, `fetchMatchPrediction(matchId)` (Promise.all de match + prediction; si la predicción falla retorna base match con probabilidades en cero — degradación elegante).
- **Tipos del contrato backend** en el mismo archivo: `BackendLeg`, `BackendTicket`, `BackendResponse`, `BackendMatch`, `BackendPrediction`, `BackendEVEntry`, `BackendTacticalAnalysis` + mapeadores `mapLeg()`, `mapBackendTicket()`, `mapBackendMatch()`, `mapBackendPrediction()`.
- **Mapeo de estados** `statusMap`: códigos cortos API-Football (`1H`, `2H`, `HT`, `ET`, `BT`, `P`, `NS`, `TBD`, `PST`, `POST`, `FT`, `AET`, `PEN`) y códigos largos → `MatchStatus` (`SCHEDULED | IN_PLAY | PAUSED | FINISHED | UPCOMING | LIVE | FT`).
- **Zona horaria COT:** hora mostrada con `toLocaleTimeString('en-US', { timeZone: 'America/Bogota' })` + sufijo `COT`.
- **Helpers de liga/banderas:** `COUNTRY_ISO`, `isoToFlagEmoji()`, `flagForCountry()` (deprecado → `resolveLeague()`), `formatCompositeLeagueName()` (deprecado), `LEAGUE_ID_MAP: Record<number, string>` (15 IDs externos → slugs: `39→epl`, `140→laliga`, `78→bundesliga`, `135→seriea`, `61→ligue1`, `239→betplay`, `71→brasileirao`, `128→profesional`, `262→ligamx`, `253→mls`, `274→primera_chile`, `275→liga_pro_ecu`, `294→liga_1_peru`, `113→allsvenskan`, `119→superliga_den`, `207→super_league_sui`).
- **Deduplicación de partidos en cliente:** `dedupeMatches()` con `normalizeTeamName()` (NFD, tildes, tokens), `teamNameSimilarity()` (Jaccard), `matchKey()` (liga + nombres normalizados), `matchRichness()` (lambda>0 +4, odds>0 +2, score +1), `sameTwoHourWindow()` (`DEDUP_WINDOW_MS = 2h`), `sameTeamPair()` (≥ 0.85).

### 2.3 Fallback a `localStorage` (persistencia defensiva)

En `apps/web/components/betmind/tracking-panel.tsx`:

- Clave `betmind_tracked_tickets` con lista `TrackedTicket[]` (`id`, `mode`, `combinedOdds`, `confidence`, `legsCount`, `trackedAt`, `status`, `remote?: boolean`).
- `addToTracking(ticket)` es **async**: primero intenta `saveTicket()` vía API; si falla, guarda en `localStorage` (top 10 entradas).
- `TrackingPanel` carga primero `fetchTicketHistory()` (fuente remota primaria); solo si la API falla usa `loadTracked()` local.
- `handleStatusChange` con entradas remotas (`remote && /^\d+$/`) llama `updateTicketStatus()`; si la API falla, escribe al local.
- Ciclo de estados: `PENDING → WON → LOST → VOID` (alineado con el contrato del backend).
- Tipos `SavedTicketStatus = 'PENDING' | 'WON' | 'LOST' | 'VOID'` y `SavedTicketRecord { id, ticket_data, status, total_odds, total_ev, created_at }` en `lib/api.ts`.

### 2.4 Librerías de dominio del frontend

- `lib/betmind.ts` — tipos `Mode` (`EDGE|VALUE|BOLD`), `MatchStatus`, `Impact`, `League`, `TacticalFactor`, `Referee`, `MarketOdds`, `Match` (con `lambdaHome`, `lambdaAway`, `odds: Record<'home'|'draw'|'away'|'over25'|'btts', number>`, `advancedStats`, `refereeProfile`), `TicketLegData`, `Ticket` (con `rationale: string[]`). Matemática Poisson espejo del backend: `poissonPmf()`, `goalDistribution(lambda, buckets=5)`, `buildModel(lambdaHome, lambdaAway)` (grid 9×9, BTTS = `(1-e^-λh)(1-e^-λa)`), `expectedValue()`, `impliedProbability()`, `marketRows()` (verdicts `EV+ | MARGINAL | NO EDGE | AVOID` con umbrales ±0.03), `bestOpportunity()` (edge ≥ 0.03), `MODE_META` (glyphs `⬡◈⬟`, labels `MODO EDGE/VALUE/BOLD`).
- `lib/league-metadata.ts` — fuente única de metadatos: `LEAGUE_METADATA: Record<number, LeagueMeta>` (26 entradas, incluyendo IDs sintéticos 9001–9011 para UEFA/CONMEBOL) y `resolveLeague(externalId, fallbackName?)`.
- `lib/formatMarketName.ts` — humanización de nombres de mercado.

---

## 3. APIs Externas Integradas

### 3.1 API-Football (`apps/api/services/api_football.py`)

- Base URL `https://v3.football.api-sports.io`, header `x-apisports-key`, `httpx.AsyncClient(timeout=30.0)`.
- Métodos: `get_leagues`, `get_target_leagues` (39/140/239), `get_teams_by_league`, `get_fixtures` (league+season, opcional `last`/`status`), `get_recent_finished_matches` (3 intentos de fallback: `status=FT` → sin status → `last=N`; filtra `FT/AET/PEN`), `get_standings`, `get_h2h`, `get_fixtures_by_date_range`, `get_odds_for_fixture` (`/odds?fixture=`), `get_fixtures_by_date`.
- Manejo de errores: 429 → `ExternalAPIException` "Rate limit exceeded", timeouts 30 s, JSON inválido, `data.errors`, y warning si `x-ratelimit-requests-remaining < 10`.
- `parse_fixture_to_match_data()` → formato interno con `regulation_time_only=True` (regla de 90 minutos).
- **Cuotas:** `apps/api/services/odds_service.py` mapea payloads reales de `/odds` a mercados internos:
  - `MARKET_MAP` (Match Winner → `1X2_HOME/DRAW/AWAY`; Both Teams Score → `BTTS_YES/NO`), `OVER_UNDER_VALUE_MAP` (0.5–3.5), `CORNERS_VALUE_MAP` (4.5–13.5, incluye líneas enteras 4–13 de Pinnacle/1xBet), `CARDS_VALUE_MAP` (2.5–7.5), `SHOTS_OT_VALUE_MAP` (4.5–10.5).
  - Filtro anti-Doble Oportunidad/DNB: bloquea bet names que contengan `double/chance/dnb/no bet/handicap` y valores `1x/x2/12`; valida que `1X2_DRAW >= 2.10` (anomalía = DO/DNB disfrazada).
  - **Mejor precio entre todos los bookmakers** por mercado (`max(odds_values)`).
  - `sync_odds_for_matches` con `asyncio.sleep(6)` entre fixtures (respeto de rate limit).

### 3.2 ESPN Scraper (`apps/api/services/scrapers/match_fixture_scraper.py` + `espn_provider.py`)

- `MatchFixtureScraper`: consume **ESPN Scoreboard API pública** (`https://site.api.espn.com/apis/site/v2/sports/soccer/{league_slug}/scoreboard`), sin API key. `ESPN_LEAGUE_SLUGS` cubre 11 ligas (`col.1`, `bra.1`, `arg.1`, `mex.1`, `usa.1`, `chi.1`, `ecu.1`, `per.1`, `swe.1`, `den.1`, `sui.1`). `fetch_all_leagues_fixtures(days_ahead=1)` usado por `scripts/sync_today_matches.py`.
- `EspnProvider(DataProviderPort)`: `ESPN_LEAGUE_SLUGS` por ID externo (UEFA `uefa.champions/europa/europa.conf`, CONMEBOL `conmebol.libertadores/sudamericana`, Big-5, Sudamérica, Norteamérica, Nórdicos) y `ESPN_LEAGUE_NAMES`. Endpoints: `/scoreboard?dates=YYYYMMDD`, `/teams/{teamId}/schedule`, `/standings`.
- Los fixtures de ESPN alimentan el upsert multi-proveedor: si un partido ya existe por pareja de equipos en ventana de 2h, se **consolida** (`alternate_external_ids`) en vez de duplicar.

### 3.3 Groq API (`apps/api/services/llm_cascade.py` + `packages/ml/betmind_ml/config.py`)

- Modelo narrativo: **`llama-3.1-8b-instant`** (`NARRATIVE_MODEL`, `GROQ_MODEL`), `temperature=0.3`, `max_tokens=400`, `response_format={"type": "json_object"}`.
- Multi-key: `get_groq_api_keys()` combina `GROQ_API_KEYS` (coma) + `GROQ_API_KEY` (prioridad single). Timeouts: `GROQ_TIMEOUT_SECONDS=90.0`, `GROQ_SINGLE_CALL_TIMEOUT=25.0`, `GROQ_NARRATIVE_TIMEOUT=80.0`.
- Cliente sincrónico `Groq(api_key, max_retries=0)` ejecutado vía `loop.run_in_executor`.

### 3.4 Gemini API (fallback de cascada)

- `LLMCascadeService` (Capa 2): flujo **Groq → Gemini → síntesis sin LLM (Capa 1)**.
- Modelo **`gemini-2.0-flash`** (`GEMINI_MODEL`) con `google-genai` (`google.genai.Client(api_key=GEMINI_API_KEY)`), `max_output_tokens=400`, `temperature=0.3`.
- El orquestador de predicciones (`prediction_orchestrator.py`) usa la cascada cuando `llm_model_used == "none"` o hay timeout, y si todo falla construye narrativa mínima estadística (`_build_minimal_tactical_analysis` con `llm_model_used="none"`).

---

## 4. CI/CD y Automatizaciones

### 4.1 GitHub Actions — `.github/workflows/daily_predictions.yml`

- **Disparadores:** `schedule` cron `'0 */2 * * *'` (cada 2 horas en UTC) para mantener cálida la ventana móvil **-2h/+36h**; más `workflow_dispatch` manual.
- **Concurrencia:** `group: betmind-data-refresh`, `cancel-in-progress: false`.
- **Permisos:** `contents: read`.
- **Inyección de variables de entorno a nivel de JOB** (visibles en todos los steps):

```yaml
env:
  SECRET_KEY: ${{ secrets.SECRET_KEY }}
  DATABASE_URL: ${{ secrets.DATABASE_URL }}
  API_FOOTBALL_KEY: ${{ secrets.API_FOOTBALL_KEY }}
  REDIS_URL: ${{ secrets.REDIS_URL }}
  GROQ_API_KEYS: ${{ secrets.GROQ_API_KEYS }}
  GROQ_API_KEY: ${{ secrets.GROQ_API_KEY }}
  GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
  DEBUG: "false"
```

- **Pasos:**
  1. `actions/checkout@v4`.
  2. `actions/setup-python@v5` con `python-version: '3.11'` y `cache: 'pip'`.
  3. Instalación: `pip install -r requirements.txt` + `pip install -e packages/ml` + `pip install -r apps/api/requirements.txt`.
  4. `python scripts/sync_today_matches.py` — sincroniza partidos y cuotas de la ventana móvil (ESPN Scoreboard para fixtures + API-Football para cuotas y marcadores; `FEATURED_LEAGUES` completo, `KNOCKOUT_CUP_LEAGUE_IDS` para `match_type`).
  5. `python scripts/batch_predict.py --mode full --limit 150` — predicciones batch con las 6 capas de resiliencia.

### 4.2 Scripts de automatización (`scripts/`)

- **`batch_predict.py`** — 6 capas de resiliencia:
  - Capa 1: motor Poisson (nunca depende del LLM). Capa 2: cascada Groq → Gemini → sintético. Capa 3: prompts ≤ 400 tokens JSON estricto. Capa 4: idempotencia (`_has_narrative`: salta si ya existe `TacticalAnalysis` con `llm_model_used != "none"` y `goals_narrative` no nulo, o una `Prediction`). Capa 5: lotes de **5** con pausa de **2 s** (`BATCH_SIZE=5`, `BATCH_DELAY_SECONDS=2`). Capa 6 (defensiva): `_deduped_matches` — nunca procesa dos variantes del mismo encuentro (ventana ±2h + similitud de nombres ≥ 0.85), conservando el registro más rico (con cuotas > id menor).
  - Query: `Match.status IN (UPCOMING_MATCH_STATUSES)` y `match_date` en `[now-2h, now+36h]`, orden asc, `limit`/`skip`.
  - Args: `--limit`, `--skip`, `--mode quant|full`, `--force`. Requiere `DATABASE_URL` en env (exit(1) si falta).
- **`sync_today_matches.py`** — sincronización de ventana móvil: crea ligas/equipos con IDs estables por hash (SHA256 → `% 2_000_000_000`) cuando el proveedor no entrega ID, upsert de partidos con `match_type` de liga (`KNOCKOUT_CUP` si el ID está en `KNOCKOUT_CUP_LEAGUE_IDS`), sincronización de cuotas vía `OddsService.sync_odds_for_matches` y fallback de marcadores con API-Football por fecha.
- Otros scripts de soporte: `sync_all_historical.py`, `apply_migration_011*.py`, `patch_matches_route.py`, `dedupe_teams.py`, `dedupe_matches_fuzzy.py`, `check_api_football.py`, `test_tickets.py`, `test_api_football.py`, `cleanup_db.py`, `enrich_european_team_logos.py`.

### 4.3 Infraestructura Docker

- `docker-compose.yml`: Redis 7 (`redis:7-alpine`, `--maxmemory 512mb`, `--maxmemory-policy allkeys-lru`, `--appendonly yes`, puerto local `127.0.0.1:6379`, healthcheck `redis-cli ping`).

---

## 5. Referencias rápidas de archivos clave

| Capa | Archivo |
|---|---|
| Config | `apps/api/config.py` |
| App / excepciones | `apps/api/main.py`, `apps/api/core/exceptions.py`, `apps/api/core/enums.py`, `apps/api/core/result.py` |
| DB | `apps/api/db/database.py`, `apps/api/models/*.py`, `apps/api/migrations/*.sql` |
| Repos | `apps/api/repositories/*.py` |
| Servicios | `apps/api/services/{api_football, odds_service, cache_service, llm_cascade, data_ingestion, match_stats_ingester, sofascore_ingester, team_normalizer}.py` + `providers/` |
| Orquestadores | `apps/api/orchestrators/{prediction_orchestrator, scanner_orchestrator}.py` |
| Engine | `apps/api/engine/{ticket_builder, kelly, match_tension, player_props_model, corners_model}.py` |
| ML | `packages/ml/betmind_ml/` (`pipeline/`, `models/`, `features/`, `ev/`, `calibration/`, `narrative/`, `backtesting/`, `bet_builder_engine.py`) |
| Web | `apps/web/lib/{api, betmind, league-metadata, formatMarketName, utils}.ts`, `apps/web/components/betmind/*.tsx` |
| CI | `.github/workflows/daily_predictions.yml` |
