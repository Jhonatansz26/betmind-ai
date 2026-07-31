# DEEP_UI_AUDIT_ANTIGRAVITY.md
## Auditoría Visual & Técnica — BetMind AI · Antigravity Design Review

> Fecha: 2026-07-30 · Código: rama `main` · Herramienta: Claude Sonnet 4.6 Thinking + Emil Kowalski Design Engineering + Vercel Web Interface Guidelines

---

## 1. Puntaje de Perfección Visual — Diagnóstico Antigravity

| Dimensión                      | Score /10 | Veredicto                                                              |
|-------------------------------|-----------|------------------------------------------------------------------------|
| **Token System & Palette**     | 8.5       | Paleta dark bien definida, variables semánticas coherentes             |
| **Tipografía & Escala**        | 7.0       | Inter + Playfair correctos; la escala text-[9px] a text-3xl es irregular |
| **Alineación & Ritmo Vertical**| 6.5       | Inconsistencias px/py entre match-card y modal, stagger gaps mixtos   |
| **Contraste & Accesibilidad**  | 7.0       | text-zinc-* hardcodeados en modal rompen WCAG en algunos fondos       |
| **Animaciones & Motion**       | 8.0       | reduced-motion correcto, easings buenos; accordion usa keyframe no interruptible |
| **Coherencia de Componentes**  | 6.0       | Modal usa paleta zinc-* propia — fractura sistémica con el resto de la app |
| **Badges & Iconografía**       | 7.5       | Live dots correctos; iconos aria-hidden bien marcados                  |
| **Rendimiento Percibido**      | 7.5       | Skeleton apropiado; tabular-nums en cuotas; ConfidenceBar usa width animado |

### Puntaje Global: 7.1 / 10

**Diagnóstico:** El sistema de diseño tiene bases sólidas — paleta oscura bien calibrada, fuentes premium (Inter + Playfair), tokens semánticos para surface/muted/positive/negative. Sin embargo, match-modal.tsx (56KB, 1264 líneas) es un **universo paralelo**: usa zinc-* hardcodeados ignorando el sistema de tokens establecido en globals.css, creando una fractura estilística mayor. El ritmo vertical entre MatchCard y TicketCard es inconsistente en sus paddings. La escala tipográfica tiene saltos bruscos de text-[9px] a text-3xl sin pasos intermedios definidos.

---

## 2. Análisis Pixel-Perfect por Componente

---

### 2.1 Header & Top Navigation (top-nav.tsx)

**Fortalezas:**
- h-14 fijo con sticky top-0 z-40 — correcto para scroll
- backdrop-blur-md con bg-background/85 — glassmorphism apropiado
- Logo "BetMindAI" con badge text-[10px] en rounded-full — elegante
- Live dot con aria-hidden correcto
- BottomNav con grid-cols-3 para móvil — responsive correcto

**Problemas detectados:**

| # | Problema | Archivo:Línea | Clase implicada | Impacto |
|---|----------|---------------|-----------------|---------|
| N1 | El logo usa <p> como contenedor — semánticamente incorrecto para una marca | top-nav.tsx:39 | `<p className="flex shrink-0 items-center...">` | Bajo |
| N2 | lang="en" en <html> no coincide con contenido en español | layout.tsx:50 | `lang="en"` | Medio (SEO) |
| N3 | Tab buttons sin focus-visible:ring-* explícito — outline global puede perderse | top-nav.tsx:58-63 | `rounded-md px-3 py-1.5` | Medio |
| N4 | Avatar AvatarFallback sin aria-label descriptivo para lectores de pantalla | top-nav.tsx:79-81 | `<Avatar className="size-7">` | Bajo |
| N5 | "MIEMBRO EDGE" badge solo visible en lg:inline-flex sin alternativa md | top-nav.tsx:76 | `lg:inline-flex` | Bajo |

---

### 2.2 Sidebar de Ligas Activas (league-sidebar.tsx)

**Fortalezas:**
- Agrupación EUROPA/AMERICA con label text-[10px] tracking-widest
- Estado del Modelo con <dl>/<dt>/<dd> semánticamente correcto
- Botón "Todas las Ligas" activo usa bg-primary text-primary-foreground

**Problemas detectados:**

| # | Problema | Archivo:Línea | Clase implicada | Impacto |
|---|----------|---------------|-----------------|---------|
| S1 | Botón "Todas las Ligas" px-3 py-2 vs items de liga px-2.5 py-1.5 — 5px diferencia horizontal | league-sidebar.tsx:108 vs 41 | `px-3 py-2` vs `px-2.5 py-1.5` | Medio |
| S2 | Label "Ligas Activas" text-[11px] vs labels de región text-[10px] — jerarquía opaca | league-sidebar.tsx:102 vs 31 | `text-[11px]` vs `text-[10px]` | Medio |
| S3 | gap-6 entre sección principal y grupos vs gap-5 entre grupos — ritmo inconsistente | league-sidebar.tsx:100,118 | `gap-6` vs `gap-5` | Bajo |
| S4 | Badge de conteo sin tabular-nums explícito — salta de ancho al pasar de 1 a 2 dígitos | league-sidebar.tsx:53 | `num shrink-0 rounded px-1.5 py-0.5` | Bajo |

---

### 2.3 Tarjeta de Partidos (match-card.tsx + league-accordion.tsx)

**Fortalezas:**
- Grid de 3 columnas (100px + flex-1 + 180px) — alineación tabular excelente
- EV+ glow con shadow-[0_0_12px_-4px_var(--positive)] + ev-glow animation — premium
- Live border con border-positive/30 — feedback de estado correcto
- tabular-nums en cuotas y probabilidades

**Problemas detectados:**

| # | Problema | Archivo:Línea | Clase implicada | Impacto |
|---|----------|---------------|-----------------|---------|
| M1 | Columna 3 w-[180px] puede comprimir Columna 2 (flex-1) <120px con nombres largos | match-card.tsx:160 | `w-[180px] shrink-0` | Alto |
| M2 | Score activo text-lg ml-auto colisiona con truncate del nombre en nombres largos | match-card.tsx:100 | `num ml-auto text-lg font-black` | Alto |
| M3 | Badge LIVE gap-1.5 vs FINALIZADO sin dot — diferencia de anchura no compensada | match-card.tsx:25-44 | `px-2 py-0.5` en ambos | Bajo |
| M4 | Badge "PROGRAMADO" opacity-0 group-hover:opacity-100 — invisible en touch sin hover | match-card.tsx:80 | `group-hover:opacity-100` | Medio |
| M5 | Sub-strip xG: PoissonMiniChart altura vs text-[10px] baseline desalineados | match-card.tsx:138-148 | `flex items-center gap-2` | Medio |
| M6 | Doble borde: accordion bg-surface/40 + MatchCard bg-card crean artefacto visual | league-accordion.tsx:31,67 | `bg-card/80` + `bg-card` | Bajo |
| M7 | accordion-down usa keyframe max-height 0→2000px — no interruptible, causa layout reflow | globals.css:171-179 | `animation: accordion-down` | Medio |

---

### 2.4 Tarjeta de Boletos (ticket-card.tsx + ticket-leg.tsx)

**Fortalezas:**
- Accent strip de 3px top — diferenciación EDGE/VALUE/BOLD excelente
- Combined odds en text-2xl font-bold font-mono — jerarquía numérica correcta
- Footer "pinned" con mt-auto — layout flex correcto para height uniforme
- Stagger animation con animationDelay prop — micro-interacción premium

**Problemas detectados:**

| # | Problema | Archivo:Línea | Clase implicada | Impacto |
|---|----------|---------------|-----------------|---------|
| T1 | <li> dentro de <div> sin <ul> padre — semánticamente inválido | ticket-card.tsx:61 + ticket-leg.tsx:10 | div sin ul contenedor | Alto (a11y) |
| T2 | GlobeIcon text-subtle vs span text-muted-foreground — dos tokens distintos mismo nivel | ticket-leg.tsx:17-21 | `text-subtle` vs `text-muted-foreground` | Bajo |
| T3 | Escala numérica: text-[11px] en 1X2, text-base en legs, text-2xl combined — sin gradación coherente | ticket-leg.tsx:29 vs match-card.tsx:186 vs ticket-card.tsx:46 | Escala numérica entre componentes | Medio |
| T4 | Disclaimer text-[10px] leading-tight — comprimido en múltiples líneas en mobile | ticket-card.tsx:74 | `text-[10px] leading-tight` | Bajo |

---

### 2.5 Modal de Análisis Detallado (match-modal.tsx)

**Fractura de sistema de diseño más grave del proyecto.**

El modal usa zinc-* hardcodeados en lugar de los tokens semánticos del sistema. Esto crea una inconsistencia visual sistémica — el modal tiene un carácter visualmente distinto al resto de la app.

**Problemas detectados:**

| # | Problema | Archivo:Línea | Clase implicada | Impacto |
|---|----------|---------------|-----------------|---------|
| Mo1 | CRITICO: DialogContent usa bg-[#09090b] hardcodeado en lugar de bg-background | match-modal.tsx:1222 | `bg-[#09090b]` | Alto |
| Mo2 | CRITICO: Cards internos usan bg-zinc-900/60 border-zinc-800/80 en lugar de bg-surface border-border | match-modal.tsx:494,543,608+ | `bg-zinc-900/60 border-zinc-800/80` | Alto |
| Mo3 | CRITICO: Textos secundarios text-zinc-500/400/600 vs tokens text-subtle/muted-foreground | match-modal.tsx:167,268,377+ | `text-zinc-*` | Alto |
| Mo4 | Dos fondos sticky distintos: ModalHeader bg-zinc-950/95 vs TabBar bg-[#09090b]/95 | match-modal.tsx:298 vs 1230 | `bg-zinc-950/95` vs `bg-[#09090b]/95` | Alto |
| Mo5 | RISK_COLORS usa bg-emerald/amber/rose en lugar de tokens positive/warning/negative | match-modal.tsx:186-188 | `bg-emerald-*` en lugar de `bg-positive` | Medio |
| Mo6 | sectionLabel() retorna <p> en lugar de <h3> — jerarquía semántica incorrecta | match-modal.tsx:165-170 | `<p className="uppercase">` | Medio |
| Mo7 | TabBar activo usa text-indigo-400/border-indigo-400 hardcodeado vs text-primary | match-modal.tsx:1237-1240 | `text-indigo-400 border-indigo-400` | Bajo |
| Mo8 | CTA "Añadir al Boleto" sin focus-visible:ring — sin feedback de focus con teclado | match-modal.tsx:589 | ausencia de `focus-visible:` | Medio |
| Mo9 | Botón "Guardar" sin type="button" — puede activarse accidentalmente con Enter | match-modal.tsx:478 | ausencia de `type="button"` | Medio |
| Mo10 | DialogTitle solo para equipo local — equipo visitante en <span> sin título ARIA | match-modal.tsx:328-356 | `<DialogTitle>` vs `<span>` | Alto (a11y) |
| Mo11 | BLOCKER PRODUCCION: text-${color} en template literal — Tailwind purga clases dinámicas | match-modal.tsx:380 | `text-${color}` dinámico | Alto (build) |
| Mo12 | Empty states inconsistentes: EmptyCard card vs dashed-border | match-modal.tsx:176 vs 1113 | Dos estilos de empty state | Bajo |

---

### 2.6 Análisis Cross-Componente: Escala Tipográfica

**Escala identificada (de menor a mayor):**

```
text-[9px]  → elapsed badge en modal — BAJO WCAG mínimo (~10px)
text-[10px] → labels secundarios, badges, disclaimers
text-[11px] → badges principales, sub-labels
text-xs     → 12px — texto de apoyo
text-sm     → 14px — nombres equipos, texto principal
text-base   → 16px — odds en legs
text-lg     → 18px — scores live en card
text-xl     → 20px — h1 sección, números árbitro
text-2xl    → 24px — combined odds, scores modal
text-3xl    → 30px — cuotas BetBuilder — SALTO BRUSCO sin paso intermedio
```

**Gap crítico:** Salto directo text-2xl (24px) → text-3xl (30px) sin escala intermedia. text-[9px] incumple WCAG minimum legibility.

---

## 3. Micro-Desalineaciones Exactas (Lista Completa)

| # | Descripción | Archivo | Línea | Clase |
|---|---|---|---|---|
| 1 | Clases Tailwind dinámicas text-${color} — ROTO EN PRODUCCIÓN | match-modal.tsx | 380 | `text-${color}` template literal |
| 2 | <li> sin <ul> padre — semánticamente inválido | ticket-card.tsx | 61 | div contenedor en lugar de ul |
| 3 | DialogTitle ausente para equipo visitante | match-modal.tsx | 354-355 | `<span>` en lugar de titulo ARIA |
| 4 | bg-[#09090b] hardcodeado en DialogContent | match-modal.tsx | 1222 | `bg-[#09090b]` |
| 5 | Fractura total de tokens zinc-* vs sistema semántico | match-modal.tsx | 167,298,494+ | `text-zinc-*`, `bg-zinc-*` sistema paralelo |
| 6 | Dos fondos sticky distintos en mismo modal | match-modal.tsx | 298 vs 1230 | `bg-zinc-950/95` vs `bg-[#09090b]/95` |
| 7 | Score ml-auto + truncate — colapso con nombres largos | match-card.tsx | 96-103 | `truncate text-sm` + `ml-auto` |
| 8 | lang="en" en app en español | layout.tsx | 50 | `lang="en"` |
| 9 | Accordion keyframe max-height — no interruptible, causa reflow | globals.css | 171-179 | `animation: accordion-down` |
| 10 | CTA "Añadir al Boleto" sin focus-visible:ring | match-modal.tsx | 589 | ausencia de `focus-visible:` |
| 11 | Badge "PROGRAMADO" hover-only sin fallback touch | match-card.tsx | 80 | `group-hover:opacity-100` |
| 12 | sectionLabel() retorna <p> en lugar de <h3> | match-modal.tsx | 165-170 | `<p>` semántico incorrecto |
| 13 | text-[9px] en elapsed — bajo mínimo WCAG legibility | match-modal.tsx | 347 | `text-[9px]` |
| 14 | px-3 vs px-2.5 entre "Todas las Ligas" y items liga | league-sidebar.tsx | 108 vs 41 | `px-3` vs `px-2.5` |
| 15 | gap-6 vs gap-5 en sidebar — ritmo inconsistente | league-sidebar.tsx | 100 vs 118 | `gap-6` vs `gap-5` |
| 16 | RISK_COLORS usa emerald/amber/rose en lugar de positive/warning/negative | match-modal.tsx | 186-188 | `bg-emerald-*` |
| 17 | Botón guardar modal sin type="button" | match-modal.tsx | 478 | ausencia de `type` |
| 18 | <p> logo en TopNav — semánticamente incorrecto | top-nav.tsx | 39 | `<p className="flex...">` |
| 19 | Avatar sin aria-label descriptivo | top-nav.tsx | 79 | `<Avatar>` sin label |
| 20 | text-[10px] vs text-[11px] en labels sidebar — jerarquía opaca | league-sidebar.tsx | 31 vs 102 | `text-[10px]` vs `text-[11px]` |
| 21 | Salto text-2xl → text-3xl sin paso intermedio en BetBuilder | match-modal.tsx | 874 | `text-3xl font-black` |
| 22 | GlobeIcon en TicketLeg sin aria-hidden="true" explícito | ticket-leg.tsx | 18 | `<GlobeIcon>` decorativo sin aria-hidden |
| 23 | Empty states con dos estilos distintos en el modal | match-modal.tsx | 176 vs 1113 | card vs dashed-border |
| 24 | Doble borde visual: accordion wrapper + MatchCard border | league-accordion.tsx | 31 + match-card.tsx:65 | bg-card/80 wrapping bg-card |
| 25 | ConfidenceBar anima width — causa layout reflow en cada frame | confidence-bar.tsx | 67 | `transition-[width] duration-[600ms]` |
| 26 | text-subtle vs text-muted-foreground en mismo nivel en TicketLeg | ticket-leg.tsx | 17-21 | Tokens distintos mismo nivel |
| 27 | TabBar modal usa indigo-400 hardcodeado vs token primary | match-modal.tsx | 1237-1240 | `border-indigo-400 text-indigo-400` |
| 28 | Badge conteo liga sin tabular-nums — salta de ancho con 2 dígitos | league-sidebar.tsx | 53 | Sin `tabular-nums` en contador |

---

## 4. Plan de Perfeccionamiento en Fases

---

### FASE 1 — Correcciones Criticas (Bloqueantes · 1-2 horas)

**P1.1 — BLOCKER: Clases Tailwind dinámicas**
Archivo: match-modal.tsx:380

```tsx
// ANTES — ROTO EN BUILD DE PRODUCCION
<span className={`num text-base font-bold text-${color}`}>

// DESPUES — safe list explícito via lookup object
const COLOR_MAP: Record<string, string> = {
  'indigo-400': 'text-indigo-400',
  'zinc-200': 'text-foreground',
  'amber-400': 'text-warning',
}
<span className={cn('num text-base font-bold', COLOR_MAP[color])}>
```

**P1.2 — lang del documento**
Archivo: layout.tsx:50

```tsx
// ANTES
<html lang="en" ...>
// DESPUES
<html lang="es" ...>
```

**P1.3 — <li> dentro de <div> sin <ul>**
Archivo: ticket-card.tsx:61

```tsx
// ANTES
<div className="flex flex-1 flex-col gap-2 px-4 pb-4">
// DESPUES
<ul className="flex flex-1 list-none flex-col gap-2 px-4 pb-4">
```

**P1.4 — DialogTitle semántico para ambos equipos**
Archivo: match-modal.tsx:328

```tsx
// Añadir DialogTitle oculto que incluya ambos equipos
<DialogTitle className="sr-only">{match.home} vs {match.away}</DialogTitle>
// Los nombres visuales pueden seguir en <span>/<div>
```

**P1.5 — type="button" en botón guardar modal**
Archivo: match-modal.tsx:478

```tsx
<button type="button" onClick={() => setSaved(s => !s)} ...>
```

---

### FASE 2 — Tokenizacion del Modal (Impacto Alto · 3-4 horas)

Reemplazar zinc-* por tokens semánticos en toda match-modal.tsx:

| Clase actual              | Reemplazar con           | Token semántico    |
|--------------------------|--------------------------|-------------------|
| bg-zinc-950/95           | bg-background/95         | --background      |
| bg-zinc-900/60           | bg-surface               | --surface         |
| bg-zinc-800/40           | bg-surface-raised/40     | --surface-raised  |
| bg-zinc-800              | bg-muted                 | --muted           |
| border-zinc-800          | border-border            | --border          |
| border-zinc-700          | border-border/60         | --border          |
| text-zinc-500            | text-subtle              | --subtle          |
| text-zinc-400            | text-muted-foreground    | --muted-foreground|
| text-zinc-300            | text-foreground/80       | --foreground      |
| text-zinc-200            | text-foreground          | --foreground      |
| bg-emerald-*/15          | bg-positive/15           | --positive        |
| text-emerald-400         | text-positive            | --positive        |
| bg-amber-*/15            | bg-warning/15            | --warning         |
| text-amber-400           | text-warning             | --warning         |
| bg-rose-*/15             | bg-negative/15           | --negative        |
| text-rose-400            | text-negative            | --negative        |

**Unificar fondos sticky del modal:**

```tsx
// Un único token para ambas superficies sticky:
const MODAL_STICKY = 'bg-background/95 backdrop-blur-sm border-b border-border'
```

**Elevar sectionLabel a h3:**

```tsx
function SectionLabel({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <h3 className={cn('text-[10px] font-bold text-subtle uppercase tracking-widest', className)}>
      {children}
    </h3>
  )
}
```

---

### FASE 3 — Alineacion Geometrica & Ritmo Vertical (Impacto Medio · 2-3 horas)

**P3.1 — Normalizar padding horizontal de listas a px-4**
Unificar: LeagueSidebar, MatchCard, TicketCard, TrackRow, TicketLeg → todos px-4.

**P3.2 — Unificar gaps de sidebar**

```tsx
// ANTES: gap-6 entre sección y grupos, gap-5 entre grupos
// DESPUES: gap-6 consistente en todo el sidebar
<div className="flex flex-col gap-6">
```

**P3.3 — ConfidenceBar: transform en lugar de width**

```tsx
// ANTES — causa layout reflow cada frame
<div style={{ width: `${width}%` }} className="transition-[width] duration-[600ms]">

// DESPUES — GPU-accelerated sin reflow
<div 
  style={{ transform: `scaleX(${width / 100})` }} 
  className="origin-left transition-transform duration-[600ms] ease-out w-full h-full rounded-full"
/>
```

**P3.4 — Elevacion min-w en columna de equipos del MatchCard**

```tsx
// Añadir min-w explícito para evitar colapso con equipos de nombre largo
<div className="flex min-w-0 flex-1 flex-col gap-1" style={{ minWidth: '140px' }}>
```

---

### FASE 4 — Pulido & Micro-Animaciones (Impacto Estetico · 3-5 horas)

**P4.1 — Accordion interruptible con CSS grid trick**

```css
/* ANTES — keyframe no interruptible con max-height */
@keyframes accordion-down {
  from { max-height: 0; opacity: 0; }
  to { max-height: 2000px; opacity: 1; }
}

/* DESPUES — CSS transition interruptible */
.accordion-wrapper {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows 250ms ease-out;
  opacity: 0;
  transition: grid-template-rows 250ms ease-out, opacity 200ms ease-out;
}
.accordion-wrapper.open {
  grid-template-rows: 1fr;
  opacity: 1;
}
.accordion-wrapper > div { overflow: hidden; }
```

**P4.2 — Escala tipografica consolidada en globals.css**

```css
/* Definir size mínimo: text-[10px] es el mínimo permitido */
/* Eliminar todos los text-[9px] — reemplazar con text-[10px] */
/* Añadir paso intermedio entre text-2xl y text-3xl en BetBuilder */
```

**P4.3 — Fallback touch para badge PROGRAMADO**

```tsx
// Tailwind v4 media query en clase:
<span className={cn(
  'inline-flex items-center rounded-full border...',
  'opacity-0 transition-opacity group-hover:opacity-100',
  '[@media(hover:none)]:opacity-100'
)}>
```

**P4.4 — focus-visible en CTA del modal**

```tsx
<button className="... focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background">
  Añadir al Boleto
</button>
```

**P4.5 — Logo en TopNav con semantica correcta**

```tsx
// ANTES
<p className="flex shrink-0 items-center...">

// DESPUES — Link a home con aria-label
<Link href="/" aria-label="BetMind AI - Inicio" className="flex shrink-0 items-center...">
```

---

## 5. Resumen Ejecutivo de Prioridades

```
BLOCKER DE PRODUCCION:
  → match-modal.tsx:380 — clases Tailwind dinamicas via template literal
    (las clases son purgadas por Tailwind en build)

ACCESIBILIDAD CRITICA:
  → match-modal.tsx:354 — DialogTitle ausente para equipo visitante
  → ticket-card.tsx:61  — <li> sin <ul> padre
  → layout.tsx:50       — lang="en" en app en espanol
  → match-modal.tsx:589 — CTA sin focus-visible:ring
  → ticket-leg.tsx:18   — GlobeIcon decorativo sin aria-hidden

COHERENCIA SISTEMICA:
  → match-modal.tsx (todo el archivo) — fractura zinc-* vs tokens semanticos
  → match-modal.tsx:298 vs 1230      — dos fondos sticky distintos mismo modal
  → match-modal.tsx:186-188          — RISK_COLORS con colores sin tokens

PERFORMANCE:
  → confidence-bar.tsx:67 — transition-[width] causa reflow (usar scaleX)
  → globals.css:173       — max-height animado causa layout reflow (usar grid trick)

MICRO-ALINEACIONES:
  → league-sidebar.tsx:108 — px-3 vs px-2.5 en boton "Todas las Ligas"
  → match-card.tsx:80      — badge hover-only sin fallback touch
  → league-sidebar.tsx:100 — gap-6 vs gap-5 ritmo inconsistente
  → match-modal.tsx:347    — text-[9px] bajo WCAG minimum
  → match-modal.tsx:874    — salto tipografico text-2xl a text-3xl
```

---

*Generado por Antigravity · Claude Sonnet 4.6 Thinking · Revision completa del source code — sin modificaciones al codigo durante esta auditoria.*
