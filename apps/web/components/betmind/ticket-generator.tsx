'use client'

import * as React from 'react'
import {
  Copy,
  Star,
  RefreshCw,
  Minus,
  Plus,
  Zap,
  Check,
  AlertCircle,
  Target,
  Flag,
  Square,
  Globe,
} from 'lucide-react'
import { toast } from 'sonner'

import { type Match, type Ticket, MODE_META } from '@/lib/betmind'
import { fetchTickets } from '@/lib/api'
import { formatMarketName } from '@/lib/formatMarketName'
import { resolveLeague } from '@/lib/league-metadata'
import { cn } from '@/lib/utils'
import { addToTracking } from './tracking-panel'

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

type RiskProfile = 'conservative' | 'balanced' | 'aggressive'
type MarketCategory = 'all' | 'goals' | 'corners' | 'cards' | 'shots'

interface GeneratorConfig {
  selectionCount: number
  riskProfile: RiskProfile
  oddsMin: number
  oddsMax: number
  marketCategory: MarketCategory
}

/* ------------------------------------------------------------------ */
/* Constants                                                           */
/* ------------------------------------------------------------------ */

const RISK_PROFILES: Array<{
  key: RiskProfile
  label: string
  sublabel: string
  mode: 'EDGE' | 'VALUE' | 'BOLD'
}> = [
  {
    key: 'conservative',
    label: 'EDGE',
    sublabel: 'Baja Varianza',
    mode: 'EDGE',
  },
  {
    key: 'balanced',
    label: 'VALUE',
    sublabel: '+EV Óptimo',
    mode: 'VALUE',
  },
  {
    key: 'aggressive',
    label: 'BOLD',
    sublabel: 'Alta Varianza',
    mode: 'BOLD',
  },
]

const RISK_MODE_MAP: Record<RiskProfile, 'EDGE' | 'VALUE' | 'BOLD'> = {
  conservative: 'EDGE',
  balanced: 'VALUE',
  aggressive: 'BOLD',
}

const MARKET_CATEGORIES: Array<{
  key: MarketCategory
  label: string
  icon: React.ElementType
  keywords: string[]
}> = [
  { key: 'all', label: 'Todos', icon: Globe, keywords: [] },
  { key: 'goals', label: 'Goles', icon: Target, keywords: ['OVER_', 'UNDER_', 'BTTS', '1X2'] },
  { key: 'corners', label: 'Córneres', icon: Flag, keywords: ['CORNERS_'] },
  { key: 'cards', label: 'Tarjetas', icon: Square, keywords: ['CARDS_'] },
  { key: 'shots', label: 'Remates', icon: Target, keywords: ['SHOTS_'] },
]

const ODDS_PRESETS = [
  { label: '1.5 – 3.0', min: 1.5, max: 3.0 },
  { label: '3.0 – 6.0', min: 3.0, max: 6.0 },
  { label: '6.0+', min: 6.0, max: 50 },
]

/* ------------------------------------------------------------------ */
/* Market category filter helper                                       */
/* ------------------------------------------------------------------ */

function filterLegsByCategory(
  legs: Ticket['legs'],
  category: MarketCategory,
): Ticket['legs'] {
  if (category === 'all') return legs
  const keywords = MARKET_CATEGORIES.find((c) => c.key === category)?.keywords ?? []
  return legs.filter((leg) =>
    keywords.some((kw) => leg.market.toUpperCase().includes(kw)),
  )
}

/* ------------------------------------------------------------------ */
/* Sub-components                                                      */
/* ------------------------------------------------------------------ */

function LegSkeleton() {
  return (
    <div className="flex items-center justify-between rounded-lg border border-border/40 bg-surface/30 px-4 py-3">
      <div className="flex flex-col gap-2 flex-1 pr-4">
        <div className="h-3.5 w-40 skeleton rounded" />
        <div className="h-2.5 w-32 skeleton rounded" />
        <div className="h-2 w-16 skeleton rounded" />
      </div>
      <div className="h-8 w-14 skeleton rounded-md shrink-0" />
    </div>
  )
}

function GeneratorLeg({
  leg,
  index,
}: {
  leg: Ticket['legs'][number]
  index: number
}) {
  const evPositive = leg.ev > 0
  const humanMarket = formatMarketName(leg.market)

  return (
    <li
      title="Cuota de bookmaker comparada contra probabilidad desmarquinizada de modelo Poisson"
      className="stagger-item flex items-center justify-between gap-3 border-b border-border/40 px-3.5 py-2.5 last:border-b-0 transition-colors hover:bg-surface/40"
      style={{ animationDelay: `${index * 55}ms` }}
    >
      <div className="flex min-w-0 flex-col gap-0.5">
        <span className="truncate text-xs font-semibold leading-snug text-foreground">
          {humanMarket}
        </span>
        <span className="block truncate text-[11px] leading-tight text-muted-foreground" title={leg.match}>
          {leg.match}
        </span>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <span className={cn(
          'rounded border px-1.5 py-0.5 font-mono text-xs font-bold tabular-nums',
          evPositive
            ? 'border-positive/20 bg-positive/10 text-positive'
            : 'border-negative/20 bg-negative/10 text-negative',
        )}>
          {evPositive ? '+' : ''}{(leg.ev * 100).toFixed(1)}% EV
        </span>
        <span className="font-mono text-sm font-bold tabular-nums text-foreground">@{leg.odds.toFixed(2)}</span>
      </div>
    </li>
  )
}

/* ------------------------------------------------------------------ */
/* Main Component                                                      */
/* ------------------------------------------------------------------ */

export function TicketGenerator({
  matches,
  onTrack,
}: {
  matches: Match[]
  onTrack?: () => void
}) {
  /* ── Config state ── */
  const [config, setConfig] = React.useState<GeneratorConfig>({
    selectionCount: 3,
    riskProfile: 'balanced',
    oddsMin: 1.80,
    oddsMax: 10.00,
    marketCategory: 'all',
  })

  /* ── Result state ── */
  const [ticket, setTicket] = React.useState<Ticket | null>(null)
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState(false)
  const [generationKey, setGenerationKey] = React.useState(0)
  const [copied, setCopied] = React.useState(false)

  /* ── Derived: filter legs by market category client-side ── */
  const displayedLegs = React.useMemo(() => {
    if (!ticket) return []
    const filtered = filterLegsByCategory(ticket.legs, config.marketCategory)
    return filtered.slice(0, config.selectionCount)
  }, [ticket, config.marketCategory, config.selectionCount])

  const combinedOddsDisplay = React.useMemo(
    () => displayedLegs.reduce((acc, l) => acc * l.odds, 1),
    [displayedLegs],
  )

  const combinedOddsInRange =
    combinedOddsDisplay >= config.oddsMin && combinedOddsDisplay <= config.oddsMax

  /* ── Generate ticket when risk profile or key changes ── */
  React.useEffect(() => {
    let cancelled = false

    async function generate() {
      setLoading(true)
      setError(false)

      try {
        const mode = RISK_MODE_MAP[config.riskProfile]
        const result = await fetchTickets([mode])

        if (cancelled) return

        if (!result.ok) throw new Error(result.error.message)
        const candidate =
          result.data.tickets.find((t) => t.mode === mode) ?? result.data.tickets[0] ?? null
        setTicket(candidate)
      } catch {
        if (!cancelled) setError(true)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    generate()
    return () => {
      cancelled = true
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.riskProfile, generationKey])

  /* ── Helpers ── */
  function updateCount(delta: number) {
    setConfig((prev) => ({
      ...prev,
      selectionCount: Math.min(7, Math.max(2, prev.selectionCount + delta)),
    }))
  }

  function handleCopy() {
    if (!displayedLegs.length) return
    const riskMeta = RISK_PROFILES.find((r) => r.key === config.riskProfile)!
    const lines = [
      `🎯 BetMind AI — Boleto ${riskMeta.label}`,
      `📊 Cuota Combinada: ${combinedOddsDisplay.toFixed(2)}`,
      ticket ? `💡 +EV Promedio: ${(ticket.evAverage * 100).toFixed(1)}%` : '',
      ticket ? `✅ Confianza IA: ${ticket.confidence}%` : '',
      '',
      ...displayedLegs.map(
        (l, i) =>
          `${i + 1}. ${l.match}\n   ${formatMarketName(l.market)} @ ${l.odds.toFixed(2)}`,
      ),
      '',
      `⚡ Generado por BetMind AI`,
    ].filter(Boolean)
    navigator.clipboard.writeText(lines.join('\n')).then(() => {
      setCopied(true)
      toast('Boleto copiado al portapapeles', {
        description: `${displayedLegs.length} selecciones listas.`,
      })
      setTimeout(() => setCopied(false), 2200)
    })
  }

  async function handleSave() {
    if (!ticket) return
    await addToTracking(ticket)
    onTrack?.()
    toast('Añadido a seguimiento', {
      description: `${displayedLegs.length} selecciones en seguimiento.`,
    })
  }

  const activeProfile = RISK_PROFILES.find((r) => r.key === config.riskProfile)!
  const modeMeta = MODE_META[activeProfile.mode]

  /* ── empty-state reason ── */
  const emptyReason = React.useMemo(() => {
    if (!ticket) return null
    if (config.marketCategory !== 'all' && filterLegsByCategory(ticket.legs, config.marketCategory).length === 0) {
      const catLabel = MARKET_CATEGORIES.find((c) => c.key === config.marketCategory)?.label ?? 'este filtro'
      return `No hay selecciones de ${catLabel} disponibles hoy. El modelo no detectó oportunidades +EV en este mercado para los partidos activos. Prueba con "Todos" o cambia el perfil de riesgo.`
    }
    return null
  }, [ticket, config.marketCategory])

  /* ------------------------------------------------------------------ */
  /* Render                                                               */
  /* ------------------------------------------------------------------ */
  return (
    <div className="flex flex-col gap-4">
      {/* ── TOP: Market Category Pills ── */}
      <div
        role="group"
        aria-label="Filtro de mercado"
        className="flex flex-wrap gap-1.5"
      >
        {MARKET_CATEGORIES.map((cat) => {
          const Icon = cat.icon
          const active = config.marketCategory === cat.key
          return (
            <button
              key={cat.key}
              type="button"
              id={`market-cat-${cat.key}`}
              aria-pressed={active}
              onClick={() => setConfig((prev) => ({ ...prev, marketCategory: cat.key }))}
              className={cn(
                'flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold transition-all duration-200',
                active
                  ? 'border-primary/50 bg-primary/15 text-primary shadow-sm shadow-primary/10'
                  : 'border-border bg-surface/40 text-muted-foreground hover:border-border hover:bg-surface hover:text-foreground',
              )}
            >
              <Icon size={11} aria-hidden />
              {cat.label}
            </button>
          )
        })}
      </div>

      {/* ── MAIN: 2-col layout ── */}
      <div className="grid gap-4 lg:grid-cols-[360px_1fr]">
        {/* ── LEFT: Controls ── */}
        <aside className="flex flex-col gap-4 rounded-xl border border-border bg-card p-5">
          <div className="flex items-center gap-2">
            <div className="flex size-7 items-center justify-center rounded-lg bg-primary/12 text-primary">
              <Zap size={13} aria-hidden />
            </div>
            <h2 className="text-sm font-bold text-foreground tracking-tight">Configurar Boleto</h2>
          </div>

          {/* 1. Selection Count */}
          <fieldset className="flex flex-col gap-2.5">
            <legend className="text-[10px] font-bold uppercase tracking-widest text-subtle">
              Selecciones
            </legend>
            <div className="flex w-fit items-center gap-3 rounded-lg border border-border/60 p-1">
              <button
                type="button"
                aria-label="Reducir"
                onClick={() => updateCount(-1)}
                disabled={config.selectionCount <= 2}
                className="flex size-8 items-center justify-center rounded-md text-foreground transition-colors hover:bg-surface-raised disabled:pointer-events-none disabled:opacity-25"
              >
                <Minus size={15} aria-hidden />
              </button>
              <div className="flex min-w-[5rem] items-baseline justify-center gap-0.5 px-2">
                <span className="font-mono text-xl font-bold tabular-nums text-foreground">
                  {config.selectionCount}
                </span>
                <span className="ml-0.5 text-[10px] font-semibold text-muted-foreground">sel.</span>
              </div>
              <button
                type="button"
                aria-label="Aumentar"
                onClick={() => updateCount(1)}
                disabled={config.selectionCount >= 7}
                className="flex size-8 items-center justify-center rounded-md text-foreground transition-colors hover:bg-surface-raised disabled:pointer-events-none disabled:opacity-25"
              >
                <Plus size={15} aria-hidden />
              </button>
            </div>
          </fieldset>

          <div className="h-px bg-border-subtle" />

          {/* 2. Risk Profile */}
          <fieldset className="flex flex-col gap-2.5">
            <legend className="text-[10px] font-bold uppercase tracking-widest text-subtle">
              Perfil de Riesgo
            </legend>
            <div className="grid grid-cols-3 gap-2">
              {RISK_PROFILES.map((profile) => {
                const active = config.riskProfile === profile.key
                return (
                  <button
                    key={profile.key}
                    type="button"
                    id={`risk-${profile.key}`}
                    aria-pressed={active}
                    onClick={() =>
                      setConfig((prev) => ({ ...prev, riskProfile: profile.key }))
                    }
                    className={cn(
                      'flex flex-col items-center gap-1 rounded-lg border px-2 py-2.5 text-center transition-colors',
                      active
                        ? 'border-primary/60 bg-primary/10 text-primary'
                        : 'border-border bg-surface/40 text-muted-foreground hover:bg-surface hover:text-foreground',
                    )}
                  >
                    <span className="text-[11px] font-bold leading-none">
                      {profile.label}
                    </span>
                    <span className="text-[9px] font-medium leading-none opacity-70">
                      {profile.sublabel}
                    </span>
                  </button>
                )
              })}
            </div>
          </fieldset>

          <div className="h-px bg-border-subtle" />

          {/* 3. Odds Range */}
          <fieldset className="flex flex-col gap-2.5">
            <legend className="text-[10px] font-bold uppercase tracking-widest text-subtle">
              Rango de Cuota Combinada
            </legend>

            <div className="grid grid-cols-2 gap-2">
              {/* Min */}
              <div className="flex flex-col gap-1.5">
                <span className="text-[9px] font-bold uppercase tracking-wider text-subtle">Mínimo</span>
                <div className="flex items-center overflow-hidden rounded-md border border-border bg-surface-inset focus-within:border-primary/50 focus-within:ring-1 focus-within:ring-primary/25">
                  <input
                    type="number"
                    value={config.oddsMin}
                    min={1.01}
                    max={config.oddsMax - 0.5}
                    step={0.10}
                    onChange={(e) => {
                      const v = parseFloat(parseFloat(e.target.value).toFixed(2))
                      if (!isNaN(v)) setConfig((prev) => ({ ...prev, oddsMin: v }))
                    }}
                    className="w-full bg-transparent px-2.5 py-2 text-sm font-mono text-foreground outline-none tabular-nums"
                  />
                </div>
              </div>
              {/* Max */}
              <div className="flex flex-col gap-1.5">
                <span className="text-[9px] font-bold uppercase tracking-wider text-subtle">Máximo</span>
                <div className="flex items-center overflow-hidden rounded-md border border-border bg-surface-inset focus-within:border-primary/50 focus-within:ring-1 focus-within:ring-primary/25">
                  <input
                    type="number"
                    value={config.oddsMax}
                    min={config.oddsMin + 0.5}
                    max={100}
                    step={0.50}
                    onChange={(e) => {
                      const v = parseFloat(parseFloat(e.target.value).toFixed(2))
                      if (!isNaN(v)) setConfig((prev) => ({ ...prev, oddsMax: v }))
                    }}
                    className="w-full bg-transparent px-2.5 py-2 text-sm font-mono text-foreground outline-none tabular-nums"
                  />
                </div>
              </div>
            </div>

            {/* Presets */}
            <div className="flex gap-1.5">
              {ODDS_PRESETS.map((preset) => {
                const active = config.oddsMin === preset.min && config.oddsMax === preset.max
                return (
                  <button
                    key={preset.label}
                    type="button"
                    onClick={() =>
                      setConfig((prev) => ({
                        ...prev,
                        oddsMin: preset.min,
                        oddsMax: preset.max,
                      }))
                    }
                    className={cn(
                      'flex-1 rounded-md border py-1.5 text-[10px] font-bold transition-colors',
                      active
                        ? 'border-primary/40 bg-primary/12 text-primary'
                        : 'border-border bg-transparent text-subtle hover:text-foreground',
                    )}
                  >
                    {preset.label}
                  </button>
                )
              })}
            </div>
          </fieldset>

          {/* Regenerate */}
          <button
            type="button"
            id="generator-regenerate"
            onClick={() => setGenerationKey((k) => k + 1)}
            disabled={loading}
            className="mt-auto flex items-center justify-center gap-2 rounded-lg border border-border bg-surface px-4 py-2.5 text-xs font-semibold text-foreground transition-colors hover:bg-surface-raised disabled:opacity-40"
          >
            <RefreshCw size={13} className={loading ? 'animate-spin' : ''} aria-hidden />
            {loading ? 'Generando…' : 'Regenerar Boleto'}
          </button>
        </aside>

        {/* ── RIGHT: Preview ── */}
        <section
          className="flex flex-col rounded-xl border border-border bg-card overflow-hidden"
          aria-label="Vista previa del boleto generado"
        >
          {/* Mode accent top bar */}
          <div className={cn('h-[3px] w-full shrink-0', modeMeta.accent)} aria-hidden />

          {/* Header */}
          <div className="flex flex-col gap-3 p-5 pb-3">
            <div className="flex items-start justify-between gap-3">
              {/* Left: Mode badge + count */}
              <div className="flex flex-col gap-1.5">
                <span
                  className={cn(
                    'inline-flex w-fit items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-bold tracking-wide uppercase',
                    modeMeta.border,
                    modeMeta.bg,
                    modeMeta.text,
                  )}
                >
                  <span aria-hidden>{modeMeta.glyph}</span>
                  {modeMeta.label}
                </span>
                <span className="text-xs text-muted-foreground">
                  {config.selectionCount} selecciones ·{' '}
                  {MARKET_CATEGORIES.find((c) => c.key === config.marketCategory)?.label}
                </span>
              </div>

              {/* Right: Combined odds HERO */}
              {ticket && !loading ? (
                <div className="flex flex-col items-end">
                  <span
                    className={cn(
                      'font-mono text-4xl font-bold tabular-nums tracking-tight leading-none',
                      combinedOddsInRange ? 'text-positive' : 'text-warning',
                    )}
                  >
                    {combinedOddsDisplay.toFixed(2)}
                  </span>
                  <span className="mt-0.5 text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
                    Cuota Combinada
                  </span>
                </div>
              ) : (
                <div className="flex flex-col items-end gap-1">
                  <div className="h-10 w-20 skeleton rounded-md" />
                  <div className="h-2.5 w-16 skeleton rounded" />
                </div>
              )}
            </div>

            {/* Stats row */}
            {ticket && !loading ? (
              <div className="my-2 flex items-center justify-between divide-x divide-border/50 rounded-lg border border-border/60 bg-surface/30 px-4 py-2 text-xs">
                <div className="flex flex-col gap-0.5 pr-3">
                  <span className="text-[9px] font-bold uppercase tracking-widest text-subtle">
                    Confianza IA
                  </span>
                  {/* confidence is 0-95 integer from backend */}
                  <span className="font-mono font-bold tabular-nums text-foreground">
                    {ticket.confidence}%
                  </span>
                </div>
                <div className="flex flex-col gap-0.5 px-3">
                  <span className="text-[9px] font-bold uppercase tracking-widest text-subtle">
                    +EV Promedio
                  </span>
                  <span className="font-mono font-bold tabular-nums text-positive">
                    +{(ticket.evAverage * 100).toFixed(1)}%
                  </span>
                </div>
                <div className="flex flex-col gap-0.5 pl-3">
                  <span className="text-[9px] font-bold uppercase tracking-widest text-subtle">
                    Rango
                  </span>
                  <div className="flex items-center gap-1">
                    <span className={cn('size-1.5 rounded-full', combinedOddsInRange ? 'bg-positive' : 'bg-warning')} aria-hidden />
                    <span
                      className={cn(
                        'text-xs font-bold',
                        combinedOddsInRange ? 'text-positive' : 'text-warning',
                      )}
                    >
                      {combinedOddsInRange ? 'En rango' : 'Fuera de rango'}
                    </span>
                  </div>
                </div>
              </div>
            ) : (
              <div className="h-[58px] w-full skeleton rounded-xl" />
            )}
          </div>

          {/* Legs list */}
          <div className="flex flex-1 flex-col px-5 pb-3 gap-2.5">
            {loading ? (
              <ul className="flex flex-col gap-2.5">
                {Array.from({ length: config.selectionCount }).map((_, i) => (
                  <li key={i}>
                    <LegSkeleton />
                  </li>
                ))}
              </ul>
            ) : error ? (
              <div className="flex flex-col items-center justify-center py-10 text-center gap-2">
                <AlertCircle size={20} className="text-negative" aria-hidden />
                <p className="text-sm font-semibold text-foreground">Error al consultar el modelo</p>
                <p className="text-xs text-muted-foreground max-w-xs">
                  No se pudo conectar con el API. Verifica que el servidor esté activo y vuelve a intentarlo.
                </p>
              </div>
            ) : emptyReason ? (
              <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border/60 py-10 px-6 text-center gap-2">
                <div className="flex size-10 items-center justify-center rounded-xl bg-muted/30 text-muted-foreground">
                  <AlertCircle size={18} aria-hidden />
                </div>
                <p className="text-sm font-semibold text-foreground">Sin selecciones para este filtro</p>
                <p className="text-xs leading-relaxed text-muted-foreground max-w-xs">
                  {emptyReason}
                </p>
              </div>
            ) : displayedLegs.length > 0 ? (
              <ul className="flex flex-col gap-2.5" key={`${generationKey}-${config.marketCategory}-${config.selectionCount}`}>
                {displayedLegs.map((leg, i) => (
                  <GeneratorLeg
                    key={`${leg.match}-${leg.market}-${i}`}
                    leg={leg}
                    index={i}
                  />
                ))}
              </ul>
            ) : (
              <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border/60 py-10 px-6 text-center gap-2">
                <div className="flex size-10 items-center justify-center rounded-xl bg-muted/30 text-muted-foreground">
                  <RefreshCw size={18} aria-hidden />
                </div>
                <p className="text-sm font-semibold text-foreground">No hay oportunidades disponibles</p>
                <p className="text-xs leading-relaxed text-muted-foreground max-w-xs">
                  El modelo no encontró selecciones con +EV para los filtros actuales. Cambia el perfil de riesgo o amplía el rango de cuotas.
                </p>
              </div>
            )}
          </div>

          {/* Analysis snippet — only when data available */}
          {ticket?.analysis && !loading && displayedLegs.length > 0 && (
            <div className="border-t border-border/40 bg-surface/20 px-5 py-3">
              <p className="text-xs leading-relaxed text-muted-foreground line-clamp-2">
                <span className="font-semibold text-foreground/80">Análisis IA · </span>
                {ticket.analysis}
              </p>
            </div>
          )}

          {ticket && !loading && displayedLegs.length > 0 && (
            <div className="border-t border-primary/15 bg-primary/[0.04] px-5 py-3">
              <p className="text-[10px] font-bold uppercase tracking-widest text-primary">Razonamiento de la IA</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {ticket.rationale.map((item) => (
                  <span key={item} className="rounded-md border border-border/60 bg-surface/60 px-2 py-1 text-[10px] font-medium text-muted-foreground">
                    {item}
                  </span>
                ))}
              </div>
              <p className="mt-2 text-[10px] leading-relaxed text-subtle" title={ticket.correlation}>
                Filtros y seguridad: {ticket.correlation}
              </p>
            </div>
          )}

          {/* Footer actions */}
          <div className="border-t border-border/40 bg-surface-raised/40 p-4">
            <div className="flex flex-col">
              <button
                type="button"
                id="generator-copy-ticket"
                onClick={handleCopy}
                disabled={!displayedLegs.length || loading}
                className={cn(
                  'flex w-full items-center justify-center gap-2 rounded-lg py-2.5 text-xs font-semibold transition-opacity hover:opacity-90 disabled:opacity-35',
                  copied
                    ? 'bg-positive text-white'
                    : 'bg-primary text-primary-foreground',
                )}
              >
                {copied ? (
                  <Check size={13} aria-hidden />
                ) : (
                  <Copy size={13} aria-hidden />
                )}
                {copied ? '¡Boleto Copiado!' : 'Copiar Boleto'}
              </button>

              <button
                type="button"
                id="generator-save-ticket"
                onClick={handleSave}
                disabled={!ticket || loading}
                className="mt-2 flex w-full items-center justify-center gap-2 rounded-lg border border-border bg-transparent py-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-surface hover:text-foreground disabled:opacity-35"
              >
                <Star size={13} aria-hidden />
                Guardar en Seguimiento
              </button>
            </div>
            <p className="mt-2.5 text-center text-[9px] font-medium text-subtle tracking-wide">
              Probabilidades estimadas por modelo Poisson + IA. No constituye asesoría financiera.
            </p>
          </div>
        </section>
      </div>
    </div>
  )
}
