# BETMIND UI/UX FLOW — Handover Arquitectónico del Frontend

> **Documento de contexto (Handover) para modelos de IA externos.**
> Este archivo describe —con fidelidad total al código fuente— la arquitectura real, los flujos de interfaz, el sistema de diseño y los contratos de datos del frontend de **BetMind AI**.
>
> - **Proyecto:** BetMind AI — Inteligencia en Apuestas Deportivas
> - **Aplicación web:** `apps/web/` (Next.js 16 App Router, React 19, TypeScript, Tailwind CSS v4, shadcn/ui, Lucide)
> - **Backend consumido:** FastAPI en `http://localhost:8000` (configurable vía `NEXT_PUBLIC_API_URL`)
> - **Ruta de auditoría:** `app/`, `components/betmind/`, `components/ui/`, `lib/`
> - **Último commit de referencia:** `140eb46` (chore: deps AST-audited)
>
> **Convención de este documento:** toda afirmación describe el comportamiento observable en el código. Los componentes presentes en el repo pero sin uso activo se listan en el Apéndice C como dato informativo. **Este documento es contexto, no restricción y tampoco un aval:** las Secciones 1–5 son evidencia del estado actual, no juicios de calidad — nada de lo descrito debe interpretarse como "correcto" o "bien hecho". El encargo de trabajo para quien reciba este archivo está en la Sección 6.

---

## Tabla de contenidos

1. [Sistema de Diseño & System Tokens](#sección-1-sistema-de-diseño--system-tokens)
2. [Navegación Global & Layout Principal](#sección-2-navegación-global--layout-principal)
3. [Desglose de Rutas y Vistas del Producto](#sección-3-desglose-de-rutas-y-vistas-del-producto)
4. [Generador de Boletos VIP & Ledger Cuantitativo](#sección-4-generador-de-boletos-vip--ledger-cuantitativo)
5. [Apéndices](#apéndices)
6. [Brief de Crítica Total (mandato para el crítico)](#sección-6-brief-de-crítica-total-mandato-para-quien-recibe-este-documento)

---

# SECCIÓN 1: SISTEMA DE DISEÑO & SYSTEM TOKENS

## 1.1 Paleta de color — "Obsidiana + Menta Técnica"

El tema es **100% oscuro** (`color-scheme: dark` forzado; el layout fija `themeColor: '#070A0D'`). Los tokens viven en `apps/web/app/globals.css` y se exponen a Tailwind vía `@theme inline` (mapeo `--color-*`).

| Token CSS | Valor | Rol semántico |
|---|---|---|
| `--background` | `#070A0D` | Negro profundo base (body) |
| `--surface` | `#0D1318` | Superficie base de tarjetas/secciones |
| `--surface-raised` | `#121B21` | Superficie elevada (hover, controles activos) |
| `--surface-inset` | `#070C10` | Surcos internos (tracks de barras) |
| `--card` | `#0D1318` | Fondo de tarjetas `bg-card` |
| `--popover` | `#10181D` | Paneles flotantes (ficha cuantitativa) |
| `--primary` | `#9BE6B0` | Menta técnica: identidad, acentos interactivos, probabilidad modelo |
| `--primary-foreground` | `#07100B` | Texto sobre primary |
| `--positive` | `#74D99A` | **Valor esperado positivo (+EV)** — reservado exclusivamente a ventaja cuantitativa, estados "EN VIVO", "En rango" y confianza alta |
| `--warning` | `#D8B36B` | Ámbar: riesgo medio, cuotas visitante, "PAUSADO", "Fuera de rango" |
| `--negative` | `#EE7B7B` | Rojo: riesgo alto, EV negativo, "AVOID", "LOST" |
| `--border` | `#26343A` | Bordes finos de tarjetas |
| `--border-subtle` | `#18242A` | Divisores interiores |
| `--subtle` | `#84968F` | Texto secundario / kickers |
| `--muted` / `--muted-foreground` | `#111A1F` / `#A8B7B0` | Fondos desactivados / texto terciario |
| `--foreground` | `#EEF4F1` | Texto principal |

**Uso actual del color (evidencia, no regla):** el verde menta (`positive`/`primary`) se usa para señalar valor esperado positivo (+EV) o probabilidad de modelo; los metadatos decorativos usan `subtle`/`muted`. La jerarquía de superficies se logra por elevación de opacidad y bordes finos (`border-white/10`, `bg-white/[0.02]`–`[0.04]`).

El `body` tiene un fondo técnico: rejilla fina verde (`linear-gradient` de 40px con `rgba(155,230,176,0.018)`) más un resplandor radial de menta (`rgba(116,217,154,0.08)` en el 50% superior), fijo con `background-attachment: fixed`.

**Nota de fidelidad:** en algunos componentes puntuales del detalle de partido persisten hexes hardcodeados heredados — `#8577FF` (índigo, local) y `#3DE3A5` (menta secundaria, visitante/EV) — usados en el radar táctico SVG, las barras de los acordeones de mercados, `#11151B`/`#252C35`/`#182029` (paneles "terminal") y el lienzo de exportación de imagen. Conviven con los tokens del tema pero **no forman parte de ellos** (ver recomendación R1 en §5.2).

## 1.2 Tipografía y alineación tabular

| Variable | Fuente | Uso |
|---|---|---|
| `--font-sans` | Inter | Texto general y UI |
| `--font-mono` | IBM Plex Mono (pesos 400–700) | Datos cuantitativos |
| `--font-serif` | Playfair Display | Acentos editoriales (p. ej. título "Escáner de Boletos") |

- **Convención actual de alineación tabular:** cuotas (`@1.95`), márgenes EV (`+10.3% EV`), Goles Esperados (`xG`), porcentajes de confianza, horarios COT y contadores se renderizan con `font-mono tabular-nums`.
- Utilidad `.num` (Tailwind v4 `@utility`): `tabular-nums` + `letter-spacing: -0.01em` + `font-family: mono`. Se usa en todos los valores numéricos de tarjetas y celdas.
- Clases utilitarias globales: `.terminal-kicker` y `.terminal-label` (mono, uppercase, `letter-spacing` 0.14em/0.1em, color `subtle`) para encabezados de sección tipo terminal; `.terminal-frame`, `.terminal-metric`, `.terminal-divider`.
- **Formateadores centralizados** (`lib/formatters.ts`):
  - `formatOdds(x)` → `x.toFixed(2)` (cuota decimal, siempre 2 decimales para columnas tabulares); `'—'` si no es finito.
  - `formatEV(x)` → porcentaje firmado con signo explícito: `+10.3%` / `-2.0%`.
  - `formatxG(x)` → 2 decimales.
  - `formatPercent(x, digits=1)` → `42.1%`.
  - `formatCOTDate(iso)` → fecha/hora con `Intl.DateTimeFormat('es-CO', …)` y `timeZone: 'America/Bogota'`.
  - `formatDecimal(v, digits=1)` → decimales estables para nombres de mercados (`10.5`).

## 1.3 Iconografía y estilo

- **Iconografía exclusiva de Lucide** (`lucide-react`). Cero emojis informales (🔥 👉 trofeos) en la UI.
- Únicas excepciones de glifos: **banderas regionales** de ligas (`🇨🇴`, `🏆` para UEFA, `🌎` para Sudamérica) definidas como escapes unicode en `lib/league-metadata.ts`, y los **glifos geométricos de modo** `⬡ ◈ ⬟` (EDGE/VALUE/BOLD) definidos en `lib/betmind.ts` (`MODE_META.glyph`) — caracteres geométricos Unicode, no emojis.
- Micro-interacciones definidas en `globals.css`: `live-dot` (pulso 1.4s para estados EN VIVO), `ev-glow` (resplandor +EV), `stagger-item` (entrada escalonada 300ms), `skeleton` (shimmer 1.6s), `accordion-content`, `animate-ping`.
- Accesibilidad: targets táctiles mínimos de 44px en `pointer: coarse`, feedback de presión `scale(0.97)` en hover-capable, `prefers-reduced-motion` desactiva todas las animaciones, `overscroll-behavior-y: contain` en diálogos.

## 1.4 Monogramas técnicos (fallbacks de escudos)

No existe un componente único llamado `Monogram`; el patrón se materializa en tres piezas:

1. **Monograma de marca (TopNav):** caja `size-8 rounded-md border border-positive/40 bg-positive/10` con `BM` en `font-mono text-xs font-bold text-positive`.
2. **`LeagueLogo`** (`components/betmind/league-logo.tsx`): si no hay `logoUrl` o falla la imagen → recuadro `rounded border border-border/60 bg-surface-raised font-mono` con las iniciales de las 2 primeras palabras (`LeagueLogo → LG`). Si hay imagen: círculo `bg-white/10 p-0.5` con la imagen.
3. **`TeamLogo`** (`components/ui/team-logo.tsx`, el usado en la app): sistema de **3 tiers** con degradación trazable:
   - Tier 1: URL directa del provider (`src`).
   - Tier 2: fallback CDN `https://media.api-sports.io/football/teams/{id}.png`.
   - Tier 3: **escudo SVG generado por código** (gradiente `#27272a → #09090b`, trazo `#3f3f46`, iniciales centradas calculadas con `buildInitials()` que ignora artículos/partículas `de, la, y, fc, cf…`).

(`components/betmind/team-logo.tsx` es una variante antigua con fallback de iniciales en `bg-muted`; **huérfana** — ver Apéndice C.)

## 1.5 Internacionalización (i18n) de mercados

**Comportamiento vigente:** ningún mercado se muestra con su clave técnica cruda; todo pasa por `formatMarketName()` en `lib/formatMarketName.ts`.

Pipeline: normalización (`lowercase`, unifica guiones `–—−`→`-`, espacios→`_`) → tabla `EXACT_NAMES` → patrones regex → fallback `titleCase`.

| Clave técnica (backend) | Español formal |
|---|---|
| `CORNERS_UNDER_10_5` | `Menos de 10.5 Córneres` |
| `CORNERS_OVER_8_5` | `Más de 8.5 Córneres` |
| `CARDS_OVER_4_5` | `Más de 4.5 Tarjetas` |
| `SHOTS_OT_OVER_3_5` | `Más de 3.5 Remates al Arco` |
| `OVER_2_5` / `UNDER_1_5` | `Más de 2.5 Goles` / `Menos de 1.5 Goles` |
| `btts_yes` / `btts_no` | `Ambos Anotan: Sí` / `Ambos Anotan: No` |
| `1x2_home` / `1x2_draw` / `1x2_away` | `Ganador Local (1)` / `Empate (X)` / `Ganador Visitante (2)` |
| `double_1x` / `double_x2` / `double_12` | `Doble Oportunidad 1X (Local/Empate)` … |
| `dnb_home` / `dnb_away` | `Empate No Válido: Local (DNB)` / `…: Visitante (DNB)` |

El fallback traduce tokens sueltos (`over→Más de`, `corners→Córneres`, `shots ot→Remates al Arco`…) y convierte a Title Case, cubriendo variantes futuras del motor sin romper decimales.

## 1.6 Tipografías del documento raíz

`app/layout.tsx` define `metadata` (título/descripción SEO en español, favicons claros/oscuros + SVG + apple) y `viewport` (`colorScheme: 'dark'`, `themeColor: '#070A0D'`). Incluye el `Toaster` de `sonner` posicionado `bottom-right` (notificaciones globales: copiado, guardado, error).

## 1.7 Primitivas UI compartidas (`components/ui/`)

Capas base de shadcn/ui (Tailwind v4 + `components.json`):

| Primitiva | Notas |
|---|---|
| `button.tsx` | Variants `default/ghost/outline/secondary/destructive`; sizes `sm/default/lg/icon/icon-sm` (el patrón `min-h-11` se usa en botones de acción grandes) |
| `card.tsx` | Contenedores `bg-card border border-border rounded-xl` |
| `dialog.tsx` | Diálogo modal base (con `sonner` como sistema de toast) |
| `table.tsx` | Tabla base (el detalle de partido usa tablas propias; la primitiva quedó para soporte) |
| `separator.tsx`, `avatar.tsx`, `sonner.tsx` | Utilidades (separadores, avatar, wrapper del Toaster) |

Los componentes de producto (`components/betmind/*`) componen estas primitivas más utilidades ad-hoc (`cn` de `lib/utils.ts` con `clsx` + `tailwind-merge`).

---

# SECCIÓN 2: NAVEGACIÓN GLOBAL & LAYOUT PRINCIPAL

## 2.1 Modelo de rutas (real)

La aplicación usa **App Router de Next.js** con exactamente **2 rutas físicas**:

| Ruta | Archivo | Contenido |
|---|---|---|
| `/` | `app/page.tsx` → `<Dashboard/>` | Terminal principal con **3 pestañas internas** (ver 2.2) |
| `/partidos/[id]` | `app/partidos/[id]/page.tsx` | Cerebro táctico & detalle de partido (4 pestañas) |

**IMPORTANTE (fidelidad):** no existen rutas `/partidos` ni `/escaner`. El "cartelera" y el "escáner" son **pestañas** dentro del dashboard, controladas por estado local (`NavTab`), no por el router. Los vínculos a detalle son `href="/partidos/{id}"` (`match.id` es `String(raw.id)` del backend).

## 2.2 Arquitectura de navegación: TopNav + BottomNav

`components/betmind/top-nav.tsx` exporta `NAV_TABS = ['Boletos', 'Partidos', 'Escáner']` (tipo `NavTab`) y dos componentes:

**`TopNav`** — header sticky (`sticky top-0 z-40 border-b border-border/60 bg-background/90 backdrop-blur-xl`, altura `min-h-16`):
- Botón hamburguesa (`lg:hidden`) para abrir el sidebar como drawer.
- **Identidad:** monograma `BM` en menta + `BetMind AI` + kicker `Quant Terminal · v0.1.0` + separador con `Signal Desk`.
- **Nav central** (desktop, `hidden md:flex`): 3 botones con iconos Lucide (`TicketIcon`, `CalendarIcon`, `ScanIcon`), `aria-current="page"` para el activo.
- **Derecha:** chip `COT · UTC−5` (`font-mono tabular-nums`) y chip en vivo `● {activeLeagueCount} ACTIVAS` (contador de ligas con `active_matches > 0`, `live-dot` pulsante).

**`BottomNav`** — barra fija móvil (`fixed inset-x-0 bottom-0 z-40 grid grid-cols-3 md:hidden`, `pb-[env(safe-area-inset-bottom)]`), mismos 3 tabs con iconos, activo en `text-primary`.

**`Dashboard`** (`components/betmind/dashboard.tsx`) orquesta: estado `tab: NavTab`, `sidebarOpen` (drawer móvil + overlay `bg-black/60 backdrop-blur-sm`), y renderiza:
- `TopNav` + `<aside class="w-[280px]">` con `LeagueSidebar` (siempre visible en `lg`, drawer en móvil).
- `<main>` con la vista de la pestaña activa.
- `BottomNav`.
- Padding inferior móvil `pb-[calc(4rem+env(safe-area-inset-bottom))]` para no quedar tras la BottomNav.

## 2.3 `DateSelector` — ventana temporal segmentada

`components/betmind/date-selector.tsx`. **Tipo `DateFilter = 'today' | 'tomorrow' | 'all'`** — **tres** opciones (no cuatro; no existe "Ayer"):

| Opción | Valor | Efecto |
|---|---|---|
| `Hoy` | `today` | `date_filter = fecha COT de hoy` |
| `Mañana` | `tomorrow` | `+1 día` |
| `Todas` | `all` | sin `date_filter` (ventana completa) |

- UI: grupo segmentado `inline-flex rounded-lg border bg-surface/70 p-1` con icono `CalendarDays`, botón activo con `bg-surface-raised shadow-sm`.
- Helpers exportados: `formatDateKey(filter, date)` → `YYYY-MM-DD` COT (o `undefined` para `all`) — se envía a `fetchLeagues`/`fetchTickets`; `formatDateTitle(filter, date)` → `{title, subtitle}` con weekday en español (`es-CO`, TZ `America/Bogota`) para los encabezados "Oportunidades de hoy", "Partidos de hoy", etc.

## 2.4 `LeagueSidebar` — Market Watch

`components/betmind/league-sidebar.tsx`. Catálogo lateral compactado por **regiones institucionales** (`CatalogGroup`):

- `BIG 5 EUROPA` — Premier, LaLiga, Bundesliga, Serie A, Ligue 1.
- `SUDAMÉRICA` — regex de países + Libertadores/Sudamericana.
- `TORNEOS UEFA` — nombre contiene `uefa`.
- `OTRAS LIGAS ACTIVAS` — resto.

Comportamiento clave:
- **Ocultamiento estricto del DOM:** las ligas se filtran con `league.active_matches > 0`; un grupo sin items no se renderiza (`LeagueGroup` retorna `null`).
- **Presets 1-clic:** botón "Todas las ligas" con contador total `{totalMatches}` (derivado de los partidos) y cabecera `Market watch` + `Competiciones activas` + contador `{activas}/26`.
- Si el endpoint `fetchLeagues` falla, se **degrada a un conteo local** derivado de `matches` (agrupando por `leagueExternalId`) — misma API de props.
- Cada fila: `LeagueLogo` + nombre truncado + badge contador `font-mono tabular-nums`; activa con `border-positive/30 bg-positive/10 text-positive`.
- `onSelect(leagueId)` en el dashboard: filtra la cartelera y **salta automáticamente a la pestaña Partidos** si el usuario estaba en Boletos.

> **Nota:** la modal flotante "Personalizar ligas" con multiselección `string[]` NO vive en el sidebar; es del **Generador de Boletos** (ver §4.1).

## 2.5 Estados de datos globales del dashboard

- **Skeletons:** `TicketSkeleton` (tarjeta de boleto con 3 patas) y `MatchSkeleton` (fila de partido con las 3 columnas) vía `LoadingState` + `<span class="sr-only">Cargando…</span>` (`aria-busy`, `aria-live="polite"`).
- **`EmptyState`:** borde punteado, icono `Sparkles`, título contextual ("Todavía no hay una señal con valor" / "No hay partidos en esta ventana"), `formatUpdatedAt`/`formatAge` ("Actualizado hace N min") y botón "Actualizar ahora" (`RefreshCw` → `retryKey++`).
- **`ErrorState`:** `role="alert"`, borde `negative/25`, "No pudimos actualizar los datos" + "Reintentar".
- **Fetches paralelos por `dateFilter`:** `fetchTickets(['EDGE','VALUE','BOLD'])`, `fetchMatches()`, `fetchLeagues(dateKey)`; cada uno con bandera `cancelled` anti-race.

---

# SECCIÓN 3: DESGLOSE DE RUTAS Y VISTAS DEL PRODUCTO

## 3.0 Mapas visuales de cada vista (referencia rápida)

Diagramas de alto nivel del layout real de cada vista, para contexto visual del rediseño.

**Vista "Boletos" (tab 1 — pestaña inicial al abrir la app):**

```
┌────────────────────────────── TopNav · sticky (min-h-16) ──────────────────────────────┐
│ [≡] [BM] BetMind AI ▸ Quant Terminal v0.1.0 | Signal Desk    [Boletos|Partidos|Escáner]  COT · UTC−5  ● N ACTIVAS │
├───────────────┬─────────────────────────────────────────────────────────────────────────┤
│ MARKET WATCH  │  Oportunidades de hoy · {weekday}          [Hoy|Mañana|Todas] [Boletos IA|Generador] │
│ [Todas las ligas]  │  N señales +EV · Actualizado hace X min                                        │
│ (n/26)        │  ┌── TicketCard EDGE ──┐ ┌── TicketCard VALUE ─┐ ┌── TicketCard BOLD ─┐   │
│               │  │ ▬▬▬ (strip 3px modo) │ │                     │ │                     │   │
│ BIG 5 EUROPA  │  │ MODO EDGE      @8.92 │ │                     │ │                     │   │
│  Premier (4)  │  │ Confianza 72% · +EV  │ │                     │ │                     │   │
│  LaLiga (3)   │  │ 1. Mercado  @2.10    │ │                     │ │                     │   │
│ SUDAMÉRICA    │  │ 2. Mercado  @1.95    │ │                     │ │                     │   │
│  BetPlay (2)  │  │ [Guardar en Ledger]  │ │                     │ │                     │   │
│ TORNEOS UEFA  │  └──────────────────────┘ └─────────────────────┘ └─────────────────────┘   │
│ OTRAS LIGAS   │  Panel de Seguimiento · Ledger cuantitativo                                │
│ ACTIVAS       │  [MODO ANÓNIMO ACTIVO · Sincroniza… · Conectar Cuenta PRO]                 │
│               │  [4 métricas]  [Fila WON · @5.20 · +12% EV · 🗑]                           │
└───────────────┴───────────────────────────────────────────────────────────────────────────┘
                    [ BottomNav móvil: ⬜ Boletos | Partidos | Escáner ] (fixed)
```

**Vista "Partidos" (tab 2 — cartelera):**

```
┌── Partidos de hoy ────────────────────────────────  [Hoy|Mañana|Todas]  ────────────────┐
│ [Todas las Ligas (12)] [Premier (4)] [LaLiga (3)] [BetPlay (2)] … (pills)               │
│ ⌕  Filtros: ( Todos ) ( ALTA CONFIANZA >75% ) ( +EV MEJOR VALOR )                       │
│ ┌─ LeagueAccordion: [escudo] Premier League · Inglaterra  ● 2 en vivo      [7] ▾       ─┐ │
│ │ ┌─ MatchCard (Alpha Strip) ─────────────────────────────────────────────────────────┐ │ │
│ │ │ [Gana Local 62.3% · @1.95 · EV +10.3%]  ← solo si hay mejor oportunidad +EV       │ │ │
│ │ │ [ 8:00 PM COT ] [▣ Arsenal 62%]                    [1 62%] [X 22%] [2 16%]         │ │ │
│ │ │ [ EN VIVO 67' ] [▣ Chelsea 22%]  ▭▭▭ Poisson 0-4+  [Ver Análisis →]                │ │ │
│ │ │ [COPA]          [xG 1.84 - 0.97 · Marcador est. 2-1 (18.4%)]                      │ │ │
│ │ └─────────────────────────────────────────────────────────────────────────────────────┘ │
│ └───────────────────────────────────────────────────────────────────────────────────────────┘
```

**Detalle `/partidos/[id]` — hero + tabs:**

```
┌─ ← Volver a Partidos ──────────────── Arsenal vs Chelsea (sticky header) ─────────────┐
│ ┌─ MatchHero ────────────────────────────────────────────────────────────────────────┐ │
│ │ [escudo liga] Premier League · 8:00 PM COT · [POR JUGAR]                           │ │
│ │ ▣ Arsenal ─────────  vs  ──────────── Chelsea ▣   (marcador si en vivo/finalizado) │ │
│ │ [ Local 58% ] [ Empate 23% ] [ Visitante 19% ]  + barra segmentada                 │ │
│ └───────────────────────────────────────────────────────────────────────────────────────┘
│ [ Señal BetMind 74/100 ] [ Estado: OPORTUNIDAD +EV ] [ Cuotas · datos 5 activas · 92% ]
│ [ Confianza IA ████████ 74/100 · Riesgo Medio ]  pills: Marcador probable · Over 2.5 · AI │
│ ┌─ TabBar sticky: [Resumen & Insights] [Pronósticos (56M)] [Bet Builder] [Cara a Cara] ─┐ │
│ │ Tab activo → contenido de la sección correspondiente (ver §3.2)                      │ │
│ └───────────────────────────────────────────────────────────────────────────────────────┘
```

**Generador de Boletos (dentro del tab Boletos):**

```
│ Mercados permitidos: (Goles) (Córneres) (1X2) (Tarjetas) (Remates)                    │
│ Presets: (Todas 12) (Big 5 Europa 5) (Sudamérica 3) (Copas UEFA 1) (⌕ Personalizar N) │
│ ┌── Configurar Boleto (360px) ──────┐  ┌── Vista previa ─────────────────────────────┐ │
│ │ Selecciones  [−] 3 sel. [+]       │  │ ▬▬▬ (strip del modo)                        │ │
│ │ Perfil de Riesgo                  │  │ MODO VALUE           @8.92   ⌬ copiar       │ │
│ │ ( EDGE ) ( VALUE ) ( BOLD )       │  │ [Confianza 74%] [+EV 12.4%] [Rango: En rango]│ │
│ │ Rango de Cuota Combinada          │  │ 1. Más de 2.5 Goles  @1.95   +12.4% EV  ⟳   │ │
│ │ (1.5–3.0) (3.0–6.0) (6.0+)        │  │    Arsenal vs Chelsea  (popover al hacer     │ │
│ │ [Regenerar Boleto]                │  │    [ficha: xG, cuota, modelo vs casa,        │ │
│ │                                   │  │     stake quarter-Kelly]                    │ │
│ │                                   │  │ Razonamiento IA: chips + Filtros y seguridad│ │
│ │                                   │  │ [Guardar en Ledger Cuantitativo]            │ │
│ │                                   │  │ [Compartir / Descargar Imagen]              │ │
│ └───────────────────────────────────┘  └──────────────────────────────────────────────┘
```

## 3.1 `/` — Vista **Boletos** (IA + Generador) y el "Terminal 3 columnas"

La composición del dashboard responde al concepto de **terminal de 3 columnas** de la siguiente forma real:

1. **Columna izquierda (fija, `w-[280px]`):** `LeagueSidebar` (Market Watch) — catálogo y presets por liga.
2. **Columna central (contenido):** según pestaña:
   - **Boletos:** selector de vista segmentado (`Boletos IA` / `Generador`), `DateSelector`, grilla de `TicketCard` (1/2/3 columnas según cantidad), meta "`{N} señales +EV · Actualizado hace X min`" y, debajo, el **Panel de Seguimiento** (`TrackingPanel`).
   - **Partidos:** cartelera con `DateSelector`, **pills de liga** derivadas de los partidos reales ("Todas las Ligas (N)" + ligas ordenadas por cantidad), **filtros rápidos de predicción** (`Todos` / `ALTA CONFIANZA (>75%)` / `+EV MEJOR VALOR`) y acordeones `LeagueAccordion` con `MatchCard`.
   - **Escáner:** `ScannerEmptyState` (ver 3.3).
3. **Columna derecha (conceptual):** dentro de la vista Boletos conviven el **Generador VIP** (panel de control + vista previa) y el **Ledger cuantitativo** (TrackingPanel). No es una tercera columna física: el layout es `[sidebar 280px | main flex-1]` y el generador usa su propia grilla `lg:grid-cols-[360px_1fr]`.

### Vista "Partidos" — `MatchCard` (formato `Alpha Strip`)

`components/betmind/match-card.tsx`. Fila horizontal en 3 columnas sobre `Card`:

- **Banner superior (Alpha Strip):** solo si `bestOpportunity(rows) != null && hasLambda && programado`. Izquierda: `{label} {probabilidad del modelo}`; derecha: `@{cuota}` + badge `EV +X.X%` en menta. Tarjeta con glow `shadow-[0_0_24px_-10px_var(--positive)]` y borde `positive/40`; en vivo, borde `positive/30`.
- **Col 1 (100px):** hora COT (`font-mono tabular-nums`), badge de estado (EN VIVO con minuto / PAUSADO / FINALIZADO), badge `COPA` para `matchType === 'KNOCKOUT_CUP'`.
- **Col 2 (flex):** `TeamLogo` + nombre (truncado) + probabilidad de modelo por equipo; sub-strip con `PoissonMiniChart` (histograma de goles 0–4+, barras local `var(--primary)` / visitante `var(--warning)`) y leyenda `xG 1.34 - 0.98 · Marcador est. 2-0 (28.1%)`; "Calculando métricas…" cuando no hay lambdas.
- **Col 3 (180px):** probabilidades base **`1 · X · 2`** en `font-mono` y enlace discreto `Ver Análisis →` (o `Ver Detalle` si finalizó) — **el único** vínculo a `/partidos/[id]`.
- Toda la tarjeta es un `<Link>` (hover: `group`, flecha que se desliza).

**Separación de responsabilidades de la cartelera (comportamiento vigente):** aquí solo se muestran el calendario oficial (horarios COT), equipos, escudos/monogramas y las probabilidades base `1·X·2`. **No se muestran pronósticos intrusivos de mercados secundarios ni prop bets** — el modelo cuantitativo completo (56 mercados) queda confinado al detalle `/partidos/[id]`.

### Vista "Escáner" — `ScannerEmptyState`

`components/betmind/scanner-empty-state.tsx`. **UI preparada pero sin backend conectado:** zona de drop de imagen (`input type="file" accept="image/*" multiple` con drag&drop, límite declarado 10MB PNG/JPG/WEBP), titular en serif "Escáner de Boletos", y una lista "Cómo funciona" en 4 pasos (subir captura → visión IA → comparar contra Poisson/VE → reporte). Actualmente el manejo de archivos no procesa nada (`handleDrop`/`handleFileSelect` son silenciosos).

## 3.2 `/partidos/[id]` — Cerebro Táctico (4 pestañas)

`app/partidos/[id]/page.tsx` (cliente). Carga en paralelo con `Promise.allSettled`:

- `fetchMatchPrediction(id)` → `GET /api/v1/matches/{id}` + `GET /api/v1/predictions/{id}` (resultado `EnrichedMatch | null`; si falla la predicción pero no el match, devuelve un `EnrichedMatch` degradado con ceros).
- `fetchMatchH2H(id)` → `GET /api/v1/matches/{id}/h2h` (opcional).

Estados: `PageSkeleton` (pulse), error "Partido no encontrado" con retorno a `/`, y el contenido. Header sticky propio: `← Volver a Partidos` + `{home} vs {away}`.

### Cabecera de partido (`MatchHero`) + `SignalRail` + `ConfidenceBar`

- **`MatchHero`:** `LeagueLogo` + liga + hora COT + badge de estado; escudos `TeamLogo` 40px; marcador `font-mono text-2xl font-black` cuando está en vivo/pausado/finalizado (o medallón `vs`); **cajas de probabilidad `Local · Empate · Visitante`** (solo programados) + barra segmentada 3 colores (primary/muted/warning).
- **`SignalRail`:** tira de 3 celdas tipo telemetría — `Señal BetMind` (`confidenceScore/100`), `Estado del mercado` (`OPORTUNIDAD +EV` en menta si el mejor edge 1X2 ≥ 3%, si no `MERCADO AJUSTADO`), `Cuotas · datos` (`N activas · COMPLETITUD %`).
- **`ConfidenceBar` (local de la página):** barra gradiente `primary`, score `X/100` en mono, chip de riesgo (`Riesgo Bajo`/`Medio`/`Alto`), pills: `Marcador probable: 2-1`, `Más de 2.5 — 61%`, `aiSummaryPill` con `Sparkles`.

### Tab bar (`MatchTabBar`)

`components/betmind/match-tab-bar.tsx` — `MatchTab = 'preview' | 'markets' | 'builder' | 'h2h'`, sticky `top-14 z-30`:

| Tab | Label | Icono |
|---|---|---|
| `preview` | Resumen & Insights | `TrendingUp` |
| `markets` | Pronósticos (56M) | `BarChart3` |
| `builder` | Bet Builder | `Target` |
| `h2h` | Cara a Cara | `Swords` |

ARIA: `role="tablist"` / `role="tab"` con `aria-controls`, subrayado activo `h-px bg-primary`.

### Tab 1 — Resumen & Insights (`PreviaTab`)

- **`TacticalPanel`** (`components/betmind/tactical-panel.tsx`) — el **Memorándum Cuantitativo (Research Briefing):**
  - Tira de metadatos: `MODELO: {llm_model_used || 'QUANT ENGINE'}` · `COMPLETITUD: {data_completeness_score}%` · `{N} TOKENS` o `SEÑAL EN VIVO`.
  - Encabezado "Memorándum cuantitativo" + headline IA + `{liga} · Señal {signal}`.
  - **Gauge de Confianza IA** (score/100 + barra + `Riesgo bajo/medio/alto`).
  - `StatBar` de Goles Esperados y Total de Goles (barras duales primary/warning) + "Ritmo contenido/moderado/abierto" por umbrales de xG total.
  - Narrativas por bloque (`Goles`, `Tarjetas`, `Córneres`, `Proposiciones de jugador`).
  - **Pros/Cons** (`FactorList`): viñetas con categoría técnica (`FORM/H2H/STATISTICS/CONTEXT/REFEREE`) y **severidad `ALTA`/`MEDIA`/`BAJA`** (alta=menta, media=ámbar, baja=gris).
  - `Riesgo clave ·` al pie. Decoración: blob radial `bg-primary/10 blur-3xl`.
- **Lógica de veredicto principal:** si `mainEdge (1X2) >= 0.03` → `PrimaryRecommendation` (pronóstico principal +EV con cuota `@X.XX` y botón "Añadir al boleto"); si no → `CapitalProtectionPanel` ("Veredicto BetMind: Protege tu Capital" — "las cuotas 1X2 están perfectamente ajustadas (0% EV)", con radar xG y tarjetas de córneres/fricción/árbitro).
- **Columna derecha:** `ModelProbabilities` (barras comparativas `Victoria/Empate/Over 2.5/Ambos Anotan`), `TopScorers` (top 5 marcadores con barra y badge "Más probable"), `CornersCards` (`+8.5 Córneres`, `3.5+ Tarjetas` + fricción), `ScouterStats` (datos verificados post-partido: córneres/remates/a puerta/faltas, o estado "Datos en vivo al finalizar el partido").

### Tab 2 — Pronósticos (56M) (`QuantMarkets`)

- Encabezado: "Escáner de margen +EV" + contador `{n}/56 mercados`.
- **Señales 80/20:** top 5 de `evAnalysis` con `ev > 0 || probability > 0.65`, ordenado por `ev` desc → `SignalScannerCard` (nombre en español, `56M · Cuota @X.XX`, veredicto `POSITIVE_EV`/`NO_VALUE`/`AVOID`/`SIN CUOTAS`, barras **MODELO vs. CASA** con porcentajes, Edge/EV en menta, `Cuota justa IA` = 1/probabilidad).
- **"Explorar los 56 mercados completos · Modo Analista":** acordeones `MarketAccordion` por grupos — `Goles & Resultado`, `Córneres Totales`, `Tarjetas & Disciplina`, `Remates a Puerta` — con barra de probabilidad, `+X.X% EV` y estado `● +EV` (prob ≥ 0.70 ∧ ev > 0) / `● Riesgo Alto` (prob < 0.35) / `Neutro`.
- Disclaimer de honestidad: *"Las cuotas no publicadas se muestran como N/D, nunca como una oportunidad inventada."*

### Tab 3 — Bet Builder (`BetBuilderCards`)

`components/betmind/bet-builder-cards.tsx` — estrategias correlacionadas del backend (`bet_builder[]`) como **portafolios de inversión**:
- Cabecera `ESTRATEGIAS CORRELACIONADAS — QUANT ENGINE`; grilla de 3 perfiles (CONSERVATIVE=BAJA VARIANZA, MODERATE=RIESGO MEDIO, BOLD/CAZADOR=ALTA VARIANZA/+EV MÁXIMO).
- Cada tarjeta: badge de perfil + label IA, **cuota combinada** en mono, lista de selecciones numeradas con `@{odds_estimate}` y probabilidad combinada, chip `Link2` "Selecciones validadas como bloque correlacionado" y un botón cuyo **único efecto actual es un toast** ("Estrategia guardada en el Ledger") — no persiste nada todavía.
- Origen de los datos: `EnrichedMatch.betBuilder` (endpoint de predicción). En `page.tsx` existe un render local alternativo (`BetBuilder` con 3 cards de gradiente) pero **retorna temprano** hacia `BetBuilderCards` — el render local es código muerto.

### Tab 4 — Cara a Cara (`H2HTab`)

- Badge de origen: `Análisis Táctico · Groq · Llama 3.3` (etiqueta fija en la página; el modelo real viene en `llmModelUsed`).
- **Forma reciente (últimos 5):** burbujas `V`/`E`/`D` (mapa `W/D/L`→`V/E/D`) en monoespaciado, estilos menta/gris/rojo.
- **Modelo Cuantitativo:** barras de `xG` y `Total Goles`, chips `Duelo cerrado` (tot < 2.2) / `Local dominante`.
- **Señal:** 3 puntos de intensidad (STRONG/MODERATE/WEAK) + resumen.
- **`H2HReferencePanel` — Smart Fallback trazable:** si `h2h.total` es falsy → badge `H2H DIRECTO NO DISPONIBLE` + nota explícita *"La muestra directa aún no está persistida. Se muestra la referencia del modelo actual y la forma reciente como degradación trazable, sin inventar promedios históricos"* + matriz bilateral `xG del modelo` y `Córneres` con barras duales. Con H2H: `{total} H2H verificados`.
- **`TacticalRadar`:** radar SVG de 5 ejes (Ataque, Defensa, Fricción, Córneres, Forma), local `#8577FF` / visitante `#3DE3A5`, valores derivados de lambdas, tarjetas del árbitro y forma.
- **Historial H2H:** lista de enfrentamientos con fecha COT (`es-CO`, TZ Bogotá) y marcador; **Contexto de minutos:** `% de goles H2H en 2ª parte (minuto > 45)` con barra.
- **Narrativa del Modelo:** `NarrativeBody` parsea secciones `Goles:`/`Tarjetas:`/`Corners:`/`Resumen:` con iconos y **elimina fórmulas λ** (`stripLambdas`); si no hay narrativa: *"El análisis táctico detallado se genera 14 horas antes del inicio del partido."*

---

# SECCIÓN 4: GENERADOR DE BOLETOS VIP & LEDGER CUANTITATIVO

## 4.1 Controles e inputs (`TicketGenerator`, `components/betmind/ticket-generator.tsx`)

`GeneratorConfig` inicial: `{ selectionCount: 3, riskProfile: 'balanced', oddsMin: 1.80, oddsMax: 10.00, selectedMarkets: [GOALS,CORNERS,1X2,CARDS,SHOTS], selectedLeagues: [] }`.

**Panel izquierdo (360px) — "Configurar Boleto":**

1. **Selector numérico `-`/`+`** (`Minus`/`Plus`, iconos sin texto) — **rango real: 2 a 7 selecciones** (`Math.min(7, Math.max(2, count + delta))`), valor en `font-mono text-xl font-bold tabular-nums` con sufijo `sel.`. Disabled en extremos con `opacity-25`.
2. **Tarjetas segmentadas de perfil de riesgo** (3 columnas, sin iconos informales):
   - `EDGE` · *Baja Varianza* → modo backend `edge`
   - `VALUE` · *+EV Óptimo* → `value`
   - `BOLD` · *Alta Varianza* → `bold`
3. **Rango de Cuota Combinada** (presets): `1.5 – 3.0` / `3.0 – 6.0` / `6.0+`; el estado marca `En rango` (menta) o `Fuera de rango` (ámbar) según la cuota HERO resultante.
4. **Botón "Regenerar Boleto"** (`RefreshCw`, spinner mientras `loading`).

**Filtros superiores:**
- **Mercados permitidos** (pills de categoría): `Goles` (OVER/UNDER/BTTS), `Córneres`, `1X2`, `Tarjetas`, `Remates` — se envían como `markets` al API; la vista previa muestra `selectionCount` patas.
- **Presets de ligas 1-clic:** `Todas (N)` / `Big 5 Europa (N)` / `Sudamérica (N)` / `Copas UEFA (N)` (contadores = partidos activos del grupo).
- **Popover "Personalizar ligas (N)":** botón `Search` + `ChevronDown`; panel flotante `max-w-sm` con input de búsqueda ("Buscar liga o país") y **checkbox por liga (`string[]` de `league.key`)** con contador `[N]` de partidos activos. Se aplican como `league_keys` al API.

**Generación:** `fetchTickets([mode], leagueKeys?, dateFilter?, selectionCount?, markets?)` → POST `/api/v1/tickets/generate`; toma `tickets.find(t => t.mode === mode)` (con fallback al primero). Regeneración automática ante cualquier cambio de config; `optimizedCount` muestra el aviso *"Reducimos tu boleto de {original} a {N} selecciones para proteger tu Bankroll"*.

## 4.2 Lista de patas — `TicketLeg` (alta densidad) con explicabilidad "Por qué"

`components/betmind/ticket-leg.tsx` — fila compacta `grid-cols-[minmax(0,1fr)_auto]`:

1. **Mercado en español formal** (`formatMarketName`, truncado) + partido (`match`) como sub-línea.
2. **Badge `+X.X% EV`** (o `-X.X% EV` en negativo) — **trigger interactivo único** del detalle cuantitativo:
   - **`hover`:** abre el popover; **`click`:** lo fija (`detailsPinned`) para lectura táctil; `aria-expanded` + `aria-label`.
   - **Ficha cuantitativa** (`role="dialog"`, `w-72 bg-popover shadow-xl`): grid de 2 columnas con `Goles esperados (xG)` (`1.34 · 0.98`), `Cuota @X.XX`, `Modelo vs. casa` (`fairProb / bookmakerProb`), **`Stake quarter-Kelly`** (`kellyStake` del backend, en %); pie con `varianceNote || reasoning`.
3. **Cuota `@X.XX`** en mono.
4. **Rotador cuantitativo** — micro-icono *ghost* `RotateCw` ("Rotar selección N"): `swapLeg(index)` sustituye la pata por el **primer candidato de `replacementCandidates`** que no repita partido, y lo elimina de la lista de candidatos. Los candidatos los envía el backend (ranking por confianza/EV del motor); **la Cuota Combinada HERO se recalcula al instante** en el cliente (`combinedOddsDisplay = Π leg.odds`).

**Nota de fidelidad:** la rotación no re-consulta el ranking localmente; consume `ticket.replacementCandidates` (orden de calidad establecido por el backend al generar). En `TicketCard` la misma función opera sobre el ticket ya cargado.

## 4.3 Jerarquía de botones (footer del boleto)

1. **CTA primario único (`w-full`):** `Guardar en Ledger Cuantitativo` (`bg-primary`, icono `Star`) → `addToTracking(ticket)` (ver §4.5) + toast "Añadido a seguimiento".
2. **CTA secundario/ghost (`w-full`):** `Compartir / Descargar Imagen` → `shareOrDownloadTicket` (ver §4.6).
3. Icono discreto `Copy` (copiar texto plano al portapapeles: cabecera, cuota HERO, EV medio, patas numeradas).
4. Disclaimer: *"Probabilidades estimadas por modelo Poisson + IA. No constituye asesoría financiera."*

**Cabecera del boleto:** tira de acento de 3px según modo (`modeMeta.accent`), badge `MODO EDGE/VALUE/BOLD`, **Cuota Combinada HERO** (`font-mono text-4xl`), fila de métricas `Confianza IA %` · `+EV Promedio` · `Rango` (En/Fuera de rango), análisis IA (`line-clamp-2`), chips de `Razonamiento de la IA` (`rationale[]`) y línea `Filtros y seguridad: {correlation}`.

## 4.4 `TicketCard` — boleto IA autogenerado

`components/betmind/ticket-card.tsx`: misma anatomía que el generador (strip 3px del modo, HERO odds, stats row, patas con `TicketLeg` + rotador, footer con los mismos 2 CTAs + disclaimer) pero sin controles; permite rotar patas y guardar en seguimiento. `ticket.mode` fija la identidad visual vía `MODE_META` (`EDGE`⬡ primary, `VALUE`◈ warning, `BOLD`⬟ negative).

## 4.5 Persistencia & Multi-Tenancy (`tracking-panel.tsx`)

Flujo defensivo **localStorage → PostgreSQL**:

- **Clave local:** `betmind_tracked_tickets` (lista `TrackedTicket[]` con `{id, mode, combinedOdds, evAverage, confidence, legsCount, trackedAt, status, remote?}`), máxima 10 entradas, parse seguro con fallback `[]`.
- **Guardar:** `addToTracking` intenta `POST /api/v1/tickets/save` (body `{ticket_data, total_odds, total_ev}`); si `ok` → entradas **remotas** (id numérico del backend, `remote: true`); si no → **fallback local** con id sintético `{mode}-{timestamp}` y `status: 'PENDING'`.
- **Reclamo progresivo (`claim`):** `claimPendingTickets()` filtra entradas `remote` con id numérico y las asocia al usuario autenticado vía `POST /api/v1/tickets/claim` (`{ticket_ids}`); las reclamadas se purgan del localStorage. Es la **ruta progresiva de multi-tenancy** (`saved_tickets.user_id` + RLS en backend).
- **Historial:** `fetchTicketHistory()` (`GET /api/v1/tickets/history`); si falla, se sirve el localStorage. **Resincronización automática:** evento `storage`, evento custom `betmind:auth-changed`, `visibilitychange` e intervalo de **30 s**.
- **Estados (`SavedTicketStatus`):** `PENDING → WON → LOST → VOID → PENDING` (ciclo por click) con `PATCH /api/v1/tickets/{id}/status`; si el PATCH falla se conserva localmente.
- **Panel:** métricas agregadas (`Boletos guardados`, `Cuota promedio`, `+EV medio`, `En seguimiento`) + banner `MODO ANÓNIMO ACTIVO` con botón `Conectar Cuenta PRO` (placeholder: toast "La conexión de cuenta estará disponible próximamente") + lista `TrackRow` con borrado (`Trash2`).
- **Auth:** `getStoredAuthToken()` en `lib/api.ts` lee `sb-*-auth-token` (Supabase) o `betmind_access_token` del localStorage y lo inyecta como `Authorization: Bearer` si no existe ya; timeout global de **12 s** (`AbortController`) con normalización `HTTP_{status}` / `REQUEST_TIMEOUT` / `NETWORK_ERROR` y mensajes en español.

## 4.6 Exportación — Canvas/PNG + Web Share (`lib/ticket-export.ts`)

`shareOrDownloadTicket(ticket)` → `'shared' | 'downloaded' | 'cancelled'`:
1. **Render Canvas real (1200px):** fondo `#0c1016`, tira superior menta `#3de3a5`, `BETMIND AI` + `{MODO} · LEDGER CUANTITATIVO`, Cuota HERO `@X.XX` (58px), `+EV%` en menta, una fila por pata (`N. Mercado`, partido con wrapping, `@odds · +EV`), footer "Probabilidades estimadas por modelo Poisson + IA." Altura = `280 + legs × 92px`.
2. **Web Share API** con `navigator.share({title, text, url, files})` cuando `navigator.canShare({files})` (abort → `cancelled`).
3. **Fallback:** descarga directa `betmind-{modo}-{ts}.png` (object URL + anchor).

---

# APÉNDICES

## Apéndice A — Contratos de datos de la UI

### A.1 Núcleo (`lib/betmind.ts`)

```ts
type Mode = 'EDGE' | 'VALUE' | 'BOLD'
type MatchStatus = 'SCHEDULED' | 'IN_PLAY' | 'PAUSED' | 'FINISHED' | 'UPCOMING' | 'LIVE' | 'FT'
type Impact = 'HIGH' | 'MEDIUM' | 'LOW'

interface Match {
  id: string; leagueId: string; leagueExternalId: number | null; league: string
  leagueCountry: string | null; matchType: string; flag: string
  leagueLogoUrl: string | null; homeLogoUrl: string | null; awayLogoUrl: string | null
  homeTeamId: number | null; awayTeamId: number | null
  time: string                       // "8:00 PM COT" (TZ America/Bogota)
  matchDate: string; status: MatchStatus; minute?: number; elapsed?: number | null
  score?: [number, number]
  home: string; away: string
  lambdaHome: number; lambdaAway: number   // xG Poisson
  odds: Record<'home'|'draw'|'away'|'over25'|'btts', number>  // 0 = sin cuota
  pros: TacticalFactor[]; cons: TacticalFactor[]; signal: 'STRONG'|'MODERATE'|'WEAK'
  keyRisk: string; summary: string; referee: Referee
  advancedStats?: {...} | null; refereeProfile?: {...} | null
}

interface TicketLegData {
  flag: string; match: string; market: string        // market_label (español)
  prob: number; odds: number; ev: number
  xgHome?: number|null; xgAway?: number|null
  fairProb?: number|null; bookmakerProb?: number|null
  edge?: number|null; kellyStake?: number             // stake sugerido Quarter-Kelly
  varianceNote?: string; reasoning?: string; confidenceScore?: number
}

interface Ticket {
  mode: Mode; glyph: string; combinedOdds: number; confidence: number; evAverage: number
  legs: TicketLegData[]; correlation: string; correlationPositive: boolean
  analysis: string; pros: string[]; cons: string[]; rationale: string[]
  optimizedCount?: boolean; originalRequested?: number|null
  replacementCandidates?: TicketLegData[]             // candidatos del rotador
}
```

### A.2 Modelo Poisson (`buildModel`)

- `poissonPmf(λ, k)`, `goalDistribution(λ, buckets)` (último bucket "≥ N"), `buildModel(λH, λA)` con **grid 9×9** → `{home, draw, away, over25, btts, topScores[5], mostLikely}`.
- `expectedValue(p, odds) = p(odds−1) − (1−p)`; `impliedProbability = 1/odds`.
- `marketRows(match, model)` → 5 filas (`Gana Local`/`Empate`/`Gana Visitante`/`Mas de 2.5 Goles`/`Ambos Anotan`) con `{key, label, probability, odds, implied, edge, ev, verdict}`; **veredicto por edge:** `≥ +3%` → `EV+`; `≥ 0` → `MARGINAL`; `≥ −3%` → `NO EDGE`; resto → `AVOID`.
- `bestOpportunity(rows)` → mejor por edge con `edge ≥ 0.03`, si no `null`.

### A.3 Respuestas backend mapeadas (`lib/api.ts`)

```ts
// POST /api/v1/tickets/generate  (body: {modes: string[], league_keys?, selection_count?, markets?, date_filter?})
interface TicketFetchResult {
  tickets: Ticket[]; totalEvOpportunities: number; matchesAnalyzed: number; generatedAt: string
}
// POST /api/v1/tickets/save → SavedTicketRecord { id, ticket_data: Ticket, status: 'PENDING'|'WON'|'LOST'|'VOID', total_odds, total_ev, created_at }
// POST /api/v1/tickets/claim  → { claimed_count, message }        (multi-tenancy)
// GET  /api/v1/tickets/history → SavedTicketRecord[]
// PATCH /api/v1/tickets/{id}/status → SavedTicketRecord
// GET  /api/v1/matches/?limit=200&include_upcoming=true&include_finished=true[&date_filter=YYYY-MM-DD]
// GET  /api/v1/leagues/?date=YYYY-MM-DD → { leagues: LeagueData[], total }
// GET  /api/v1/matches/{id} + GET /api/v1/predictions/{id}  (paralelos)
// GET  /api/v1/matches/{id}/h2h → { match_id, total, h2h[], home_form[], away_form[] }
```

```ts
interface LeagueData { key: string; group?: string; id: number; external_id: number
  name: string; country: string|null; logo_url: string|null; tier: string|null; active_matches: number }

interface EnrichedMatch extends Match {
  probabilities: { home_win; draw; away_win; over_2_5; over_1_5 }
  evAnalysis: Array<{ market: string; probability: number; odds: number; edge: number; ev: number; verdict: string }>
  confidenceScore: number; riskLevel: string; tacticalNarrative: string; tacticalHeadline: string
  llmModelUsed: string   // 'Groq' / 'Gemini' / 'none'
  tacticalAnalysis: { goals_narrative; cards_narrative; corners_narrative; overall_confidence; data_completeness_score } | null
  betBuilder: Array<{ profile: string; label: string;
    selections: Array<{ market_name; label; probability; odds_estimate }>;
    combined_odds: number; combined_probability: number }>
}
```

### A.4 Ejemplo de contrato (JSON conceptual)

```jsonc
// GET /api/v1/predictions/123 (mapeado a EnrichedMatch)
{
  "match_id": 123,
  "lambda_home": 1.84, "lambda_away": 0.97,
  "probabilities": { "home_win": 0.58, "draw": 0.23, "away_win": 0.19, "over_2_5": 0.61, "over_1_5": 0.83 },
  "confidence_score": 74, "risk_level": "MEDIUM",
  "ev_analysis": [
    { "market": "CORNERS_OVER_8_5", "our_probability": 0.56,
      "bookmaker_implied_probability": 0.48, "bookmaker_odds": 2.08,
      "edge_percentage": 0.08, "expected_value": 0.166, "verdict": "POSITIVE_EV" }
  ],
  "tactical_analysis": { "llm_model_used": "groq", "data_completeness_score": 0.92, "match_preview_headline": "…" },
  "bet_builder": [ { "profile": "MODERATE", "label": "…", "selections": [ { "label": "…", "odds_estimate": 1.75 } ],
                     "combined_odds": 3.42, "combined_probability": 0.29 } ]
}
```

## Apéndice B — Normalizaciones y reglas de datos

- **Mapa de estados** (códigos API-Football → interno): `1H/2H/ET→IN_PLAY`, `HT/BT/P→PAUSED`, `NS/TBD/POSTPONED/NOT_STARTED/UPCOMING→SCHEDULED`, `FT/AET/PEN/CANCELLED/ABANDONED→FINISHED`, etc.
- **Horarios:** siempre `toLocaleTimeString('en-US', {timeZone:'America/Bogota'})` + sufijo ` COT`.
- **Dedupe de partidos** (`dedupeMatches`): clave por `liga + nombres normalizados`; similitud Jaccard de tokens ≥ 0.85 con ventana de 2 h; conserva el registro más "rico" (`λ +4`, cuotas +2, marcador +1); normaliza tildes/abreviaturas (`Independ.→Independiente`, elimina `fc/cf/if/ff/bk/aif`).
- **Convención de marcadores:** `0` es válido; solo `null/undefined` significa "sin datos".

## Apéndice C — Componentes presentes pero no conectados (código sin uso activo)

| Componente | Estado |
|---|---|
| `components/betmind/odds-pill.tsx`, `score-heatmap.tsx`, `poisson-modal-chart.tsx`, `referee-widget.tsx`, `trend-pills.tsx`, `insufficient-data-card.tsx`, `mode-selector.tsx`, `ev-badge.tsx`, `match-comparison-bars.tsx`, `confidence-bar.tsx` | Definidos, **nunca importados** por el árbol de render |
| `components/betmind/team-logo.tsx` | Reemplazado por `components/ui/team-logo.tsx` (3 tiers) |
| `page.tsx` (detalle): `EVTable`, `AdditionalMarkets`, `ArbitroTab`, render local `BetBuilder`, `SignalCard` | Código muerto dentro del archivo (la tab bar solo usa preview/markets/builder/h2h) |
| `MarketTable` | Importado en `page.tsx` pero solo usado por `EVTable` (muerto) |
| Tab `Escáner` del dashboard | UI de subida de imágenes **sin backend conectado** (placeholder intencional) |

## Apéndice D — Resumen de flujos críticos (checklist para IA externa)

1. **Auditoría → Señal:** `fetchMatches` → `MatchCard` (Alpha Strip) → `/partidos/[id]` → `fetchMatchPrediction` + `fetchMatchH2H` → 4 tabs.
2. **Valor:** umbral universal `edge ≥ 0.03` (+3%) para `EV+`; `bestOpportunity`; `POSITIVE_EV` cuando `ev > 0`.
3. **Boleto:** `TicketGenerator` (2–7 patas, 3 perfiles, rangos de cuota, categorías de mercado, presets/ligas personalizadas) → `fetchTickets` → `TicketLeg` (ficha cuantitativa + rotador) → `Guardar en Ledger Cuantitativo` → `POST /tickets/save` (+fallback localStorage) → `TrackingPanel` (claim → `/tickets/claim`, historial, estados PENDING/WON/LOST/VOID).
4. **Export:** Canvas PNG 1200px + Web Share API con archivos + fallback de descarga.
5. **i18n:** toda clave técnica pasa por `formatMarketName`; horarios y fechas siempre en `America/Bogota` con locale `es-CO`.

---

# SECCIÓN 6: BRIEF DE CRÍTICA TOTAL (mandato para quien recibe este documento)

> **Qué es esta sección:** el encargo de trabajo de este documento. Contiene (a) las reglas del juego de la crítica y (b) un inventario exhaustivo de frentes de evaluación, todos formulados como **preguntas abiertas sin respuesta**. Nada de esto está resuelto: el crítico debe responderlo todo con criterio propio, sin piedad y sin dejarse influir por lo que existe.
>
> **Por qué:** este producto se venderá por suscripción. Las secciones 1–5 son solo evidencia del estado actual; **nada de lo descrito es un aval de calidad**. La existencia de una pantalla, un componente o un texto en el código no significa que deba existir.
>
> **Instrucción directa al crítico:** no digas que algo "está bien" para luego proponer ajustes. Si algo no convence —un concepto, una pantalla completa, la marca, el modelo de producto—, dila directamente y propón el reemplazo total si hace falta. Asume que todo es mejorable, incluidas las bases: el concepto de dashboard, el público objetivo, el idioma, el formato "terminal", los umbrales numéricos, los textos y los datos mostrados.

---

## 6.1 Reglas del juego (leer antes de criticar)

1. **Nada está bien por defecto.** Cuestiona todo: concepto, arquitectura, estética, copy, datos, números, negocio.
2. **No valides.** Está prohibido abrir con "la base es buena", "está bien estructurado", "me gusta que…" u otros avales. Ve directo al problema.
3. **No te dejes guiar por lo existente.** Los mapas ASCII, contratos y descripciones son evidencia forense del estado actual, no una referencia de diseño a preservar. Si el dashboard entero sobra y el producto debería ser otra cosa, dilo.
4. **Critica también lo invisible:** datos y umbrales, mensajes, estados, rendimiento, accesibilidad, coherencia interna, promesas rotas (botones que solo muestran toasts), y todo lo que afecte la confianza de un usuario que pagará dinero.
5. **Toda crítica debe sostenerse en el negocio:** ¿esto ayuda a convertir visitantes en suscriptores, a retenerlos y a justificar el precio?
6. **Libertad absoluta de propuesta:** rediseñar desde cero, borrar, fusionar, renombrar, cambiar de soporte (PWA, app), cambiar la marca. Todo es válido.

## 6.2 Inventario de frentes de crítica (preguntas abiertas)

### A. Concepto y modelo de producto
- ¿El concepto "terminal cuantitativo para apostadores serios" es el correcto? ¿Existe un público más amplio que se esté perdiendo?
- ¿Esto es un dashboard, una app, un servicio de alertas, un tipster digital, una herramienta de análisis? ¿Debería ser otra cosa?
- ¿El nombre, la identidad y el tono ("Quant Terminal", "Signal Desk", "MODO EDGE/VALUE/BOLD") comunican valor o alejan al comprador promedio?
- ¿La estética "trading/terminal" es una ventaja o una barrera para vender a no-expertos?
- ¿Qué debería ver un usuario nuevo en su PRIMERA pantalla? ¿La actual sirve?
- ¿El español fijo es suficiente para un producto vendible?

### B. Arquitectura de la información y navegación
- ¿Tres pestañas (Boletos / Partidos / Escáner) son la organización correcta? ¿Qué alternativas existen (rutas reales, una sola vista, dashboard por rol)?
- ¿El sidebar de ligas aporta en todas las vistas o estorba? ¿Cuándo debe aparecer?
- ¿La cadena "pestaña → fecha → liga → partido → detalle" es la correcta? ¿Faltan o sobran niveles (jornada, competición, día)?
- ¿Qué información debería estar siempre fija y cuál oculta?
- ¿El viaje "señal +EV → partido → boleto" es corto y natural? ¿Cuántos clics cuesta?
- ¿Faltan búsqueda global, atajos, favoritos o historial de navegación?

### C. Layout, jerarquía y densidad
- ¿Cada pantalla tiene UN propósito y UN CTA principal? ¿Cuál es en cada caso? ¿Alguno compite?
- ¿La densidad de información es correcta? ¿Demasiada para novatos, insuficiente para expertos? ¿Debe existir modo compacto/detallado?
- ¿Los datos críticos (cuota, EV, probabilidad, hora) están donde el ojo mira primero?
- ¿Existe un sistema de contenedores consistente o las tarjetas/acordeones/tablas/paneles compiten entre sí?
- ¿Las columnas fijas (100px/180px) de las filas de partido funcionan en todos los tamaños de pantalla?
- ¿Los widgets "hero" (MatchHero, SignalRail, ConfidenceBar) aportan o duplican información y añaden ruido?
- ¿El scroll largo es el patrón correcto en el detalle de partido y el generador?

### D. Tipografía
- ¿El uso masivo de uppercase y microtipografías (9–11px) es legible y vendible, o es una estética que cansa?
- ¿Tres familias (Inter, IBM Plex Mono, Playfair) son necesarias? ¿Cuál debería liderar la identidad?
- ¿Los kickers "terminal" son marca o muletilla sobreutilizada?
- ¿Los números tabulares se ven coherentes en todas las superficies?
- ¿La escala tipográfica es intencional o arbitraria? ¿Dónde rompe?

### E. Color
- ¿La paleta obsidiana + menta transmite confianza financiera o parece un clon de terminal genérico (Binance/Bybit)?
- ¿Conviven 3 verdes distintos? ¿Es un error a corregir o la semilla de un sistema?
- ¿El color comunica estado de forma consistente (positivo/negativo/neutro) en TODAS las superficies, o hay contradicciones?
- ¿El color es semántico o decorativo? ¿Dónde se usa mal?
- ¿El dark-only es una decisión correcta? ¿Se pierde mercado o accesibilidad sin tema claro?
- ¿Usar primary para "local" y warning para "visitante" es bueno, o confunde con el color semántico de riesgo?

### F. Visualización de datos
- ¿Cada gráfico (PoissonMiniChart, radar táctico, barras duales, heatmap, barras de probabilidad) se lee de inmediato? ¿Cuáles sobran?
- ¿Las barras "MODELO vs CASA" explican el edge mejor que un número? ¿O son ruido?
- ¿El radar de 5 ejes aporta información accionable o es decoración?
- ¿Cómo se compara esto con el estándar de la industria (SofaScore, Oddspedia, ValueStats, Unibet insights)?
- ¿Los formatos numéricos (decimales, signos, unidades) son correctos en todas partes? ¿Dónde cambian entre superficies?
- ¿Marcador probable, top marcadores y heatmap son herramientas útiles para apostar o datos de relleno?

### G. Copy, tono y contenido
- ¿Los nombres de mercado en español formal son los correctos para apostadores? ¿Alguno es confuso?
- ¿Los microtextos ("Reducimos tu boleto de X a Y para proteger tu Bankroll", "Protege tu Capital", "MODO ANÓNIMO ACTIVO", "Optimizado algorítmicamente") suenan a marca, a sistema o a traducción automática?
- ¿Los disclaimers legales son consistentes entre superficies? ¿Son suficientes?
- ¿El producto explica qué es EV, xG, edge, desmarquinización y quarter-Kelly, o asume conocimiento?
- ¿Los mensajes de vacío/error ayudan o frustran?
- ¿El tono vende confianza o suena a clon genérico de "IA de apuestas"?

### H. Estados y comportamiento
- ¿Los estados de carga, vacío y error existen en TODAS las vistas? ¿Dónde faltan o son inconsistentes?
- ¿Los comportamientos que solo muestran un toast (guardar estrategia del Bet Builder, notificar confirmación de árbitro, Conectar Cuenta PRO, Añadir al boleto) deben existir mientras no persistan nada?
- ¿La regeneración automática del boleto al cambiar filtros es buena UX o desorienta al usuario?
- ¿La rotación de patas (swap) es descubrible? ¿El popover de EV es el patrón correcto o debería ser otra cosa (bottom sheet, modal, expand)?
- ¿Qué pasa con red caída, datos viejos, partidos sin cuotas, predicciones vacías, árbitro sin confirmar? ¿Cada caso tiene un estado digno?

### I. Móvil y responsive
- ¿La experiencia móvil es de primera clase o un desktop comprimido?
- ¿Los grids de 3–4 columnas y las tablas son utilizables en pantallas pequeñas?
- ¿El popover de la ficha cuantitativa funciona táctil? ¿Debería ser bottom sheet?
- ¿Los targets táctiles cumplen 44px en todos los controles (rotador, selectores, chips)?
- ¿El producto debería ser instalable (PWA) y poder notificar?

### J. Accesibilidad e inclusión
- ¿Los contrastes cumplen AA en todos los textos y superficies?
- ¿Todo es navegable por teclado (tabs, popovers, acordeones, drawer)?
- ¿Los lectores de pantalla reciben labels, roles y estados anunciados?
- ¿Se respetan prefers-reduced-motion, zoom 200% y ambas orientaciones?
- ¿El color es el único canal que comunica estados? ¿Qué pasa a un daltónico?

### K. Rendimiento y técnica
- ¿Los fetches en paralelo por cada cambio de fecha son óptimos? ¿Hay caché o se vuelve a pedir todo?
- ¿Los límites actuales (200 partidos, 10 boletos en el ledger, 5 señales, top 5 marcadores) son decisiones de diseño o accidentes?
- ¿El bundle contiene código muerto que ensucia el producto?
- ¿El detalle de partido (SVGs, grids, narrativas) renderiza pesado?
- ¿La app funciona offline? ¿Debería?
- ¿El timeout de 12s y la estrategia de errores son los correctos?

### L. Flujos de usuario completos (crítica de journey)
- **Nuevo usuario:** entra por primera vez → ¿entiende qué es, qué puede hacer y qué le conviene? ¿Se queda o se va en 30 segundos?
- **Señal:** encuentra un +EV → ¿llega al boleto en pocos clics? ¿Confía en lo que ve o duda?
- **Historial:** quiere guardar su progreso → ¿puede? ¿En cuántos pasos? ¿Y mañana desde otro dispositivo?
- **Pago:** quiere pagar por esto → ¿existe el camino? ¿Qué compra exactamente? ¿Vale el precio?
- **Retorno:** vuelve al día siguiente → ¿encuentra su estado (liga, fecha, filtros, pestaña) o empieza de cero?

### M. Monetización y retención
- ¿Qué debe ser gratuito, qué PRO y qué no debería existir? (decisión abierta, sin respuesta aquí)
- ¿El "MODO ANÓNIMO ACTIVO" permanente ayuda o lastima la conversión?
- ¿Qué métricas del usuario justifican renovar mes a mes (ROI, hit rate, crecimiento de bankroll)?
- ¿Cómo se demuestra valor real sin inflar resultados?
- ¿Qué feature inexistente pagaría primero un usuario? ¿Cuál haría que un PRO se quedara?
- ¿Existen palancas para cobrar más (API, alertas tiempo real, multi-bookmaker, históricos ilimitados)?

### N. Qué quitar (crítica de lo existente)
- ¿Qué pantallas, componentes, secciones, textos o datos sobran por completo? (candidatos a examinar, sin que esto sea una respuesta: Escáner sin backend, doble vista de pronósticos en el detalle, widgets de árbitro redundantes, contador `/26` fijo, pills de ligas, panel de 4 métricas, etc.)
- ¿Qué se puede fusionar sin perder función?
- ¿Qué simplificación cambia la percepción de "complejo" a "confiable"?

### O. Qué agregar (futuro)
- ¿Qué features convertirían esto en una suscripción sostenible? (propón tu propia lista y defiéndela; puede coincidir o no con ideas como alertas +EV, gestión de bankroll, reportes de ROI, escáner de boletos por imagen, comparación de casas, comunidad, API pública…)
- ¿Qué ventaja competitiva se debe construir primero para que la IA sea creíble y verificable?
- ¿Qué se necesita para vender: landing, planes y precios, demo interactiva, prueba social, garantías?
- ¿Qué datos o visualizaciones harían que un apostador profesional pague sin dudar?

## 6.3 Anti-reglas (lo que NO debe hacer el crítico)

- No dar por bueno nada por el hecho de existir.
- No proponer cambios cosméticos si el problema es estructural.
- No preservar componentes por sentimentalismo o esfuerzo invertido en ellos.
- No decir "esto es cuestión de gustos" sin tomar postura.
- No ignorar el negocio: cada recomendación debe poder defenderse en términos de conversión o retención.
- No dejar preguntas sin respuesta: si algo no puede decidirse sin el dueño del producto, listarlo explícitamente como decisión pendiente del dueño al final del informe.

---

*Fin del brief. A partir de aquí, el crítico tiene la palabra.*
