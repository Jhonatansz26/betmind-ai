# AUDITORÍA COMPLETA — BACKEND BetMind AI

> **Fecha:** 2026-08-09  
> **Alcance:** `apps/api/` + `packages/ml/`  
> **Contexto:** documento de referencia para cualquiera que retome el trabajo — inventario factual, sin juicios de valor.

---

## 1. Arquitectura general

### Stack completo

| Capa | Tecnología | Versión | Notas |
|------|-----------|---------|-------|
| **Framework web** | FastAPI | `>=0.110.0,<1.0.0` | Con `uvicorn[standard]` |
| **ORM** | SQLAlchemy 2.0 | `>=2.0.25,<3.0.0` | Async, sin Alembic activo |
| **Base de datos dev** | SQLite | `aiosqlite>=0.20.0` | Archivo `betmind.db` local |
| **Base de datos prod** | PostgreSQL (Supabase) | `asyncpg>=0.29.0` | Pooler de Supabase |
| **Cache / rate limiting** | Redis 7 | `redis>=5.0.0,<6.0` | Upstash en prod, docker local |
| **Rate limiting** | slowapi | `>=0.1.9` | 200/min, 2000/hr por IP |
| **Validación** | Pydantic v2 | `>=2.6.0,<3.0.0` | Schemas en `schemas/` |
| **Configuración** | pydantic-settings | `>=2.1.0,<3.0.0` | `apps/api/config.py` |
| **Email** | Resend + SMTP (Gmail) | `resend>=1.0`, `aiosmtplib>=3.0` | Cascade: SMTP → Resend → stub |
| **ML engine** | NumPy + SciPy + Pandas | múltiples | Paquete `betmind-ml` en `packages/ml/` |
| **LLM** | Groq + Gemini + Anthropic | `groq`, `google-genai`, `anthropic` | Cascade para análisis táctico |
| **Web scraping** | Playwright + crawl4ai + DuckDuckGo | múltiples | SofaScore, Flashscore, ESPN |

### Estructura de carpetas

```
apps/api/
├── main.py                    # Entry point (lifespan, CORS, rate limit, health endpoints)
├── config.py                  # Settings vía pydantic-settings (todas las vars de entorno)
├── dependencies.py            # FastAPI DI: get_db, get_current_user_id, require_pro_user, etc.
├── requirements.txt           # Dependencias Python del backend
├── betmind.db                 # SQLite local (generado en dev)
│
├── core/                      # Utilidades base (enums, excepciones personalizadas, Result type)
│   ├── enums.py
│   ├── exceptions.py
│   └── result.py
│
├── db/                        # Configuración de base de datos
│   └── database.py            # Engine async, init_db (create_all), ping_db, dispose
│
├── models/                    # ORM models (SQLAlchemy) — 15 modelos, 15 tablas
│   ├── base.py                # Base declarativa + TimestampMixin
│   ├── user.py                # users
│   ├── team.py                # teams
│   ├── league.py              # leagues
│   ├── match.py               # matches (+ 8 relaciones a otras tablas)
│   ├── prediction.py          # predictions
│   ├── bookmaker_odd.py       # bookmaker_odds
│   ├── match_event.py         # match_events
│   ├── match_advanced_stats.py # match_advanced_stats (1:1 con matches)
│   ├── referee_profile.py     # referee_profiles
│   ├── tactical_analysis.py   # tactical_analyses (1:1 con matches)
│   ├── ticket.py              # saved_tickets
│   ├── bankroll.py            # bankrolls + bankroll_movements
│   └── subscription.py        # subscriptions + subscription_transactions
│
├── repositories/              # Capa de acceso a datos (patrón repositorio)
│   ├── base_repository.py     # CRUD genérico
│   ├── match_repository.py
│   ├── bookmaker_odd_repository.py
│   ├── league_repository.py
│   ├── team_repository.py
│   ├── ticket_repository.py
│   └── tactical_analysis_repository.py
│
├── services/                  # Lógica de negocio e integraciones externas
│   ├── api_football.py        # Cliente API-Football (v3)
│   ├── auth_service.py        # Auth + email (password reset con cascade SMTP→Resend→stub)
│   ├── cache_service.py       # Redis wrapper (get/set/delete con TTL, safe degradation)
│   ├── data_ingestion.py      # Pipeline de ingesta de datos (proveedores múltiples)
│   ├── llm_cascade.py         # Cascade Groq→Gemini→synthetic para narrativa táctica
│   ├── match_stats_ingester.py # SofaScore vía Playwright (alternativa al HTTP directo)
│   ├── odds_service.py        # Sincronización de odds desde API-Football
│   ├── sofascore_ingester.py  # SofaScore vía HTTP directo
│   ├── subscription_service.py # Lógica de suscripciones y webhooks Wompi
│   ├── team_normalizer.py     # Normalización de nombres de equipos
│   ├── wompi_service.py       # Cliente API Wompi (pagos)
│   ├── scrapers/              # Scrapers web
│   │   ├── match_fixture_scraper.py  # ESPN scoreboard scraper
│   │   └── uefa_qualifiers_scraper.py # Flashscore (crawl4ai) para clasificatorias UEFA
│   └── providers/             # Sistema modular de proveedores de datos
│       ├── base_provider.py
│       ├── provider_registry.py
│       ├── espn_provider.py
│       ├── football_data_provider.py
│       └── ai_agent/          # LangGraph agent: DuckDuckGo → crawl4ai → Claude (fallback)
│
├── orchestrators/             # Orquestadores de alto nivel
│   ├── prediction_orchestrator.py
│   └── scanner_orchestrator.py
│
├── routes/v1/                 # Endpoints REST (FastAPI routers)
│   ├── router.py              # Ensamblador de sub-routers
│   ├── auth.py                # Register, login, forgot/reset password
│   ├── users.py               # GET /me
│   ├── matches.py             # List, upcoming, detail, sync, H2H
│   ├── leagues.py             # List leagues with active matches
│   ├── predictions.py         # GET prediction by match_id
│   ├── scanner.py             # POST scan (stub — vacío)
│   ├── tickets.py             # Save, history, status, claim, generate
│   ├── subscriptions.py       # CRUD + webhook Wompi
│   ├── bankroll.py            # Setup, GET, PATCH, adjust (PRO-only)
│   └── backtesting.py         # POST run backtest (admin-only)
│
├── schemas/                   # Pydantic models (request/response)
│   ├── auth.py, bankroll.py, match.py, prediction.py
│   ├── scanner.py, subscription.py, ticket.py
│
├── engine/                    # Motor de apuestas (Kelly, corners, ticket builder, etc.)
│   ├── ticket_builder.py, kelly.py, corners_model.py
│   ├── match_tension.py, player_props_model.py
│
├── jobs/                      # Jobs programados (sin scheduler en repo)
│   ├── reconcile_pending_subscriptions.py
│   └── renew_subscriptions.py
│
├── migrations/                # DDL SQL manual (aplica solo en PostgreSQL/Supabase)
│   └── 004_*.sql ... 017_*.sql  (14 archivos, numerados 004–017)
│
└── scripts/
    └── enrich_european_team_logos.py
```

### Cómo se ejecuta localmente

```bash
# 1. Dependencias del sistema: Redis (docker compose up), Python 3.11+, Node.js

# 2. Backend
cd C:\betmind-ai
pip install -r requirements.txt -r apps/api/requirements.txt
pip install -e packages/ml
python -m uvicorn apps.api.main:app --reload --port 8000

# 3. Frontend (separado)
cd C:\betmind-ai\apps\web
npm run dev
```

- Backend: `http://localhost:8000`
- Swagger: `http://localhost:8000/docs`
- Frontend: `http://localhost:3000`

### Variables de entorno

**Archivo:** `C:\betmind-ai\.env` (activo, contiene secretos reales)  
**Template:** `C:\betmind-ai\.env.example`

| Variable | Obligatoria | Default | Propósito |
|----------|:-----------:|---------|-----------|
| `DATABASE_URL` | No | `sqlite+aiosqlite:///./betmind.db` | Conexión DB (dev: SQLite, prod: PostgreSQL) |
| `REDIS_URL` | No | `redis://localhost:6379/0` | Redis (rate limiting + cache) |
| `SECRET_KEY` | **Sí** (prod) | `"change-me-in-production"` | JWT signing |
| `ADMIN_API_KEY` | Opcional | `""` | API key para endpoints admin |
| `API_FOOTBALL_KEY` | **Sí** (para datos) | `""` | Datos de fútbol |
| `FOOTBALL_DATA_KEY` | Opcional | `None` | Proveedor alternativo (PL, LaLiga) |
| `GROQ_API_KEY` / `GROQ_API_KEYS` | Opcional | `""` | LLM primario (cascade) |
| `GEMINI_API_KEY` | Opcional | `None` | LLM fallback (cascade) |
| `ANTHROPIC_API_KEY` | Opcional | `None` | LLM para AI search agent |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | Opcional | `None` | Email primario (Gmail SMTP) |
| `RESEND_API_KEY` | Opcional | `None` | Email secundario |
| `WOMPI_PUBLIC_KEY` / `WOMPI_PRIVATE_KEY` | Opcional | `""` | Pagos (sandbox) |
| `WOMPI_INTEGRITY_SECRET` | Opcional | `""` | Hash de integridad |
| `WOMPI_EVENTS_SECRET` | Opcional | `""` | Firma HMAC webhooks |
| `ALLOWED_ORIGINS` | No | `localhost:3000,127.0.0.1:3000` | CORS origins |
| `DEBUG` | No | `False` | Activa SQL echo |
| `SUBSCRIPTION_GRACE_DAYS` | No | `3` | Días de gracia tras fallo de cobro |
| `PENDING_PAYMENT_RECONCILE_DELAY_MINUTES` | No | `10` | Minutos antes de reconciliar pagos |

**Nota:** La app arranca sin API keys externas — endpoints de datos devolverán error/vacío, pero auth, health, y suscripciones (sin Wompi) sí funcionan.

---

## 2. Inventario completo de rutas

### Health (`main.py`)

| Método | Path | Auth | PRO | Descripción | Archivo:línea |
|--------|------|:----:|:---:|-------------|---------------|
| `GET` | `/` | No | No | Root check (app name + version) | `main.py:119` |
| `GET` | `/health` | No | No | Health check (app name + version) | `main.py:124` |
| `GET` | `/api/v1/health/db` | No | No | DB connectivity (ping) | `main.py:129` |
| `GET` | `/api/v1/health/redis` | No | No | Redis connectivity (ping) | `main.py:134` |

### Auth (`routes/v1/auth.py`)

| Método | Path | Auth | PRO | Descripción | Archivo:línea |
|--------|------|:----:|:---:|-------------|---------------|
| `POST` | `/api/v1/auth/register` | No | No | Crear cuenta, retorna JWT | `auth.py:42` |
| `POST` | `/api/v1/auth/login` | No | No | Login, retorna JWT | `auth.py:74` |
| `POST` | `/api/v1/auth/forgot-password` | No | No | Envía link de reset (200 siempre) | `auth.py:97` |
| `POST` | `/api/v1/auth/reset-password` | No | No | Consume token + actualiza password | `auth.py:122` |

### Users (`routes/v1/users.py`)

| Método | Path | Auth | PRO | Descripción | Archivo:línea |
|--------|------|:----:|:---:|-------------|---------------|
| `GET` | `/api/v1/users/me` | Sí | No | Perfil del usuario autenticado | `users.py:16` |

### Tickets (`routes/v1/tickets.py`)

| Método | Path | Auth | PRO | Descripción | Archivo:línea |
|--------|------|:----:|:---:|-------------|---------------|
| `POST` | `/api/v1/tickets/save` | Opt | No | Guardar ticket (free: máx 5) | `tickets.py:49` |
| `GET` | `/api/v1/tickets/history` | Sí | No | Historial de tickets del usuario | `tickets.py:81` |
| `PATCH` | `/api/v1/tickets/{id}/status` | Sí | No | Actualizar estado + movimiento bankroll | `tickets.py:90` |
| `POST` | `/api/v1/tickets/claim` | Sí | No | Reclamar tickets anónimos | `tickets.py:114` |
| `POST` | `/api/v1/tickets/generate` | Opt | No | Generar tickets con IA (free: 2/día) | `tickets.py:339` |

### Subscriptions (`routes/v1/subscriptions.py`)

| Método | Path | Auth | PRO | Descripción | Archivo:línea |
|--------|------|:----:|:---:|-------------|---------------|
| `GET` | `/api/v1/subscriptions/me` | Sí | No | Detalle de suscripción del usuario | `subscriptions.py:80` |
| `GET` | `/api/v1/subscriptions/wompi-tokenization-key` | Sí | No | Llave pública Wompi para frontend | `subscriptions.py:94` |
| `POST` | `/api/v1/subscriptions/trial` | Sí | No | Iniciar trial PRO de 7 días | `subscriptions.py:108` |
| `POST` | `/api/v1/subscriptions/activate` | Sí | No | Activar suscripción paga vía Wompi | `subscriptions.py:149` |
| `POST` | `/api/v1/subscriptions/cancel` | Sí | No | Cancelar suscripción | `subscriptions.py:244` |
| `POST` | `/api/v1/subscriptions/refund` | Sí | No | Solicitar reembolso (revoca PRO, reembolso monetario manual en Wompi) | `subscriptions.py:263` |
| `POST` | `/api/v1/webhooks/wompi` | HMAC | No | Webhook `transaction.updated` de Wompi | `subscriptions.py:352` |

### Matches (`routes/v1/matches.py`)

| Método | Path | Auth | PRO | Descripción | Archivo:línea |
|--------|------|:----:|:---:|-------------|---------------|
| `GET` | `/api/v1/matches/` | No | No | Listar partidos (filtro fecha/status) | `matches.py:28` |
| `GET` | `/api/v1/matches/upcoming/` | No | No | Próximos partidos (-2h a +36h, máx 10) | `matches.py:118` |
| `GET` | `/api/v1/matches/{id}` | No | No | Detalle completo de un partido | `matches.py:146` |
| `POST` | `/api/v1/matches/sync/{league_id}` | No | No | Sincronizar datos de una liga (API-Football) | `matches.py:215` |
| `POST` | `/api/v1/matches/sync-all` | No | No | Sincronizar todas las ligas objetivo | `matches.py:275` |
| `GET` | `/api/v1/matches/{id}/h2h` | No | No | Head-to-head + forma reciente | `matches.py:312` |

### Predictions (`routes/v1/predictions.py`)

| Método | Path | Auth | PRO | Descripción | Archivo:línea |
|--------|------|:----:|:---:|-------------|---------------|
| `GET` | `/api/v1/predictions/{match_id}` | Opt | No | Predicción completa (free: EV truncado, bet_builder oculto) | `predictions.py:59` |

### Leagues (`routes/v1/leagues.py`)

| Método | Path | Auth | PRO | Descripción | Archivo:línea |
|--------|------|:----:|:---:|-------------|---------------|
| `GET` | `/api/v1/leagues/` | No | No | Ligas con partidos activos, agrupadas por región | `leagues.py:31` |

### Scanner (`routes/v1/scanner.py`)

| Método | Path | Auth | PRO | Descripción | Archivo:línea |
|--------|------|:----:|:---:|-------------|---------------|
| `POST` | `/api/v1/scanner/` | No | No | Stub — siempre retorna lista vacía | `scanner.py:8` |

### Bankroll (`routes/v1/bankroll.py`)

| Método | Path | Auth | PRO | Descripción | Archivo:línea |
|--------|------|:----:|:---:|-------------|---------------|
| `POST` | `/api/v1/bankroll/setup` | **PRO** | **Sí** | Crear bankroll (409 si ya existe) | `bankroll.py:56` |
| `GET` | `/api/v1/bankroll` | **PRO** | **Sí** | Estado actual + historial de movimientos | `bankroll.py:96` |
| `PATCH` | `/api/v1/bankroll` | **PRO** | **Sí** | Actualizar `risk_profile` | `bankroll.py:106` |
| `POST` | `/api/v1/bankroll/adjust` | **PRO** | **Sí** | Ajuste manual de capital | `bankroll.py:122` |

### Backtesting (`routes/v1/backtesting.py`)

| Método | Path | Auth | PRO | Descripción | Archivo:línea |
|--------|------|:----:|:---:|-------------|---------------|
| `POST` | `/api/v1/backtesting/{league_key}` | Admin | No | Walk-forward backtest (requiere `X-Admin-Key`) | `backtesting.py:18` |

### Resumen

| Categoría | Cantidad |
|-----------|:--------:|
| Total endpoints | **35** |
| Públicos (sin auth) | 17 |
| Auth requerida (`get_current_user_id`) | 9 |
| Auth opcional (`get_optional_user_id`) | 3 |
| PRO requerido (`require_pro_user`) | 4 |
| Admin key requerida | 1 |
| HMAC signature (webhook) | 1 |

---

## 3. Modelo de datos completo

### Tablas (15 en total, manejadas por 15 modelos ORM)

#### `users`
| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `Integer` PK autoincrement | |
| `email` | `String(255)` UNIQUE NOT NULL INDEX | |
| `auth_uid` | `Uuid` UNIQUE NULL INDEX | UUID de Supabase auth |
| `hashed_password` | `String(255)` NOT NULL | |
| `full_name` | `String(255)` NULL | |
| `is_active` | `Boolean` NOT NULL DEFAULT True | |
| `is_pro` | `Boolean` NOT NULL DEFAULT False | Flag PRO |
| `pro_expires_at` | `DateTime(tz)` NULL | Expiración PRO |
| `created_at` / `updated_at` | TimestampMixin | |

#### `teams`
| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `Integer` PK autoincrement | |
| `external_id` | `Integer` UNIQUE NOT NULL INDEX | API-Football team ID |
| `name` | `String(150)` NOT NULL | |
| `logo_url` | `String(500)` NULL | |
| `country` | `String(100)` NULL | |
| `created_at` / `updated_at` | TimestampMixin | |

#### `leagues`
| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `Integer` PK autoincrement | |
| `external_id` | `Integer` UNIQUE NOT NULL INDEX | API-Football league ID |
| `name` | `String(150)` NOT NULL | |
| `country` | `String(100)` NULL | |
| `logo_url` | `String(500)` NULL | |
| `tier` | `String(20)` NULL | |
| `created_at` / `updated_at` | TimestampMixin | |

#### `matches` (tabla central)
| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `Integer` PK autoincrement | |
| `external_id` | `Integer` UNIQUE NOT NULL INDEX | API-Football fixture ID |
| `league_id` | `Integer` FK→leagues.id NOT NULL INDEX | |
| `home_team_id` | `Integer` FK→teams.id NOT NULL INDEX | |
| `away_team_id` | `Integer` FK→teams.id NOT NULL INDEX | |
| `match_date` | `DateTime(tz)` NOT NULL INDEX | |
| `status` | `String(20)` NOT NULL DEFAULT "SCHEDULED" INDEX | |
| `match_type` | `String(20)` NOT NULL DEFAULT "LEAGUE" INDEX | `LEAGUE` / `KNOCKOUT_CUP` |
| `regulation_time_only` | `Boolean` NOT NULL DEFAULT True | |
| `home_score` / `away_score` | `Integer` NULL | |
| `home_corners` / `away_corners` | `Integer` NULL | |
| `home_yellows` / `away_yellows` | `Float` NULL | |
| `home_reds` / `away_reds` | `Float` NULL | |
| `home_fouls` / `away_fouls` | `Float` NULL | |
| `home_shots_on_target` / `away_shots_on_target` | `Float` NULL | |
| `sofascore_event_id` | `BigInteger` UNIQUE NULL | |
| `referee_id` | `BigInteger` FK→referee_profiles.referee_id NULL INDEX | |
| `alternate_external_ids` | `Text` NULL | JSON array para deduplicación |
| `created_at` / `updated_at` | TimestampMixin | |

**Relaciones en el modelo Match:**
- `league` → League (lazy="noload")
- `home_team` → Team (lazy="noload")
- `away_team` → Team (lazy="noload")
- `predictions` → list[Prediction] (lazy="noload")
- `bookmaker_odds` → list[BookmakerOdd] (lazy="**selectin**")
- `events` → list[MatchEvent] (lazy="**selectin**", cascade delete-orphan)
- `advanced_stats` → MatchAdvancedStats 1:1 (lazy="**selectin**", cascade delete-orphan)
- `referee` → RefereeProfile (lazy="**selectin**")

#### `predictions`
| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `Integer` PK autoincrement | |
| `match_id` | `Integer` FK→matches.id NOT NULL INDEX | |
| `prediction_type` | `String(50)` NOT NULL | |
| `confidence` | `String(20)` NOT NULL | |
| `value_score` | `Float` NOT NULL | |
| `reasoning` | `Text` NULL | |
| `lambda_home` / `lambda_away` | `Float` NULL | Poisson xG |
| `home_attack_index` / `away_attack_index` | `Float` NULL | |
| `home_defense_index` / `away_defense_index` | `Float` NULL | |
| `markets_json` | `Text` NULL | Probabilidades serializadas |
| `created_at` / `updated_at` | TimestampMixin | |

#### `bookmaker_odds`
| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `Integer` PK autoincrement | |
| `match_id` | `Integer` FK→matches.id NOT NULL INDEX | |
| `market_name` | `String(50)` NOT NULL | |
| `bookmaker_name` | `String(100)` NOT NULL DEFAULT "api_football" | |
| `odds_value` | `Float` NOT NULL | |
| `external_fixture_id` | `Integer` NULL | |
| `fetched_at` | `DateTime(tz)` NOT NULL | |
| `created_at` / `updated_at` | TimestampMixin | |
| | `UNIQUE(match_id, market_name, bookmaker_name)` | |

#### `match_events`
| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `Integer` PK autoincrement | |
| `match_id` | `Integer` FK→matches.id CASCADE NOT NULL INDEX | |
| `event_type` | `String(20)` NOT NULL | goal, card, sub |
| `minute` | `Integer` NOT NULL | |
| `added_time` | `Integer` NOT NULL DEFAULT 0 | |
| `is_home` | `Boolean` NULL | |
| `player_name` | `String(150)` NULL | |
| `created_at` | `DateTime(tz)` NOT NULL | |
| | `UNIQUE(match_id, event_type, minute, added_time, is_home, player_name)` | |

#### `match_advanced_stats` (1:1 con matches, PK = match_id)
| Columna | Tipo | Notas |
|---------|------|-------|
| `match_id` | `Integer` PK + FK→matches.id CASCADE | |
| `home_xg` / `away_xg` | `Float` NULL | |
| `home_shots` / `away_shots` | `Integer` NULL | |
| `home_shots_on_target` / `away_shots_on_target` | `Integer` NULL | |
| `home_corners` / `away_corners` | `Integer` NULL | |
| `home_fouls` / `away_fouls` | `Integer` NULL | |
| `updated_at` | `DateTime(tz)` NOT NULL | |

#### `referee_profiles`
| Columna | Tipo | Notas |
|---------|------|-------|
| `referee_id` | `BigInteger` PK (natural) | |
| `name` | `String(150)` NOT NULL | |
| `matches_count` | `Integer` NOT NULL DEFAULT 0 | |
| `yellow_cards` / `red_cards` | `Integer` NOT NULL DEFAULT 0 | |
| `yellow_cards_avg` / `red_cards_avg` | `Float` NOT NULL DEFAULT 0 | |
| `updated_at` | `DateTime(tz)` NOT NULL | |

#### `tactical_analyses` (1:1 con matches)
| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `Integer` PK autoincrement | |
| `match_id` | `Integer` FK→matches.id UNIQUE NOT NULL INDEX | |
| `model_version` | `String(50)` NOT NULL DEFAULT "narrative_v1.0" | |
| `goals_narrative` / `cards_narrative` / `corners_narrative` | `JSON` NULL | |
| `player_props_narratives` | `JSON` NULL | |
| `bet_builder_suggestions` | `JSON` NULL | |
| `overall_confidence` | `Integer` NOT NULL DEFAULT 0 | |
| `match_preview_headline` | `String(200)` NOT NULL | |
| `llm_model_used` | `String(100)` NOT NULL | |
| `generation_tokens_used` | `Integer` NOT NULL DEFAULT 0 | |
| `data_completeness_score` | `Float` NOT NULL DEFAULT 0.0 | |
| `created_at` / `updated_at` | TimestampMixin | |

#### `saved_tickets`
| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `Integer` PK autoincrement | |
| `ticket_data` | `JSON` NOT NULL | |
| `status` | `String(10)` NOT NULL DEFAULT "PENDING" | PENDING/WON/LOST/VOID |
| `total_odds` | `Float` NOT NULL | |
| `total_ev` | `Float` NOT NULL | |
| `stake_amount` | `Float` NULL | |
| `user_id` | `Integer` FK→users.id SET NULL INDEX | |
| `created_at` | `DateTime(tz)` NOT NULL | |

#### `bankrolls`
| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `Integer` PK autoincrement | |
| `user_id` | `Integer` FK→users.id CASCADE UNIQUE NOT NULL INDEX | |
| `current_capital` | `Float` NOT NULL | |
| `risk_profile` | `String(20)` NOT NULL DEFAULT "moderado" | |
| `created_at` / `updated_at` | Timestamps propios | |

#### `bankroll_movements`
| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `Integer` PK autoincrement | |
| `bankroll_id` | `Integer` FK→bankrolls.id CASCADE NOT NULL INDEX | |
| `type` | `String(30)` NOT NULL | ticket_won/lost/void/manual_adjustment |
| `amount` | `Float` NOT NULL | Positivo=crédito, negativo=débito |
| `ticket_id` | `Integer` FK→saved_tickets.id SET NULL | |
| `reason` | `String(500)` NULL | |
| `created_at` | `DateTime(tz)` NOT NULL | |
| | `UNIQUE INDEX ON ticket_id WHERE ticket_id IS NOT NULL` | |

#### `subscriptions`
| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `Integer` PK autoincrement | |
| `user_id` | `Integer` FK→users.id CASCADE UNIQUE NOT NULL INDEX | |
| `wompi_payment_source_id` | `String(100)` NULL | |
| `plan` | `String(20)` NOT NULL | |
| `status` | `String(30)` NOT NULL INDEX | trial/pending_payment/active/past_due/cancelled/refund_requested |
| `current_period_end` | `DateTime(tz)` NOT NULL | |
| `trial_ends_at` | `DateTime(tz)` NULL | |
| `initial_transaction_id` | `String(100)` NULL | |
| `recurrence_enabled` | `Boolean` NULL | COF de Wompi |
| `created_at` / `updated_at` | TimestampMixin | |

#### `subscription_transactions`
| Columna | Tipo | Notas |
|---------|------|-------|
| `id` | `Integer` PK autoincrement | |
| `subscription_id` | `Integer` FK→subscriptions.id CASCADE NOT NULL INDEX | |
| `wompi_transaction_id` | `String(100)` UNIQUE NOT NULL | |
| `reference` | `String(255)` UNIQUE NOT NULL | |
| `kind` | `String(20)` NOT NULL | initial/renewal |
| `amount_in_cents` | `Integer` NOT NULL | |
| `status` | `String(20)` NOT NULL | |
| `processor_response_code` | `String(50)` NULL | |
| `status_message` | `String(500)` NULL | |
| `created_at` / `updated_at` | TimestampMixin | |

### Diagrama de relaciones (textual)

```
users ──1:1── subscriptions          (user_id FK, UNIQUE)
users ──1:1── bankrolls              (user_id FK, UNIQUE)
users ──1:N── saved_tickets          (user_id FK, nullable, SET NULL on delete)

subscriptions ──1:N── subscription_transactions  (CASCADE)

bankrolls ──1:N── bankroll_movements             (CASCADE)
bankroll_movements ──0..1:N── saved_tickets      (ticket_id FK, nullable, SET NULL)

leagues  ──1:N── matches              (league_id FK)
teams    ──1:N── matches (home)       (home_team_id FK)
teams    ──1:N── matches (away)       (away_team_id FK)
referee_profiles ──1:N── matches      (referee_id FK, nullable)

matches  ──1:N── predictions          (match_id FK)
matches  ──1:N── bookmaker_odds       (match_id FK)
matches  ──1:N── match_events         (match_id FK, CASCADE)
matches  ──1:1── match_advanced_stats (match_id FK/PK, CASCADE)
matches  ──1:1── tactical_analyses    (match_id FK, UNIQUE)
```

### Migraciones

| # | Archivo | Contenido |
|---|---------|-----------|
| 004 | `004_create_tactical_analyses.sql` | Crea tabla tactical_analyses + RLS + índices |
| 005 | `005_create_bookmaker_odds.sql` | Crea tabla bookmaker_odds + RLS + índices |
| 006 | `006_expand_predictions_table.sql` | Agrega columnas Poisson y markets_json a predictions |
| 007 | `007_add_match_statistics_columns.sql` | 10 columnas de estadísticas a matches |
| 008 | `008_create_sofascore_statistics.sql` | Crea match_events, match_advanced_stats, referee_profiles |
| 009 | `009_enable_rls_statistics.sql` | RLS en tablas de estadísticas |
| 010 | `010_enable_rls_global.sql` | RLS global en matches, predictions, teams, leagues, users |
| 011 | `011_add_match_type.sql` | Columna match_type + backfill de copas |
| 012 | `012_create_saved_tickets.sql` | Crea tabla saved_tickets |
| 013 | `013_add_user_id_to_saved_tickets.sql` | FK user_id + auth_uid en users + RLS tickets |
| 014 | `014_add_pro_fields_to_users.sql` | is_pro + pro_expires_at en users |
| 015 | `015_create_bankroll_tables.sql` | Crea bankrolls + bankroll_movements |
| 016 | `016_add_stake_amount_to_saved_tickets.sql` | stake_amount + índice parcial único en movements |
| 017 | `017_create_subscriptions.sql` | Crea subscriptions + subscription_transactions |

**Gap 001–003:** Las primeras 5 tablas (users, teams, leagues, matches, predictions) se crearon en Fase 0 del proyecto. Su DDL inicial no se capturó como archivos SQL de migración. La numeración de migraciones SQL comienza en 004.

**Mecanismo de migración:**
- **Desarrollo local (SQLite):** `Base.metadata.create_all()` en `db/database.py:init_db()`. No usa Alembic. No usa los archivos SQL de `migrations/`. El esquema se deriva de los modelos ORM al arrancar.
- **Producción (PostgreSQL/Supabase):** Los archivos SQL en `migrations/` se aplican manualmente vía Supabase SQL Editor o `psql`. No hay Alembic, Flyway ni migrador automático.
- **Consecuencia:** Los modelos ORM son la fuente de verdad para el esquema. Las migraciones SQL son un reflejo manual que debe mantenerse sincronizado. Si se modifica un modelo sin crear/actualizar la migración SQL correspondiente, producción y desarrollo divergen.

---

## 4. Integraciones externas — estado real

### 4.1 Wompi (pagos)

| Atributo | Valor |
|----------|-------|
| **Archivo** | `services/wompi_service.py` |
| **Función** | Procesamiento de pagos de suscripción (mensual/anual). Tokenización de tarjetas, creación de payment sources, transacciones recurrentes. |
| **URL base** | `https://sandbox.wompi.co/v1` (default sandbox, configurable vía `WOMPI_BASE_URL`) |
| **Endpoints** | `/merchants/{key}`, `/tokens/keys/tokenization`, `/payment_sources`, `/transactions`, `/transactions/{id}` |
| **Variables de entorno** | `WOMPI_BASE_URL`, `WOMPI_PUBLIC_KEY`, `WOMPI_PRIVATE_KEY`, `WOMPI_INTEGRITY_SECRET`, `WOMPI_EVENTS_SECRET`, `WOMPI_MONTHLY_AMOUNT_CENTS` (default 2,990,000 COP), `WOMPI_ANNUAL_AMOUNT_CENTS` (default 24,990,000 COP) |
| **Stub/fallback** | **No.** Si las keys faltan, `WompiConfigurationError`. |
| **Estado** | Sandbox. Las keys en `.env` son `pub_test_*` / `prv_test_*`. Para producción se requiere cambiar URL base y keys. |

### 4.2 API-Football (api-sports.io)

| Atributo | Valor |
|----------|-------|
| **Archivo** | `services/api_football.py` |
| **Función** | Fuente primaria de datos: ligas, equipos, fixtures, standings, H2H, odds. |
| **URL base** | `https://v3.football.api-sports.io` |
| **Variables de entorno** | `API_FOOTBALL_KEY` |
| **Stub/fallback** | **No.** Si la key está vacía, toda llamada lanza `ExternalAPIException("API key not configured")`. |
| **Rate limiting** | Alerta cuando `x-ratelimit-requests-remaining < 10`. HTTP 429 → excepción. |

### 4.3 ESPN API (pública, sin key)

| Atributo | Valor |
|----------|-------|
| **Archivos** | `services/scrapers/match_fixture_scraper.py`, `services/providers/espn_provider.py` |
| **Función** | Scoreboards, standings, team schedules, search. Cubre 16+ ligas. |
| **URL base** | `https://site.api.espn.com/apis/site/v2/sports/soccer` |
| **Variables de entorno** | **Ninguna.** API pública, sin key. |
| **Stub/fallback** | Degradación graceful (retorna `[]` en error HTTP). |

### 4.4 SofaScore (HTTP directo)

| Atributo | Valor |
|----------|-------|
| **Archivo** | `services/sofascore_ingester.py` |
| **Función** | Ingesta post-partido: event data, incidents, statistics, shotmap. |
| **URL base** | `https://www.sofascore.com/api/v1` |
| **Variables de entorno** | **Ninguna.** Headers hardcodeados. |
| **Stub/fallback** | **No.** HTTP 429 → `RuntimeError("SofaScore rate limit reached")`. |

### 4.5 SofaScore (Playwright — alternativa)

| Atributo | Valor |
|----------|-------|
| **Archivo** | `services/match_stats_ingester.py` |
| **Función** | Alternativa al HTTP directo cuando SofaScore bloquea por bot detection. Usa Chromium headless. |
| **Variables de entorno** | **Ninguna.** Requiere `playwright install chromium`. |
| **Stub/fallback** | **No.** Si playwright no está instalado, `RuntimeError`. |

### 4.6 Flashscore (crawl4ai — UEFA Qualifiers)

| Atributo | Valor |
|----------|-------|
| **Archivo** | `services/scrapers/uefa_qualifiers_scraper.py` |
| **Función** | Scraper de fixtures de clasificatorias UEFA (Champions y Conference League) cuando ESPN no tiene datos. |
| **URL base** | `https://www.flashscore.com/football/europe/...` |
| **Variables de entorno** | **Ninguna.** Requiere `crawl4ai`. |
| **Stub/fallback** | **Sí — él mismo es el fallback.** Si `crawl4ai` no instalado, warning + retorna `[]`. |

### 4.7 football-data.org

| Atributo | Valor |
|----------|-------|
| **Archivo** | `services/providers/football_data_provider.py` |
| **Función** | Proveedor secundario para Premier League y LaLiga (backup de ESPN). |
| **URL base** | `https://api.football-data.org/v4` |
| **Variables de entorno** | `FOOTBALL_DATA_KEY` |
| **Stub/fallback** | **No.** Key vacía → `ExternalAPIException`. |

### 4.8 Groq (LLM primario)

| Atributo | Valor |
|----------|-------|
| **Archivo** | `services/llm_cascade.py` |
| **Función** | Capa 1 del cascade LLM para análisis táctico. Modelo: `llama-3.1-8b-instant`. |
| **Variables de entorno** | `GROQ_API_KEY` o `GROQ_API_KEYS` (comma-separated, se usa la primera disponible) |
| **Stub/fallback** | **Sí — cascade.** Fallback a Gemini (capa 2), luego synthetic (capa 3, sin LLM). |

### 4.9 Gemini (LLM secundario)

| Atributo | Valor |
|----------|-------|
| **Archivo** | `services/llm_cascade.py` |
| **Función** | Capa 2 del cascade. Modelo: `gemini-2.0-flash`. |
| **Variables de entorno** | `GEMINI_API_KEY` |
| **Stub/fallback** | **Sí — él mismo es fallback.** Si `google-genai` no instalado o key no configurada, se omite silenciosamente. |

### 4.10 Anthropic / Claude (LLM — AI Search Agent)

| Atributo | Valor |
|----------|-------|
| **Archivo** | `services/providers/ai_agent/nodes/parse_node.py` |
| **Función** | Extrae datos estructurados de fixtures desde HTML scrapeado (usado por el AI Search Agent para Liga BetPlay). Modelo: `claude-3-5-sonnet-20241022`. |
| **Variables de entorno** | `ANTHROPIC_API_KEY` |
| **Stub/fallback** | **No.** Key no configurada → error en el state del agente, retorna vacío. |

### 4.11 DuckDuckGo (búsqueda web)

| Atributo | Valor |
|----------|-------|
| **Archivo** | `services/providers/ai_agent/nodes/search_node.py` |
| **Función** | Búsqueda web para el AI Search Agent (descubre URLs con datos de partidos). |
| **Variables de entorno** | **Ninguna.** |
| **Stub/fallback** | Error de red → retorna lista vacía. |

### 4.12 Resend (email)

| Atributo | Valor |
|----------|-------|
| **Archivo** | `services/auth_service.py:120-129` |
| **Función** | Envío de emails de password reset (secundario, después de SMTP). |
| **Variables de entorno** | `RESEND_API_KEY`, `EMAIL_FROM_ADDRESS` |
| **Stub/fallback** | **Sí — triple cascade.** Después de intentar SMTP y Resend, cae a `_log_stub()` (consola). |

### 4.13 SMTP / Gmail (email)

| Atributo | Valor |
|----------|-------|
| **Archivo** | `services/auth_service.py:132-149` |
| **Función** | Envío primario de emails (password reset). |
| **Variables de entorno** | `SMTP_SERVER` (default `smtp.gmail.com`), `SMTP_PORT` (default 587), `SMTP_USERNAME`, `SMTP_PASSWORD` |
| **Stub/fallback** | **Sí — triple cascade.** SMTP → Resend → `_log_stub()`. |

### 4.14 Redis (caching)

| Atributo | Valor |
|----------|-------|
| **Archivo** | `services/cache_service.py` |
| **Función** | Caché en memoria: get/set/delete con TTL, JSON, Pydantic, increment atómico. |
| **Variables de entorno** | `REDIS_URL` (default `redis://localhost:6379/0`) |
| **Stub/fallback** | Degradación graceful. Todo método wrapped en try/except → get retorna `None`, set/delete retorna `False`, increment retorna `0`. |

---

## 5. Jobs / procesos programados

### 5.1 `reconcile_pending_subscriptions`

| Atributo | Valor |
|----------|-------|
| **Archivo** | `jobs/reconcile_pending_subscriptions.py` |
| **Función** | Busca suscripciones trabadas en `status = "pending_payment"` por más de 10 minutos, consulta el estado real en Wompi vía `GET /transactions/{id}`, y aplica la transición correspondiente (APPROVED → active, DECLINED → cancelled). |
| **Ejecución** | `python -m apps.api.jobs.reconcile_pending_subscriptions` (manual o vía cron externo). |
| **Sin scheduler** | No hay cron, `docker-compose.yml` solo tiene Redis. Depende de cron externo del entorno de deployment. |
| **Si nunca corre** | Suscripciones con webhook perdido quedan en limbo indefinido. Usuarios que pagaron no reciben PRO. El webhook de Wompi es el camino primario — este job es red de seguridad. |
| **Concurrencia** | `SELECT ... FOR UPDATE SKIP LOCKED` (seguro para múltiples workers). |

### 5.2 `renew_subscriptions`

| Atributo | Valor |
|----------|-------|
| **Archivo** | `jobs/renew_subscriptions.py` |
| **Función** | Renueva suscripciones activas cuyo `current_period_end` ya pasó. Intenta cobro recurrente vía Wompi (si hay payment source y recurrence habilitado). Si falla el cobro: mueve a `past_due` + extiende PRO por `SUBSCRIPTION_GRACE_DAYS` (3 días). Para suscripciones `past_due` más allá del grace period: desactiva PRO (`user.is_pro = False`). |
| **Ejecución** | `python -m apps.api.jobs.renew_subscriptions` (diseñado para correr 1 vez/día vía cron externo). |
| **Sin scheduler** | Misma situación que reconcile. |
| **Si nunca corre** | Sin renovaciones automáticas. Todas las suscripciones expiran eventualmente. Pipeline de cobro recurrente roto. |

---

## 6. Seguridad y enforcement

### 6.1 Endpoints protegidos por PRO

Los únicos endpoints que requieren suscripción PRO activa (`require_pro_user` → 401 si no auth, 403 si no PRO):

| Endpoint | Archivo:línea |
|----------|---------------|
| `POST /api/v1/bankroll/setup` | `bankroll.py:56` |
| `GET /api/v1/bankroll` | `bankroll.py:96` |
| `PATCH /api/v1/bankroll` | `bankroll.py:106` |
| `POST /api/v1/bankroll/adjust` | `bankroll.py:122` |

### 6.2 "Limitación de UI únicamente" — enforcement real

| Feature | Dónde se limita | Tipo de enforcement |
|---------|----------------|---------------------|
| **Bet Builder** en predicciones | `predictions.py:59` — si no es PRO, `bet_builder` se setea a `None` en la respuesta | **Backend** (real, no solo UI) |
| **EV truncado** para free users | `predictions.py:59` — `value_score` se trunca a 10 | **Backend** (real) |
| **Generación de tickets** free | `tickets.py:339` — rate limit de 2/día, verificado en backend con Redis | **Backend** (real) |
| **Límite 5 tickets guardados** free | `tickets.py:49` — verificado en backend contando tickets del usuario | **Backend** (real) |
| **Scanner** | `scanner.py:8` — stub, siempre retorna `[]` | No implementado |

### 6.3 CORS

**Archivo:** `main.py:57-63`

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- Orígenes permitidos vía `ALLOWED_ORIGINS` (default: `localhost:3000`, `127.0.0.1:3000`).
- El validador `normalize_allowed_origins()` en `config.py` soporta strings comma-separated y JSON arrays.
- Credenciales permitidas, todos los métodos y headers.

### 6.4 Rate limiting

**Archivo:** `main.py:32-36`

```python
limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=settings.REDIS_URL,
    default_limits=["200 per minute", "2000 per hour"],
)
```

- Por IP (`get_remote_address`, X-Forwarded-For aware).
- 200 req/min, 2000 req/hr a nivel global.
- Backed por Redis (Upstash en prod).
- **No hay rate limiting por endpoint** más allá de los límites de negocio explícitos (2 tickets/día, 5 tickets guardados) implementados en los handlers.

### 6.5 RLS (Row Level Security) en Supabase

Las migraciones 009 y 010 habilitan RLS en 8 tablas con políticas:
- `anon` / `authenticated`: solo SELECT.
- `service_role`: acceso completo.
- `users`: sin política pública de SELECT (contiene hashed passwords).

**Nota:** RLS solo aplica en PostgreSQL/Supabase. En SQLite local no existe RLS.

---

## 7. Código muerto o inconsistencias conocidas

### 7.1 TODOs

| Archivo | Línea | Contenido |
|---------|:-----:|-----------|
| `routes/v1/subscriptions.py` | 293 | `# TODO: cuando se confirme el endpoint real de reembolsos de Wompi, automatizar este paso.` |

No se encontraron `FIXME`, `HACK`, `WORKAROUND`, ni `XXX` en `apps/api/`.

### 7.2 Stubs y código no implementado

| Ubicación | Descripción |
|-----------|-------------|
| `routes/v1/scanner.py:8` | `POST /scanner/` — endpoint registrado pero siempre retorna `{"opportunities": []}`. No tiene lógica real. |
| `services/auth_service.py:110-117` | `_log_stub()` — fallback de email que solo imprime en consola. No es un bug: es degradación graceful cuando SMTP y Resend no están configurados. |

### 7.3 Inconsistencias arquitectónicas

| Ubicación | Descripción |
|-----------|-------------|
| `models/match.py` | Relaciones `bookmaker_odds`, `events`, `advanced_stats`, `referee` declaradas con `lazy="selectin"` a nivel modelo, pero los endpoints las cargan explícitamente con `selectinload()` en las queries (o no las cargan, como `bookmaker_odds`). Esto crea riesgo de double-loading: si alguien accede a `match.bookmaker_odds` en una sesión donde ya se cargó vía `_fetch_odds_for_matches()`, SQLAlchemy podría disparar otra query. |
| `routes/v1/matches.py` | `/upcoming/` no carga `predictions` vía `selectinload`, pero `_match_to_dict_full()` intenta acceder a `m.predictions[0]`. El `try/except` captura el `InvalidRequestError` silenciosamente y pone `prediction = None`. Esto es intencional (upcoming no tiene predicciones), pero es un patrón de silent failure. |
| `migrations/` vs `db/database.py` | Doble mecanismo de schema: `Base.metadata.create_all()` para dev local (SQLite), migraciones SQL manuales para prod (PostgreSQL/Supabase). No hay Alembic ni sincronización automática. Riesgo de divergencia si se modifica un modelo sin crear la migración SQL correspondiente. |
| Reembolsos Wompi | `POST /subscriptions/refund` marca `status = "refund_requested"` y revoca PRO, pero **no ejecuta el reembolso monetario**. El TODO en línea 293 confirma que el endpoint de reembolsos de Wompi no está integrado. El reembolso real debe hacerse manualmente en el panel de Wompi. |
| Jobs sin scheduler | Los jobs existen como scripts Python pero no hay scheduler en el repositorio. El `docker-compose.yml` solo define Redis. La ejecución programada depende de infraestructura externa no documentada. |

### 7.4 Código que podría estar muerto

| Ubicación | Razón |
|-----------|-------|
| `services/providers/ai_agent/` | El AI Search Agent (LangGraph + DuckDuckGo + crawl4ai + Claude) solo se usa como fallback para Liga BetPlay cuando ESPN y football-data.org no tienen datos. Es un sistema complejo (~5 archivos) para un caso de uso muy acotado. |
| `services/match_stats_ingester.py` | Alternativa Playwright al `sofascore_ingester.py` HTTP. Ambos existen para el mismo propósito. No está claro cuál es el camino activo actualmente. |
| `services/providers/football_data_provider.py` | Backup para PL y LaLiga, pero ESPN ya cubre ambas ligas. Solo se usaría si ESPN falla para esos slugs. |

---

## 8. Rendimiento — patrón de queries

### 8.1 Hallazgo principal

El backend **no tiene N+1 clásico** (1 query por cada fila), pero sí tiene un patrón de **múltiples queries por tabla** con potencial de repetición entre requests.

### 8.2 `GET /api/v1/matches/` — 6 queries por request

| # | Query | Tabla |
|---|-------|-------|
| 1 | `SELECT * FROM matches WHERE ... ORDER BY match_date LIMIT 100` | matches |
| 2 | `SELECT * FROM teams WHERE id IN (...)` | teams (home) |
| 3 | `SELECT * FROM teams WHERE id IN (...)` | teams (away) |
| 4 | `SELECT * FROM leagues WHERE id IN (...)` | leagues |
| 5 | `SELECT * FROM predictions WHERE match_id IN (...) ORDER BY created_at DESC` | predictions |
| 6 | `SELECT * FROM bookmaker_odds WHERE match_id IN (...) AND bookmaker_name = 'api_football'` | bookmaker_odds |

- Las queries 2 y 3 consultan la misma tabla `teams` — son dos round-trips separados porque SQLAlchemy trata `home_team` y `away_team` como relaciones independientes.
- `bookmaker_odds`, `events`, `advanced_stats`, `referee` tienen `lazy="selectin"` a nivel modelo pero los endpoints las cargan manualmente (o no las cargan). Esto crea un riesgo de queries extra si algún código accede a esas relaciones sin pasar por el `selectinload` explícito.
- El uso de `selectinload` es correcto para evitar N+1 (número constante de queries independientemente de N).

### 8.3 `GET /api/v1/matches/{id}` — 9 queries por request

1 query principal + 7 `selectinload` (home_team, away_team, league, predictions, events, advanced_stats, referee) + 1 query manual para bookmaker_odds.

### 8.4 `GET /api/v1/matches/{id}/h2h` — ~11 queries

Incluye queries para el match principal, H2H history, y `recent_form()` para ambos equipos (2 queries cada uno: home + away).

### 8.5 Caché

**No hay caché en los endpoints de matches.** El `CacheService` existe y se usa en tickets y predicciones, pero los endpoints de matches (`matches.py`) no tienen dependencia de caché ni llamadas a Redis. Cada request a `/matches/`, `/{id}`, `/upcoming/`, `/{id}/h2h` va directo a PostgreSQL.

### 8.6 Explicación del síntoma "múltiples queries idénticas en ventana corta"

Lo que se observa en logs (múltiples llamadas a `GET /api/v1/matches/` con los mismos parámetros en <30s) es esperado si:
1. **Varios componentes del frontend** hacen fetching independiente del mismo endpoint (ej. página principal + sidebar + widget de próximos partidos).
2. **No hay deduplicación** de requests en el frontend (no hay React Query `staleTime`, no hay SWR `dedupingInterval`, no hay caché de servicio).
3. **No hay caché de backend** para matches.

Cada request ejecuta 6 queries SQL. Si 3 componentes frontend piden `/matches/` casi simultáneamente, son 18 queries SQL en una ventana de ~1 segundo.

### 8.7 Oportunidades de mejora (documentadas, no implementadas)

| Área | Severidad | Descripción |
|------|:---------:|-------------|
| Caché de matches | **Alta** | Agregar Redis caching a `/matches/` y `/{id}` con TTL de 30-60s eliminaría queries redundantes entre componentes frontend. |
| Dos queries a `teams` | Baja | `home_team` y `away_team` disparan queries separadas a la misma tabla. Se podría unificar con una subquery o `contains_eager`. |
| `bookmaker_odds` dual-load | Media | Modelo declara `lazy="selectin"` pero el endpoint lo carga manualmente filtrado. Si otro código accede a `match.bookmaker_odds`, dispara una query sin filtrar. |
| `/upcoming/` silent failure | Baja | Predictions no cargados → excepción silenciosa. Si en el futuro upcoming matches tienen predicciones, esto fallará sin warning. |

### 8.8 Logging SQL

- `echo=settings.DEBUG` en `db/database.py:17` — solo activo si `DEBUG=True`.
- En producción (`DEBUG=False`), **cero logging de queries SQL**.
- No se encontraron archivos `.log` en el proyecto.
- No se adjuntó archivo de log con el prompt — el análisis se basa en inspección de código.

---

## 9. Tests

### 9.1 Configuración

**Archivo:** `C:\betmind-ai\pytest.ini`
```ini
[pytest]
pythonpath = . apps/api packages/ml
testpaths = tests
python_files = test_*.py
asyncio_mode = auto
```

**Comando:** `pytest` (desde la raíz del proyecto)

### 9.2 Inventario de tests (~155 tests en 13 archivos)

| Archivo | Tests | Módulo(s) cubierto(s) |
|---------|:-----:|----------------------|
| `tests/test_ticket_builder.py` | 36 | `apps.api.engine.ticket_builder` |
| `tests/test_subscriptions.py` | 24 | Jobs reconcile, subscription_service, webhook, PRO status, auth |
| `tests/test_phase17_models.py` | 23 | `betmind_ml.models` (Dixon-Coles, corners, player props, MTI) |
| `tests/test_kelly_and_filters.py` | 22 | `betmind_ml` (Kelly, staking, EV thresholds, variance filters) |
| `tests/test_backtest_runner.py` | 19 | `betmind_ml` (calibration, simulation, metrics, runner, reports) |
| `tests/test_poisson_engine.py` | 6 | `betmind_ml.pipeline`, `betmind_ml.models.poisson_engine` |
| `tests/test_odds_parser_real_payload.py` | 5 | `apps.api.services.odds_service` |
| `tests/test_fuzzy_dedup.py` | 5 | Team name normalization, fuzzy dedup |
| `tests/test_match_dedup.py` | 4 | Match dedup (external ID, cross-provider, time-window) |
| `tests/test_full_analysis.py` | 4 | `betmind_ml.pipeline.full_analysis_pipeline` |
| `tests/test_ticket_bankroll.py` | 4 | Ticket status updates, bankroll movements, idempotency, rollback |
| `tests/test_ticket_repository.py` | 2 | `apps.api.repositories.ticket_repository` (atomic claims) |
| `tests/test_cache_resilience.py` | 1 | `apps.api.services.cache_service` |

### 9.3 Cobertura — lo que SÍ tiene tests

- `apps.api.engine.ticket_builder` — **alta** (36 tests)
- `apps.api.services.subscription_service` + jobs — **media** (24 tests)
- `betmind_ml.models` — **alta** (23 tests)
- `betmind_ml` (Kelly, backtesting, EV) — **alta** (41 tests combinados)
- `apps.api.services.odds_service` — **baja** (5 tests)
- `apps.api.repositories.ticket_repository` — **baja** (2 tests)
- `apps.api.services.cache_service` — **mínima** (1 test)

### 9.4 Cobertura — lo que NO tiene tests (cero)

| Categoría | Módulos sin tests |
|-----------|-------------------|
| **Routes** | `auth.py`, `backtesting.py`, `bankroll.py`, `leagues.py`, `matches.py`, `predictions.py`, `scanner.py`, `subscriptions.py` (endpoints), `tickets.py` (endpoints), `users.py` |
| **Services** | `api_football.py`, `auth_service.py`, `data_ingestion.py`, `llm_cascade.py`, `match_stats_ingester.py`, `sofascore_ingester.py`, `team_normalizer.py`, `wompi_service.py` |
| **Providers** | `espn_provider.py`, `football_data_provider.py`, `base_provider.py`, `provider_registry.py`, todo `ai_agent/` |
| **Repositories** | `base_repository.py`, `bookmaker_odd_repository.py`, `league_repository.py`, `match_repository.py`, `tactical_analysis_repository.py`, `team_repository.py` |
| **Models** | Todos (15 modelos) |
| **Schemas** | Todos (7 archivos) |
| **Orchestrators** | `prediction_orchestrator.py`, `scanner_orchestrator.py` |
| **Core** | `enums.py`, `exceptions.py`, `result.py` |
| **Engine** (except ticket_builder) | `kelly.py`, `corners_model.py`, `match_tension.py`, `player_props_model.py` |

### 9.5 Scripts de prueba manuales (no pytest)

| Archivo | Descripción |
|---------|-------------|
| `test_supabase_sync.py` | Conexión Supabase + verificación de sync |
| `scripts/test_tickets.py` | HTTP requests manuales a localhost:8000 |
| `scripts/test_api_football.py` | Fetch de odds de API-Football para un fixture |
| `tests/test_live_full_analysis.py` | End-to-end con Groq API real |

---

## Resumen ejecutivo

El backend de BetMind AI es una API REST en FastAPI con 35 endpoints, 15 tablas, y ~155 tests. La arquitectura es modular (routes → services → repositories → models) con inyección de dependencias. La base de datos usa SQLite en desarrollo local (`create_all`) y PostgreSQL en producción (migraciones SQL manuales). Las integraciones externas son 14, con distintos niveles de fallback (desde graceful degradation en Redis/email hasta error duro en API-Football/Wompi). El sistema de jobs (renovación y reconciliación de suscripciones) carece de scheduler en el repositorio. No hay caché en los endpoints de matches, lo que combinado con múltiples componentes frontend pidiendo los mismos datos explica la percepción de lentitud. Las rutas, servicios, modelos y esquemas carecen de tests automatizados (la cobertura se concentra en el motor ML y el ticket builder).
