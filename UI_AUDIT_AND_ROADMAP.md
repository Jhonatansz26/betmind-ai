# BetMind AI — Auditoria General de UI/UX y Plan de Rediseno

> **Fecha:** 2026-07-30  
> **Alcance:** Inspeccion visual completa de Partidos, Boletos, Modal de Analisis, Sidebar y Navegacion.  
> **Metodologia:** Puppeteer MCP + Skills (`frontend-design`, `web-design-guidelines`, `emil-design-eng`).  
> **Regla:** NO se modifico ningun archivo durante esta auditoria. Solo inspeccion.

---

## 1. Diagnostico General de Diseno

| Dimension | Puntaje (1–10) | Observacion |
|-----------|---------------|-------------|
| Paleta de colores | **7/10** | Dark theme zinc solido. Sistema de tokens semanticos bien definido en `globals.css` (`--positive`, `--warning`, `--primary`). **Problema:** Hardcodeo de `text-indigo-400`, `bg-zinc-900/60`, `text-amber-400` en `top-nav.tsx:43`, `page.tsx` (detail), y `match-comparison-bars.tsx` rompe la consistencia. |
| Tipografia y alineacion | **6/10** | `font-sans` (Inter) + `font-mono` (tabular-nums) bien aplicados a datos. **Problema:** Jerarquia de headings ausente en pagina de detalle (sin `<h1>`). Labels de seccion usan `<p>` en lugar de `<h2>`–`<h4>` en `league-sidebar.tsx`, `match-comparison-bars.tsx`, `insufficient-data-card.tsx`. |
| Gestion de espacios | **6/10** | Tarjetas de partidos consistentes a 128px tras rediseno. **Problema:** Mix de `gap` y margenes manuales (`mt-2`, `mb-3`) en `league-sidebar.tsx:127` y `match-comparison-bars.tsx:51`. Ancho de columna de tiempo (90px) apenas cabe con timezone incluido ("3:30 PM COT"). |
| Accesibilidad | **4/10** | Varios gaps criticos: `date-selector.tsx` sin `role="radiogroup"`, `match-tab-bar.tsx` sin `role="tablist"`, iconos sin `aria-hidden` en `top-nav.tsx`, visualizaciones sin `aria-label` en `match-comparison-bars.tsx`. |
| Microinteracciones | **5/10** | Live pulse dot funcional. EV+ glow implementado. **Problema:** Sin soporte `prefers-reduced-motion`. Sin `touch-action: manipulation`. Sin `:active` scale en botones. |
| **TOTAL** | **6.0/10** | Base solida, pero con deuda de accesibilidad y consistencia de tokens. |

---

## 2. Desglose de Fallos Visuales por Seccion

### 2.1 Vista Partidos (`/` tab Partidos)

| # | Problema | Ubicacion | Severidad |
|---|----------|-----------|-----------|
| 1 | **Timezone en columna de tiempo** — "3:30 PM COT" ocupa ~85px de los 90px disponibles. En vista movil se desbordara. | `match-card.tsx:75` | Media |
| 2 | **MatchSkeleton desactualizado** — El skeleton de carga sigue usando el layout antiguo de 3 columnas desiguales (20%/50%/30%), no coincide con el nuevo MatchCard de 90px/flex-1/180px. | `dashboard.tsx:57-96` | Alta |
| 3 | **Ligas duplicadas en pills** — El filtro horizontal de ligas muestra entradas duplicadas (ej. "Liga Profesional Argentina" aparece dos veces si los datos vienen con diferente `leagueExternalId`). | `dashboard.tsx:179-204` | Media |
| 4 | **Sin tabs visuales Hoy/Mañana** — El `DateSelector` es un segmented control sutil que facilmente se pasa por alto. No hay separacion visual clara entre partidos de hoy y mañana. | `dashboard.tsx:318` | Baja |
| 5 | **Estado SCHEDULED sin badge** — Los partidos programados no muestran ningun badge de estado (solo hora). Seria util un indicador sutil "PROGRAMADO" o "POR JUGAR" en hover. | `match-card.tsx:47-51` | Baja |
| 6 | **SVGs sin dimensiones explicitas** — Los 36 SVGs en pagina (PoissonMiniChart + team logos) no declaran `width`/`height` en algunos casos, causando CLS potencial. | `poisson-mini-chart.tsx`, `team-logo.tsx` | Baja |

### 2.2 Vista Boletos (`/` tab Boletos)

| # | Problema | Ubicacion | Severidad |
|---|----------|-----------|-----------|
| 1 | **Truncado agresivo de nombres** — "Central Cordoba (Santiago del Estero" se corta a mitad. Los nombres de equipos en `TicketLeg` necesitan `truncate` con `min-w-0` confirmado, pero el texto sigue siendo muy largo para 411px. | `ticket-leg.tsx:19` | Alta |
| 2 | **Solo 2 tickets generados** — No hay ticket BOLD. La grid `xl:grid-cols-3` se ve vacia con solo 2 tarjetas. Considerar centrado o grid adaptable. | `dashboard.tsx:290` | Media |
| 3 | **Ancho de ticket inconsistente** — 411px en una grid de 3 columnas deja ~120px vacios a la derecha de cada tarjeta. | `ticket-card.tsx:26` | Media |
| 4 | **Icono StarIcon sin aria-hidden** — El `StarIcon` dentro del boton "Anadir a Seguimiento" no tiene `aria-hidden="true"`, causando anuncio duplicado en lectores de pantalla. | `ticket-card.tsx:78` | Alta |
| 5 | **Texto legal ilegible** — "Confianza basada en datos de 90 min..." en `text-[10px] text-subtle` es practicamente invisible en dark mode. | `ticket-card.tsx:82` | Baja |
| 6 | **ConfidenceBar sin contexto** — "56/100" no explica que significa. Falta un tooltip o label descriptivo. | `ticket-card.tsx:56` | Baja |

### 2.3 Pagina de Analisis Detallado (`/partidos/[id]`)

| # | Problema | Ubicacion | Severidad |
|---|----------|-----------|-----------|
| 1 | **Sin `<h1>`** — La pagina no tiene heading principal. El titulo "Envigado FC vs Once Caldas" es texto plano. Esto rompe la jerarquia de accesibilidad y el SEO. | `apps/web/app/partidos/[id]/page.tsx` | Alta |
| 2 | **Hardcodeo masivo de colores** — `bg-zinc-900/60`, `text-indigo-400`, `text-amber-400`, `text-emerald-400`, `text-rose-400`, `text-zinc-*` aparecen +80 veces. Ninguno usa tokens semanticos del design system. Esto hace imposible theming futuro. | `page.tsx` (todo el archivo) | Critica |
| 3 | **Tab navigation custom** — La pagina implementa sus propios tabs (Previa, H2H, Arbitro) con estado local React, en lugar de usar `match-tab-bar.tsx`. Duplica codigo y rompe consistencia visual. | `page.tsx:43, ~1200` | Alta |
| 4 | **Tab buttons sin aria** — Los botones de tab no tienen `role="tab"`, `aria-selected`, ni `aria-controls`. Son `<button>` planos con estado visual solamente. | `page.tsx` (render de tabs) | Alta |
| 5 | **EV Table sin datos edge** — Para partidos sin EV+, la tabla muestra 5 filas de "NO EDGE". No hay indicacion visual de que el modelo no encontro valor. | `page.tsx:445-557` | Media |
| 6 | **TeamLogo inconsistente** — Usa `<TeamLogo size={40}>` en el hero pero `<TeamLogo size={24}>` en las tarjetas. La diferencia es aceptable pero el padding alrededor de logos de 40px crea desbalance visual. | `page.tsx:337, 363` | Baja |
| 7 | **NarrativeBody con emojis** — Los iconos de secciones (Goles, Tarjetas, Corners) usan emojis (⚽, 🟨, 📐) que se renderizan distinto en cada SO. Deberian usar lucide-react icons. | `page.tsx:224-228` | Media |
| 8 | **ModelProbabilities nombres cortos** — `match.home.split(' ')[0]` produce "Central" para "Central Cordoba", que es ambiguo. Deberia usar abreviacion controlada. | `page.tsx:766` | Baja |

### 2.4 Barra de Navegacion y Sidebar

| # | Problema | Ubicacion | Severidad |
|---|----------|-----------|-----------|
| 1 | **Badge "AI" hardcodeado** — `border-indigo-500/30 bg-indigo-500/20 text-indigo-400` en vez de usar `--primary`. | `top-nav.tsx:43-44` | Media |
| 2 | **Iconos sin aria-hidden** — `<MenuIcon />`, `<TicketIcon />` y otros lucide icons dentro de botones con `aria-label` necesitan `aria-hidden="true"` para evitar doble anuncio. | `top-nav.tsx:36, 91-109` | Alta |
| 3 | **Bottom nav duplica Top nav** — En mobile, ambos existen simultaneamente. El Top nav tiene tabs horizontales y el Bottom nav tambien. Uno deberia ocultarse. | `dashboard.tsx:239, 379` | Media |
| 4 | **Sidebar headings como `<p>`** — "Ligas Activas", "EUROPA", "AMERICA", "Estado del Modelo" son `<p>` en vez de `<h2>`/`<h3>`. | `league-sidebar.tsx:102, 31, 129` | Media |
| 5 | **DateSelector sin ARIA** — El control segmentado Hoy/Mañana/Todos no tiene `role="radiogroup"` ni `role="radio"` ni `aria-checked`. | `date-selector.tsx:23-25` | Critica |

---

## 3. Propuesta de Sistema de Diseno Unificado

### 3.1 Estructura de Tarjetas Estandarizada

```
┌──────────────────────────────────────────────────────────────┐
│ [90px]         │ [flex-1]                │ [180px]           │
│ TIME           │ TEAM ROW 1             │ EV+ / SIN EDGE    │
│ STATUS BADGE   │ TEAM ROW 2             │ 1 X 2 ODDS        │
│                │ MODEL SUB-STRIP        │ VER ANALISIS ->   │
└──────────────────────────────────────────────────────────────┘
```

- **MatchCard:** Layout horizontal de 3 columnas ya implementado. Pendiente: ajustar columna de tiempo a 100px para acomodar timezone.
- **TicketCard:** Migrar a grid de 2 columnas en desktop (`grid-cols-[1fr_auto]`) con altura minima fija (`min-h-[320px]`) para evitar desbalance visual con pocos tickets.
- **Skeleton:** Actualizar `MatchSkeleton` para reflejar el nuevo layout de 3 columnas.

### 3.2 Guia de Badges y Microinteracciones

| Badge | Diseno | Animacion |
|-------|--------|-----------|
| **EV+** | `rounded-full border border-positive/30 bg-positive/10 text-positive shadow-[0_0_12px_-4px_var(--positive)]` | Pulso sutil en el glow cada 3s |
| **LIVE** | `rounded-full border border-positive/30 bg-positive/10` + `live-dot` animado | `live-pulse` 1.4s ease-in-out |
| **FINALIZADO** | `rounded-full border border-muted bg-muted/60 text-muted-foreground` | Sin animacion |
| **SIN EDGE** | `text-[11px] text-subtle tracking-wide` | Sin animacion |
| **MODO EDGE/VALUE/BOLD** | `rounded-md border px-2 py-1 text-[11px]` con colores de `MODE_META` | Sin animacion |

**Reglas de microinteraccion (emil-design-eng):**
- `transition: transform 160ms ease-out, opacity 160ms ease-out` (nunca `transition: all`)
- `:active { transform: scale(0.97) }` en todos los botones
- `@media (prefers-reduced-motion: reduce)` para deshabilitar animaciones de movimiento
- `touch-action: manipulation` en elementos interactivos moviles

### 3.3 Paleta de Colores — Migracion a Tokens Semanticos

**Hardcodeos a eliminar:**

| Actual | Reemplazo |
|--------|-----------|
| `bg-zinc-900/60` | `bg-card` |
| `text-zinc-400`, `text-zinc-500` | `text-subtle` / `text-muted-foreground` |
| `text-indigo-400`, `bg-indigo-500/15` | `text-primary`, `bg-primary/15` |
| `text-amber-400`, `bg-amber-500/15` | `text-warning`, `bg-warning/15` |
| `text-emerald-400`, `bg-emerald-500/15` | `text-positive`, `bg-positive/15` |
| `text-rose-400`, `bg-rose-500/15` | `text-negative`, `bg-negative/15` |
| `border-zinc-800/80` | `border-border` |
| `border-zinc-700/50` | `border-border` |

### 3.4 Componentes a Unificar

| Componente actual | Problema | Componente unificado |
|-------------------|----------|---------------------|
| Tabs en `page.tsx` (detail) | Custom, sin ARIA | `MatchTabBar` con `role="tablist"` |
| Tabs en `match-tab-bar.tsx` | Falta `role="tablist"` | `MatchTabBar` corregido |
| `DateSelector` | Sin `role="radiogroup"` | `SegmentedControl` con ARIA |
| `StatusPill` + `StatusBadge` (2 variantes) | Duplicado | `MatchStatusBadge` unico |
| Labels de seccion como `<p>` | Semanticamente incorrecto | `SectionHeading` (`<h3>`) |

---

## 4. Roadmap de Implementacion en Fases

### Fase 1: Correcciones Criticas (Accesibilidad + Bugs)

**Objetivo:** Cero errores de accesibilidad, eliminar bugs visuales que rompen la experiencia.

| # | Tarea | Archivos | Prioridad |
|---|-------|----------|-----------|
| 1.1 | Agregar `role="radiogroup"`, `role="radio"`, `aria-checked` al `DateSelector` | `date-selector.tsx` | P0 |
| 1.2 | Agregar `role="tablist"` al contenedor de `MatchTabBar` + vincular `aria-controls` con `tabpanel` | `match-tab-bar.tsx` | P0 |
| 1.3 | Agregar `aria-hidden="true"` a todos los iconos dentro de botones con `aria-label` | `top-nav.tsx`, `ticket-card.tsx` | P0 |
| 1.4 | Agregar `<h1>` a la pagina de detalle de partido | `apps/web/app/partidos/[id]/page.tsx` | P0 |
| 1.5 | Actualizar `MatchSkeleton` al nuevo layout de 3 columnas (90px / flex-1 / 180px) | `dashboard.tsx:57-96` | P0 |
| 1.6 | Reemplazar badge "AI" hardcodeado con tokens semanticos | `top-nav.tsx:43-44` | P0 |
| 1.7 | Agregar `aria-label` a visualizaciones (`role="img"`) | `match-comparison-bars.tsx` | P1 |
| 1.8 | Convertir labels de seccion a headings (`<h2>`–`<h4>`) | `league-sidebar.tsx`, `match-comparison-bars.tsx`, `insufficient-data-card.tsx` | P1 |

### Fase 2: Rediseno de Componentes Base (Partidos + Boletos)

**Objetivo:** Consistencia visual total, eliminar hardcodeo de colores, estandarizar layouts.

| # | Tarea | Archivos | Prioridad |
|---|-------|----------|-----------|
| 2.1 | Migrar pagina de detalle a tokens semanticos (eliminar ~80 hardcodeos `text-zinc-*`, `bg-zinc-*`) | `apps/web/app/partidos/[id]/page.tsx` | P0 |
| 2.2 | Reemplazar tabs custom en pagina de detalle con `MatchTabBar` unificado | `page.tsx` + `match-tab-bar.tsx` | P0 |
| 2.3 | Redisenar `TicketCard` con altura minima fija y grid adaptable a numero de tickets | `ticket-card.tsx` | P1 |
| 2.4 | Mejorar truncado de nombres de equipos en `TicketLeg` (elipsis + tooltip en hover) | `ticket-leg.tsx` | P1 |
| 2.5 | Reemplazar emojis en `NarrativeBody` con iconos de lucide-react | `page.tsx:224-228` | P1 |
| 2.6 | Agregar `touch-action: manipulation` y `overscroll-behavior` en modales/scroll containers | `globals.css`, cards | P1 |
| 2.7 | Ampliar columna de tiempo a 100px en MatchCard para timezone | `match-card.tsx:75` | P2 |
| 2.8 | Mostrar badge sutil "PROGRAMADO" en hover para partidos SCHEDULED | `match-card.tsx` | P2 |

### Fase 3: Pulido de Microinteracciones y Animaciones

**Objetivo:** Experiencia premium, animaciones con proposito, soporte reduced-motion.

| # | Tarea | Archivos | Prioridad |
|---|-------|----------|-----------|
| 3.1 | Implementar `prefers-reduced-motion` en `live-pulse`, skeletons, y glow EV+ | `globals.css`, componentes | P1 |
| 3.2 | Agregar `:active { transform: scale(0.97) }` a botones y elementos presionables | `globals.css` (utility) | P2 |
| 3.3 | Stagger animation (30-80ms) para entrada de tarjetas en lista de partidos | `match-card.tsx`, CSS | P2 |
| 3.4 | Animacion de glow EV+ con pulso sutil (3s interval, opacity 0.6->1) | `match-card.tsx` | P3 |
| 3.5 | Transicion `clip-path` para expandir/colapsar accordiones de liga | `league-accordion.tsx` | P3 |
| 3.6 | Skeleton shimmer con gradiente animado en lugar de `animate-pulse` plano | `dashboard.tsx` skeletons | P3 |
| 3.7 | Tooltip en nombres de equipo truncados (usando `title` attribute o popover nativo) | `ticket-leg.tsx`, `match-card.tsx` | P3 |

---

## 5. Notas de Implementacion

### Reglas de codificacion a seguir:
- **Nunca** usar `transition: all` — listar propiedades explicitamente.
- **Nunca** animar `width`, `height`, `padding`, `margin` — solo `transform` y `opacity`.
- **Siempre** usar tokens semanticos (`text-primary`, `bg-positive/15`) sobre colores directos (`text-indigo-400`, `bg-zinc-900`).
- **Siempre** incluir `min-w-0` en flex children que usan `truncate`.
- **Siempre** proveer `aria-label` en icon-only buttons y `aria-hidden` en iconos decorativos.
- **`…`** (elipsis Unicode) sobre `...` (tres puntos) en textos de UI.

### Componentes que requieren tests visuales:
- `MatchCard` — verificar SCHEDULED, LIVE, FINISHED con y sin score.
- `TicketCard` — verificar con 1, 2, 3 tickets en grid. Nombres largos.
- `EVTable` — verificar con datos EV+, NO EDGE, y AVOID.
- `MatchHero` — verificar con marcador LIVE y sin marcador (SCHEDULED).

---

## Resumen Ejecutivo

**Puntaje global: 6.0/10.** La aplicacion tiene una base de diseno solida (dark theme, sistema de tokens, tipografia tabular para datos) pero acumula deuda de accesibilidad significativa y hardcodeo de colores en componentes clave (~80 ocurrencias en la pagina de detalle).

**Impacto estimado por fase:**
- **Fase 1 (3-5 dias):** Resuelve el 80% de los problemas de accesibilidad. El DateSelector y los tabs seran usables con lectores de pantalla.
- **Fase 2 (5-8 dias):** Unifica el lenguaje visual. La pagina de detalle usara los mismos tokens que el resto de la app. Los tickets tendran altura consistente.
- **Fase 3 (3-4 dias):** Eleva la experiencia a nivel premium con microinteracciones y animaciones con proposito.

**Tiempo total estimado:** 11-17 dias de desarrollo.
