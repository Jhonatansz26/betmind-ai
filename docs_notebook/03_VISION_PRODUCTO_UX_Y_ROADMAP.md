# 03 — Visión de Producto, UX y Hoja de Ruta Comercial de BetMind AI

> Documento de producto anclado al código real de `apps/web/` (componentes, `lib/`), el motor de tickets (`apps/api/engine/ticket_builder.py`) y la capa de persistencia de tickets.

---

## 1. Arquetipos de Usuario

### 1.1 Apostador Práctico ("quiero el boleto y copiarlo rápido")

- **Necesidad:** decisiones rápidas, sin fricción: un boleto combinado listo, con cuota total visible y un botón para copiarlo al portapapeles.
- **Superficie de UI que lo sirve:**
  - `TicketGenerator` (`ticket-generator.tsx`): botón `Copiar Boleto` (`#generator-copy-ticket`) que genera texto con cabecera `🎯 BetMind AI — Boleto {perfil}`, `📊 Cuota Combinada`, `💡 +EV Promedio`, `✅ Confianza IA`, legs `N. Local vs Visitante / Mercado @ cuota` y cierre `⚡ Generado por BetMind AI` (`navigator.clipboard.writeText` + toast de confirmación).
  - Perfiles de riesgo de un clic: **Conservador (EDGE)** / **Equilibrado (VALUE)** / **Agresivo (BOLD)** (`RISK_PROFILES`) con presets de cuota combinada (`1.5–3.0`, `3.0–6.0`, `6.0+`).
  - `Guardar en Seguimiento` para no perder el ticket.
- **Disclaimers presentes en UI:** "Probabilidades estimadas por modelo Poisson + IA. No constituye asesoría financiera." y "Confianza basada en datos de 90 min. No es asesoría financiera." — el producto se posiciona como herramienta de análisis, no de consejo.

### 1.2 Apostador Visual ("entiendo con gráficas e imágenes")

- **Necesidad:** asimilar probabilidad sin leer tablas; comparar equipos de un vistazo.
- **Superficie de UI que lo sirve:**
  - `PoissonMiniChart` (`poisson-mini-chart.tsx`): histograma SVG determinista (server/client) de distribución de goles por equipo — **barras del local en indigo** (`var(--primary)`), **visitante en ámbar** (`var(--warning)`), buckets `0, 1, 2, 3, 4+` (columna 4+ = probabilidad acumulada restante vía `goalDistribution()`). Es "la firma visual" del producto y aparece en cada `MatchCard` (también en `score-heatmap.tsx` para matrices de marcador).
  - `MatchCard` (`match-card.tsx`): jerarquía clara de hora COT, logos de equipo, `1 2 X` chips con probabilidad del modelo, badge `COPA` para `KNOCKOUT_CUP` y marcador EN VIVO/PAUSADO/FINALIZADO.
  - `ScoreHeatmap` (`score-heatmap.tsx`), `MatchComparisonBars` (`match-comparison-bars.tsx`), `ConfidenceBar` (`confidence-bar.tsx`), `TrendPills` (`trend-pills.tsx`) — capa de visualización de datos del detalle de partido.
  - Filtros rápidos del dashboard (`dashboard.tsx`): `⚡ Alta Confianza (>75%)` y `🔥 Mejor Valor (EV+)`.

### 1.3 Apostador Analítico / Pro ("quiero ver el razonamiento y el EV")

- **Necesidad:** transparencia total: por qué se eligió cada selección, el desglose del modelo Poisson, EV%, confianza, y herramientas de validación (backtesting, H2H, análisis táctico, árbitro).
- **Superficie de UI que lo sirve:**
  - `MarketTable` (`market-table.tsx`) con filas por mercado: probabilidad real, cuota, probabilidad implícita, edge, EV y veredicto (`EV+ | MARGINAL | NO EDGE | AVOID` — calculado por `marketRows()` en `lib/betmind.ts`).
  - Sección "Por qué esta selección" + `rationale` chips en `ticket-card.tsx` y `ticket-generator.tsx`.
  - Página de detalle `app/partidos/[id]/page.tsx`: `TacticalPanel` (narrativas de goles/tarjetas/córneres con pros/cons y señal), `RefereeWidget` (estadísticas del árbitro), `BetBuilderCards` (combinadas con correlación), `PoissonModalChart`, H2H (`fetchMatchH2H`) y forma reciente.
  - Backtesting admin (`POST /api/v1/backtesting/{league_key}`) para validación walk-forward del modelo.

---

## 2. Jerarquía de Componentes UI (árbol real en `apps/web/components/betmind/`)

```
app/page.tsx  (Dashboard)
├── TopNav (top-nav.tsx)
├── DateSelector (date-selector.tsx) · LeagueSidebar (league-sidebar.tsx) / LeagueAccordion
├── ModeSelector (mode-selector.tsx) · MatchTabBar (match-tab-bar.tsx)
├── Dashboard (dashboard.tsx)                ← orquesta cartelera + tickets + tracking
│   ├── MatchCard (match-card.tsx)           ← tarjeta de partido en la cartelera
│   │   ├── PoissonMiniChart (poisson-mini-chart.tsx)   ← histograma xG local/visitante
│   │   ├── TeamLogo (components/ui/team-logo.tsx)
│   │   ├── EvBadge (ev-badge.tsx) · OddsPill (odds-pill.tsx) · ConfidenceBar
│   │   └── InsufficientDataCard (insufficient-data-card.tsx)
│   ├── TicketGenerator (ticket-generator.tsx)          ← configurar + generar boleto
│   │   ├── GeneratorLeg (leg: mercado, partido, +EV%, cuota)
│   │   └── (usa fetchTickets → POST /api/v1/tickets/generate)
│   ├── TicketCard (ticket-card.tsx)                    ← boleto generado por modo
│   │   ├── ConfidenceBar · TicketLeg (ticket-leg.tsx)
│   │   └── Sección "Por qué esta selección" (rationale)
│   └── TrackingPanel (tracking-panel.tsx)              ← historial de boletos
│       ├── TrackRow (estado PENDING/WON/LOST/VOID clicable)
│       └── (usa fetchTicketHistory/saveTicket/updateTicketStatus + localStorage fallback)

app/partidos/[id]/page.tsx  (Detalle de partido)
├── MatchHeader (equipos, hora COT, estado, tipo LEAGUE/KNOCKOUT_CUP)
├── MarketTable (market-table.tsx)                      ← tabla EV completa
├── ScoreHeatmap (score-heatmap.tsx) · MatchComparisonBars
├── TacticalPanel (tactical-panel.tsx)                  ← análisis táctico (Fase 4)
│   └── TrendPills · RefereeWidget (referee-widget.tsx)
├── BetBuilderCards (bet-builder-cards.tsx)             ← perfiles de combinada
├── PoissonModalChart (poisson-modal-chart.tsx)
└── ScannerEmptyState (scanner-empty-state.tsx)
```

**Roles de los 5 componentes clave solicitados:**

| Componente | Rol | Props → Estado |
|---|---|---|
| `ticket-generator.tsx` | Generador configurable de boletos | `matches: Match[]`, `onTrack`; estado `GeneratorConfig { selectionCount (2–7), riskProfile (conservative/balanced/aggressive), oddsMin/oddsMax, marketCategory (all/goals/corners/cards/shots) }`; regenera vía `fetchTickets([mode])` y filtro de legs por categoría + límite de selecciones |
| `ticket-card.tsx` | Tarjeta pasiva de un boleto con explicabilidad | `ticket: Ticket`, `onTrack`; franja de acento del modo, `@ cuota combinada`, `ConfidenceBar`, "+EV promedio", "Por qué esta selección", legs con `TicketLeg`, footer "Añadir a Seguimiento" |
| `match-card.tsx` | Tarjeta de partido con banner de valor | `match: Match`; `buildModel()` → `marketRows()` → `bestOpportunity()` (edge ≥ 3%); banner `👉 [Mercado] · prob% · @cuota · 🔥 EV+` solo si `SCHEDULED && best != null && hasLambda`; sub-strip "Poisson calibrado · EV real X% · Confianza X%" |
| `tracking-panel.tsx` | Historial y seguimiento de boletos | `refreshKey`; fuente primaria remota (`/tickets/history`) con fallback `localStorage` (`betmind_tracked_tickets`); ciclo de estados `PENDING→WON→LOST→VOID`; contadores pendiente/ganado/perdido |
| `poisson-mini-chart.tsx` | Visualización firma: histograma de goles | `lambdaHome`, `lambdaAway`, `width=120`, `height=48`; `goalDistribution(lambda, 5)`; geometría redondeada a 2 decimales para render determinista SSR |

---

## 3. Mecanismos de Transparencia (Explicabilidad)

El producto hace visible la cadena **datos → modelo → decisión**:

1. **"Por qué esta selección"** (`ticket-card.tsx:61`): chips `rationale` construidos en `mapBackendTicket()` (`apps/web/lib/api.ts:216`):
   - `Modelo Poisson calibrado`
   - `+{ev}% EV medio`
   - `{confidence}% de confianza del modelo`
   - `Validación de correlación negativa superada` o `Selecciones independientes, sin correlación detectada`
   - Más el título de seguridad: `Filtros y seguridad: {ticket.correlation}`.
2. **Desglose del modelo Poisson:** cada leg muestra `{leg.ev}% EV` y la etiqueta `Cuota real · Poisson calibrado` (tooltip: "Cuota real comparada contra el modelo Poisson"); el `TicketGenerator` muestra `Razonamiento de la IA` como chips y el snippet `Análisis IA` (`ticket.analysis`).
3. **EV% y confianza:** stats row del generador (`Confianza IA %`, `+EV Promedio`, `Rango En/Fuera de rango`), `EvBadge`, `ConfidenceBar` y, en `match-card.tsx`, la línea de evidencia `Poisson calibrado · EV real X.X% · Confianza X%` bajo el banner.
4. **Honestidad de mercados sin cuotas:** `NO_ODDS_AVAILABLE` en la API y filtros que no inventan valor; en UI el estado "SIN EDGE" y el mensaje "El modelo no detectó oportunidades +EV…" cuando no hay selecciones.
5. **Riesgo declarado:** cons de cada ticket ("Lower confidence legs…", "High combined odds — expect high variance outcomes", "Past model performance does not guarantee future results"), narrativa táctica con `pros`/`cons` por mercado (`ProConPoint` con peso high/medium/low) y nivel de riesgo `LOW/MEDIUM/HIGH`.
6. **Backtesting público del modelo:** endpoint admin `POST /backtesting/{league_key}?season=` con métricas walk-forward (`betmind_ml.backtesting.*`), base para publicar track record.

---

## 4. Hoja de Ruta Comercial

### Fase 1 — Gratuita (acumulación de track record server-side) — IMPLEMENTADA EN CÓDIGO

El motor de confianza de la Fase 2 ya existe como infraestructura:

- **Persistencia remota:** `POST /api/v1/tickets/save` → tabla `saved_tickets` (JSONB `ticket_data`, `total_odds`, `total_ev`, `status`) con RLS en Supabase (migración 012 + política en 010). `GET /api/v1/tickets/history` y `PATCH /api/v1/tickets/{id}/status` permiten liquidar cada boleto (`PENDING → WON/LOST/VOID`).
- **Fallback local:** `localStorage` (`betmind_tracked_tickets`, máx. 10) solo cuando la API no responde (`addToTracking` → `saveTicket` primero).
- **Track record acumulable:** con el historial server-side se puede computar yield, hit-rate por modo (`EDGE/VALUE/BOLD`), EV medio vs resultado real, ROI por liga — la base honesta del marketing ("confianza basada en datos de 90 min").
- **Modo sin cuenta:** los endpoints de auth (`/auth/register`, `/auth/login`) son stubs 501 — el producto gratuito es de uso anónimo total.

### Fase 2 — SaaS VIP (roadmap producto, apalancado en la arquitectura existente)

| Feature VIP | Apalancamiento técnico actual |
|---|---|
| **Alertas de Telegram** | Los boletos ya se generan programáticamente cada 2h (workflow `daily_predictions.yml` + `batch_predict.py`); falta un suscriptor que envíe `TicketGenerateResponse` a un bot (nuevo servicio; los datos ya están cacheados en Redis con TTL 30 min) |
| **Gestión de banca (bankroll)** | Ya existe Quarter-Kelly por leg (`kelly_stake`) y combinada (`_calculate_combined_kelly` = mínimo de Kelly de las piernas) + sugerencia de stake legible; falta asociar `saved_tickets` a un `user_id` (auth real reemplazando los stubs 501) |
| **Límites de parlay por plan** | El motor ya limita `max_selections` por modo (EDGE 2 / VALUE 3 / BOLD 4) y rangos de cuota objetivo; el plan VIP puede exponer estos mismos parámetros como configuración por plan (los presets existen en `ODDS_PRESETS` y `RISK_PROFILES`) |
| **Perfil Pro (Analítico)** | Backtesting admin, `MarketTable`, H2H, análisis táctico Fase 4 (narrativas + árbitro + bet builder) ya construidos; desbloqueo por plan |

**Norte de producto:** convertir el track record acumulado en Fase 1 en el activo principal de Fase 2 — transparencia total del modelo Poisson calibrado + EV real, monetizada como SaaS de alertas y gestión de banca, nunca como "tipster".

---

## 5. Métricas de producto sugeridas (derivables de datos actuales)

- `saved_tickets`: ROI, hit rate, EV medio vs yield real, distribución por `mode`.
- `predictions.value_score` + `lambda_home/lambda_away`: calibración del modelo (Brier score, accuracy de Over 2.5).
- `matches.match_type`: volumen y rendimiento LEAGUE vs KNOCKOUT_CUP.
- `bookmaker_odds`: mejor línea promedio vs cuota de cierre (calidad del sourcing).
