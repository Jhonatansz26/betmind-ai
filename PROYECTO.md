# BetMind AI — Documento del Proyecto

> Documento único y vivo del monorepo. Para historial detallado de desarrollo ver `docs/archive/PROJECT_LOG.md`.

## Visión

**BetMind AI** es una terminal cuantitativa SaaS para apuestas deportivas: calcula la probabilidad real de cada evento (modelo Poisson bivariado) para detectar apuestas con **Valor Esperado Positivo (+EV)**, con el mismo tipo de información que usa la casa.

- **Regla estricta de 90 minutos:** todo análisis excluye prórrogas/tiempos extra.
- **Ligas objetivo:** Liga BetPlay (Colombia), Premier League, LaLiga (+ ligas sudamericanas vía ESPN).
- **Modelo de negocio:** Freemium estricto — acceso free limitado (2 boletos/día, 10 mercados) + suscripción VIP mensual/anual vía Wompi (COP).

## Estructura del monorepo

| Directorio | Rol |
|---|---|
| `apps/api` | Backend FastAPI (Python 3.11+, SQLAlchemy 2 async, Pydantic v2) |
| `apps/web` | Frontend Next.js (App Router, Tailwind, diseño Obsidiana + Menta Técnica) |
| `packages/ml` | Motor cuantitativo (`betmind_ml`): Poisson, Kelly, filtros +EV |
| `scripts` | Automatizaciones (los que usa el CI se conservan) |
| `tests` | Tests del backend (pytest) |
| `.github/workflows` | CI: predicciones diarias cada 2h |

## Cómo correr

```bash
# Backend (puerto 8000)
python -m uvicorn apps.api.main:app --reload --port 8000

# Frontend (puerto 3000)
cd apps/web && npm run dev

# Redis local (opcional)
docker compose up -d redis

# Tests
pytest tests/ -q

# Jobs manuales
python -m apps.api.jobs.clv_tracker            # captura de CLV 5-10min antes del kickoff
python -m apps.api.jobs.renew_subscriptions    # renovaciones recurrentes
python -m apps.api.jobs.reconcile_pending_subscriptions  # reconcilia pagos pendientes
```

**Env:** copiar `.env.example` → `.env` (backend, raíz) y `apps/web/.env.local`. Secretos: `SECRET_KEY`, `DATABASE_URL` (Supabase), `API_FOOTBALL_KEY`, `WOMPI_*`, `GROQ_API_KEYS`, `REDIS_URL`.

## Arquitectura clave

### Ingesta de datos — Cascada estricta (A → B → C)

| Plan | Fuente | Notas |
|---|---|---|
| A | ESPN Scoreboard → football-data.org → API-Football | Proveedores oficiales |
| B | `scrapers/espn_summary_scraper.py` | Determinista, JSON estricto, retries/backoff, cero IA |
| C | Agente IA (LangGraph + DuckDuckGo + crawl4ai) | Solo si A y B fallan/vacíos |

**Cuotas (desde 2026-08):** cascada ESPN → SofaScore → API-Football.
- ESPN (`EspnOddsService`): 1X2 + Over/Under (summary por evento, sin key).
- SofaScore (`SofaScoreOddsService`): mercados especiales — córneres, tarjetas,
  remates a puerta y BTTS (odds fraccionarias → decimal, línea en `choiceGroup`,
  solo Full-time y no suspendidos; resolución de evento por búsqueda de equipo).
- API-Football: solo copas sin slug ESPN o partidos sin cuotas.
Se persisten con `bookmaker_name='espn'` / `'sofascore'` / `'api_football'`;
las lecturas toman el MEJOR precio por mercado entre las tres fuentes. Todo el
fetching pasa por Redis (scoreboard 15m, summary 30m, búsqueda equipo 24h,
eventos/odds SofaScore 30m).

Stats post-partido: SofaScore (Plan A, payloads cacheados en Redis 6h) → ESPN
Summary fallback; API-Football solo como primera pasada en
`ingest_match_statistics`.

### Monetización — Freemium estricto

- **Frontend:** checkout Wompi con elementos seguros (widget `checkout.wompi.co/widget.js`, modo `tokenize`); acceptance tokens vía `GET /v1/merchants/{key}`; paywall blur + truncado server-side (10 mercados free).
- **Backend:** `POST /api/v1/subscriptions/activate` crea registro **PENDING**; solo el **webhook firmado** (`/api/v1/webhooks/wompi`) asciende a VIP en `APPROVED`.
- **Seguridad del webhook:** firma SHA-256 (`signature.properties` + timestamp + `WOMPI_EVENTS_SECRET`), comparación `hmac.compare_digest` (constante en tiempo), **anti-replay** (|now − timestamp| > 5 min → 408 "Evento expirado").
- **RLS en Supabase:** `subscriptions` y `subscription_transactions` con políticas `SELECT` solo para `authenticated` (vía `users.auth_uid`); cero políticas de escritura para clientes (las escribe el backend con rol `postgres`/BYPASSRLS).

### Motor cuantitativo

- `packages/ml/betmind_ml`: Poisson bivariado, probabilidades de mercado, edge/EV, Kelly fraction, bet builder con validación de correlación.
- Análisis táctico (LLM) gated por suscripción (`is_effectively_pro`); bypass `X-Betmind-Dev-Pro` solo con `DEBUG=true`.

### Monitoreo CLV (Closing Line Value)

- `jobs/clv_tracker.py`: captura la cuota de cierre 5-10 min antes del kickoff (ventana estricta), cascada API-Football → ESPN moneyline.
- Concurrencia: `pg_try_advisory_lock` (escaneo) + **Optimistic Concurrency Control** en el UPDATE (`WHERE closing_odds_captured_at IS NULL` + rowcount → colisión = skip).
- CLV por mercado: `(opening_odds / closing_odds) − 1`, media en `matches.clv_value` (JSONB `closing_odds` + `DOUBLE PRECISION`).

## Estado actual — Fase 1 ✅ (certificada)

- Freemium estricto sin trial; checkout Wompi E2E; webhook con anti-replay.
- Cascada de ingesta con scraper determinista BetPlay.
- Monitoreo CLV operativo; RLS en tablas financieras.
- Auditoría de seguridad: 0 hallazgos críticos/altos; 2 medios resueltos (replay + carrera CLV).
- Purga de código muerto y scripts one-off completada.

## Decisiones importantes

- **Trial eliminado:** el tier VIP solo se otorga por webhook `APPROVED`; renovación fallida = revocación inmediata (sin gracia).
- **xG:** no disponible en ESPN → `None` en stats (SofaScore lo provee cuando puede).
- **Rate limits:** API-Football ~10 req/min → throttle de 6s entre fixtures SOLO en el fallback (ESPN no tiene límite de key; el cache Redis evita abusar).
- **RLS en `users`:** sin política SELECT para `authenticated` (la app lee `/users/me` vía FastAPI) — revisar si se conecta un cliente Supabase directo.
