# CONTEXTO DEL PROYECTO — BetMind AI (para revisión externa)

> Documento de contexto para el revisor externo (Claude). Léelo ANTES de la auditoría técnica.
> Complementa: `docs/auditoria-tecnica-2026.md` (detalle técnico) y `docs/prompt-claude-auditoria.md` (la crítica).

---

## 1. Qué es BetMind AI

**Terminal cuantitativa SaaS para apuestas deportivas** (no es un bot de trading): el usuario abre la app, ve partidos de su liga, recibe probabilidades reales calculadas por un modelo (Poisson bivariado), detecta apuestas con **Valor Esperado Positivo (+EV)** contra las cuotas del bookmaker, arma boletos multi-apuesta (parlays) y le sugiere cuánto apostar (Quarter-Kelly) y con qué nivel de riesgo.

Regla de oro del producto: **90 minutos**. Todo análisis excluye prórrogas y penales.

## 2. Propuesta de valor

"El mismo tipo de información que usa la casa": probabilidad real de cada evento vs la probabilidad implícita que cobra el bookmaker. Cuando la probabilidad del modelo supera a la del mercado por un margen suficiente, hay valor.

Público objetivo: apostador colombiano (y latinoamericano) minorista. Mercado local: BetPlay y ligas sudamericanas, más Big 5 europeas.

## 3. Modelo de negocio (freemium estricto)

| | Gratis | VIP (PRO) |
|---|---|---|
| Generación de boletos | 2/día | Ilimitada |
| Mercados visibles | 10 | Todos (~70) |
| Guardado de boletos | 5 | Sin límite (con stake y bankroll) |
| Análisis táctico (IA) | No | Sí |
| Precio | — | Mensual/anual vía **Wompi** en COP (2.990.000 y 24.990.000 centavos ≈ $29.900 / $249.900 COP) |

El estado PRO solo se concede vía **webhook firmado** de Wompi (APPROVED). No hay trial. Renovación fallida = revocación inmediata.

## 4. Producto — páginas del frontend (Next.js)

- `/` — Home: resumen, boletos destacados, partidos del día.
- `/partidos` — Listado de partidos por fecha (COT) + sidebar de ligas. Cada partido muestra cuotas reales, lambda (xG) del modelo y predicción guardada.
- `/partidos/[id]` — Detalle: probabilidades 1X2/O-U, análisis EV completo por mercado, análisis táctico (goles, tarjetas, córneres, bet builder), H2H, forma reciente, árbitro, stats avanzadas (xG, SOT, córneres).
- `/senales` — Escáner de oportunidades (hoy es un **stub** que devuelve vacío — el backend no implementa la búsqueda).
- `/generador` — Generador de boletos por modo: **EDGE** (conservador, 2 selecciones, cuotas 1.5-3.5), **VALUE** (3 selecciones, cuotas 2.5-12), **BOLD** (4 selecciones, cuotas 8-30). Filtros por liga, mercado y fecha. Valida correlaciones negativas entre selecciones.
- `/historial` — Boletos guardados con estado (PENDING/WON/LOST/VOID) y su impacto en bankroll.
- `/bankroll` — Gestión de bankroll con movimientos.
- `/planes` — Checkout Wompi (widget de tokenización, aceptación en Colombia).
- `/cuenta/*` — Auth con Supabase Auth (login/registro/resetear/olvidé password).

## 5. Stack técnico

- **Backend:** FastAPI (Python 3.11+, async), SQLAlchemy 2 async, Pydantic v2, Supabase Postgres, Redis (caché + rate limits slowapi).
- **Frontend:** Next.js App Router, Tailwind, SWR, tema Obsidiana + Menta.
- **ML:** paquete propio `packages/ml/betmind_ml` (Poisson bivariado + Dixon-Coles, mercados, EV, backtesting) — matemática pura, sin I/O.
- **IA:** Groq (llama-3.1-8b-instant) → Gemini (2.0-flash) → narrativa sintética. Claude sonnet solo en el agente de extracción de datos.
- **Infra:** GitHub Actions (cron cada 2h para sync + predicciones), Docker Compose (Redis local).

## 6. Cómo funciona el día a día (flujo operativo)

```
CADA 2 HORAS (GitHub Actions):
  1. scripts/sync_today_matches.py
     a. ESPN Scoreboard (via MatchFixtureScraper — ARCHIVO ELIMINADO, job roto)
        → ligas, equipos, partidos de la ventana -2h/+36h
     b. API-Football /odds → cuotas de todos los bookmakers (6s de throttle por partido)
     c. API-Football fixtures → fallback de marcadores/estados
  2. scripts/batch_predict.py --mode full --limit 150
     → ventana -2h/+36h, dedup, idempotencia (omite ya analizados)
     → por partido: pipeline cuantitativo (Poisson → mercados → EV con cuotas reales)
       + análisis táctico (Groq→Gemini→sintético, 400 tokens, JSON validado)
     → persiste predictions y tactical_analysis, cachea en Redis 6h

CUANDO UN USUARIO ENTRA (request-time):
  /partidos      → lee matches + cuotas + predicciones persistidas (DB)
  /partidos/[id] → prediction del orquestador (cache → DB → pipeline on-demand si no existe)
  /generador     → /tickets/generate: lee predicciones persistidas, arma boletos por modo
                   con validación de correlaciones y +EV; cache 30 min
  Guardar boleto → /tickets/save con límites free (2/día, 5 guardados)

ANTES DEL KICKOFF (cada ~10 min):
  jobs/clv_tracker.py → captura cuota de cierre 5-10 min antes del inicio
                        (API-Football → ESPN moneyline), calcula CLV vs apertura

FONDO (jobs):
  renew_subscriptions (renovaciones Wompi), reconcile_pending_subscriptions (pagos pendientes)
```

## 7. Reglas de negocio críticas

1. **90 minutos estricto**: `regulation_time_only=True` en todos los partidos; los eventos AET/PEN se marcan para excluirlos de stats.
2. **Cascada de datos A → B → C**: ESPN/football-data (oficiales) → scraper determinista (cero IA) → agente IA (último recurso). El primer resultado no vacío gana.
3. **El LLM nunca toca los números**: la predicción es 100% Poisson/EV; la IA solo redacta narrativa post-cálculo.
4. **Freemium estricto**: límites enforceados en backend (no solo en UI); el análisis táctico completo está gated por PRO.
5. **Sin trial y sin gracia**: PRO = webhook APPROVED; renovación fallida = baja inmediata.
6. **Anti-cáscara**: en ligas de alta varianza (BetPlay, Argentina, México, etc.) se rechazan favoritos con cuota < 1.25 (valor insuficiente para el riesgo).

## 8. Datos que maneja el modelo (por partido)

- Equipos: últimos 12 partidos (ventana con decaimiento 0.85^k), forma últimos 5, H2H últimos 6.
- Promedios de liga calculados sobre TODOS los partidos finalizados de la liga en DB.
- Cuotas reales de API-Football (1X2, O/U 0.5-3.5, BTTS, córneres, tarjetas, remates) — se guarda la mejor cuota entre bookmakers.
- Post-partido: SofaScore (xG, SOT, córneres, eventos, árbitro) cuando está disponible.
- No se usan alineaciones, bajas, lesiones, clima ni noticias (el agente IA de búsqueda existe pero solo como último recurso de datos y casi nunca se usa).

## 9. Estado actual

- **Fase 1 certificada**: checkout Wompi E2E, webhook con anti-replay y firma SHA-256, RLS en Supabase para tablas financieras, monitoreo CLV con advisory lock + optimistic concurrency, purga de código muerto.
- Backtesting disponible (walk-forward, Brier, ROI, calibración) pero **manual**.
- 18 archivos de tests (Poisson, EV, Kelly, tickets, odds parser con payloads reales, seguridad, paywall).
- Auditoría de seguridad anterior: 0 hallazgos críticos/altos; 2 medios resueltos.

## 10. Lo que se busca con esta revisión

1. ¿El edge +EV es real o ilusión (calibración, sobreajuste, mejor cuota de N bookmakers)?
2. ¿Las fórmulas y parámetros son defendibles o hay que recalibrar/reestimar?
3. ¿El stack de APIs (ESPN gratis + API-Football para cuotas + SofaScore) es el correcto, escalable y honesto?
4. ¿La arquitectura (cascada de datos, identidad multi-proveedor, jobs cada 2h) aguanta escala?
5. ¿Qué hay que arreglar HOY (P0) vs mañana (P1/P2)?

## 11. Qué NO es BetMind

- No es un bot que apuesta solo: recomienda y sugiere staking.
- No vende picks "seguros": es una terminal de análisis con números a la vista.
- No tiene trial: es freemium estricto con paywall server-side.
- No apuesta por el usuario ni guarda fondos (los pagos van directo a Wompi).
