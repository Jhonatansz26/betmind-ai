'use client'

import * as React from 'react'
import {
  Copy,
  Star,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  Zap,
  Shield,
  TrendingUp,
  CheckCircle2,
  AlertCircle,
} from 'lucide-react'
import { toast } from 'sonner'

import { type Match, type Ticket, MODE_META } from '@/lib/betmind'
import { fetchTickets } from '@/lib/api'
import { formatMarketName } from '@/lib/formatMarketName'
import { resolveLeague } from '@/lib/league-metadata'
import { cn } from '@/lib/utils'
import { addToTracking } from './tracking-panel'
import { LeagueLogo } from './league-logo'

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

type RiskProfile = 'conservative' | 'balanced' | 'aggressive'

interface GeneratorConfig {
  selectionCount: number
  riskProfile: RiskProfile
  oddsMin: number
  oddsMax: number
  selectedLeagues: string[] // leagueExternalId strings
}

interface LeaguePill {
  id: string
  name: string
  logoUrl: string | null
}

/* ------------------------------------------------------------------ */
/* Constants                                                           */
/* ------------------------------------------------------------------ */

const RISK_PROFILES: Array<{
  key: RiskProfile
  label: string
  sublabel: string
  mode: 'EDGE' | 'VALUE' | 'BOLD'
  icon: React.ElementType
  color: string
  border: string
  bg: string
  glowColor: string
}> = [
  {
    key: 'conservative',
    label: 'Conservador',
    sublabel: 'Bajo Riesgo',
    mode: 'EDGE',
    icon: Shield,
    color: 'text-primary',
    border: 'border-primary/40',
    bg: 'bg-primary/10',
    glowColor: 'shadow-primary/20',
  },
  {
    key: 'balanced',
    label: 'Equilibrado',
    sublabel: 'Value',
    mode: 'VALUE',
    icon: TrendingUp,
    color: 'text-warning',
    border: 'border-warning/40',
    bg: 'bg-warning/10',
    glowColor: 'shadow-warning/20',
  },
  {
    key: 'aggressive',
    label: 'Agresivo',
    sublabel: 'Bold / +EV Máx',
    mode: 'BOLD',
    icon: Zap,
    color: 'text-negative',
    border: 'border-negative/40',
    bg: 'bg-negative/10',
    glowColor: 'shadow-negative/20',
  },
]

const RISK_MODE_MAP: Record<RiskProfile, 'EDGE' | 'VALUE' | 'BOLD'> = {
  conservative: 'EDGE',
  balanced: 'VALUE',
  aggressive: 'BOLD',
}

const ODDS_PRESETS = [
  { label: '1.5–3.0', min: 1.5, max: 3.0 },
  { label: '3.0–6.0', min: 3.0, max: 6.0 },
  { label: '6.0+', min: 6.0, max: 50 },
]

/* ------------------------------------------------------------------ */
/* Sub-components                                                      */
/* ------------------------------------------------------------------ */

function LegSkeleton() {
  return (
    <div className="flex items-center justify-between rounded-lg border border-border/40 bg-surface/40 px-3.5 py-3">
      <div className="flex flex-col gap-1.5 flex-1 pr-3">
        <div className="h-3.5 w-36 skeleton rounded" />
        <div className="h-2.5 w-28 skeleton rounded" />
        <div className="h-2 w-16 skeleton rounded" />
      </div>
      <div className="h-8 w-12 skeleton rounded-md shrink-0" />
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
      className="stagger-item flex items-center justify-between rounded-lg border border-border/60 bg-surface/60 px-3.5 py-3 transition-colors hover:border-border"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <div className="flex flex-col gap-0.5 min-w-0 pr-3">
        <span className="truncate text-sm font-semibold text-foreground">
          {humanMarket}
        </span>
        <span className="block text-xs text-muted-foreground leading-tight truncate" title={leg.match}>
          {leg.match}
        </span>
        <span
          className={cn(
            'text-[10px] font-semibold',
            evPositive ? 'text-positive' : 'text-negative',
          )}
        >
          {evPositive ? '+' : ''}{(leg.ev * 100).toFixed(1)}% EV
        </span>
      </div>
      <span className="num ml-2 shrink-0 rounded-md bg-surface-raised/80 px-2.5 py-1 text-base font-bold text-foreground">
        {leg.odds.toFixed(2)}
      </span>
    </li>
  )
}

function OddsRangeInput({
  label,
  value,
  onChange,
  min,
  max,
  step,
}: {
  label: string
  value: number
  onChange: (v: number) => void
  min: number
  max: number
  step: number
}) {
  return (
    <div className="flex flex-col gap-1">
      <label className="text-[10px] font-semibold uppercase tracking-wider text-subtle">
        {label}
      </label>
      <div className="flex items-center gap-2">
        <input
          type="number"
          value={value}
          min={min}
          max={max}
          step={step}
          onChange={(e) => {
            const parsed = parseFloat(e.target.value)
            if (!isNaN(parsed)) onChange(parsed)
          }}
          className="w-20 rounded-md border border-border bg-surface-inset px-2.5 py-1.5 text-sm font-mono text-foreground outline-none transition-colors focus:border-primary/60 focus:ring-1 focus:ring-primary/30"
        />
        <div
          className="h-1 flex-1 rounded-full bg-border-subtle overflow-hidden"
          aria-hidden
        >
          <div
            className="h-full rounded-full bg-primary/50 transition-all duration-300"
            style={{ width: `${Math.min(100, ((value - min) / (max - min)) * 100)}%` }}
          />
        </div>
      </div>
    </div>
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
    oddsMin: 1.8,
    oddsMax: 10.0,
    selectedLeagues: [],
  })

  /* ── Result state ── */
  const [ticket, setTicket] = React.useState<Ticket | null>(null)
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState(false)
  const [generationKey, setGenerationKey] = React.useState(0)
  const [copied, setCopied] = React.useState(false)

  /* ── Debounce timer for odds range ── */
  const oddsDebounceRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)

  /* ── League pills derived from matches ── */
  const leaguePills = React.useMemo<LeaguePill[]>(() => {
    const map = new Map<string, LeaguePill>()
    for (const m of matches) {
      const lid = String(m.leagueExternalId ?? 'other')
      if (!map.has(lid)) {
        const meta = resolveLeague(m.leagueExternalId, m.league)
        map.set(lid, {
          id: lid,
          name: meta.shortName,
          logoUrl: m.leagueLogoUrl || meta.logoUrl,
        })
      }
    }
    return Array.from(map.values()).slice(0, 12)
  }, [matches])

  /* ── Generate ticket when config or key changes ── */
  React.useEffect(() => {
    let cancelled = false

    async function generate() {
      setLoading(true)
      setError(false)

      try {
        const mode = RISK_MODE_MAP[config.riskProfile]
        const leagueFilter =
          config.selectedLeagues.length > 0 ? config.selectedLeagues : undefined

        const result = await fetchTickets([mode], leagueFilter)

        if (cancelled) return

        // Find the ticket matching the mode, filter by odds range
        const candidate = result.tickets.find((t) => t.mode === mode) ?? result.tickets[0] ?? null

        if (candidate) {
          // Filter legs that fall within the desired combined odds range
          const legs = candidate.legs.slice(0, config.selectionCount)
          const combinedOdds = legs.reduce((acc, l) => acc * l.odds, 1)

          if (combinedOdds >= config.oddsMin && combinedOdds <= config.oddsMax) {
            setTicket({ ...candidate, legs, combinedOdds })
          } else {
            // Still show it but highlight it's outside the range
            setTicket({ ...candidate, legs, combinedOdds })
          }
        } else {
          setTicket(null)
        }
      } catch {
        if (!cancelled) setError(true)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    generate()
    return () => { cancelled = true }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [config.riskProfile, config.selectedLeagues, generationKey])

  /* ── Helpers ── */
  function updateCount(delta: number) {
    setConfig((prev) => ({
      ...prev,
      selectionCount: Math.min(7, Math.max(2, prev.selectionCount + delta)),
    }))
  }

  function updateOddsWithDebounce(field: 'oddsMin' | 'oddsMax', value: number) {
    setConfig((prev) => ({ ...prev, [field]: value }))
    if (oddsDebounceRef.current) clearTimeout(oddsDebounceRef.current)
    oddsDebounceRef.current = setTimeout(() => {
      setGenerationKey((k) => k + 1)
    }, 500)
  }

  function toggleLeague(id: string) {
    setConfig((prev) => {
      const current = prev.selectedLeagues
      const updated = current.includes(id)
        ? current.filter((l) => l !== id)
        : [...current, id]
      return { ...prev, selectedLeagues: updated }
    })
  }

  function handleCopy() {
    if (!ticket) return
    const riskMeta = RISK_PROFILES.find((r) => r.key === config.riskProfile)!
    const lines = [
      `🎯 BetMind AI — Boleto ${riskMeta.label}`,
      `📊 Cuota Combinada: ${ticket.combinedOdds.toFixed(2)}`,
      `💡 +EV Promedio: ${(ticket.evAverage * 100).toFixed(1)}%`,
      `✅ Confianza: ${Math.round(ticket.confidence * 100)}%`,
      '',
      ...ticket.legs.map(
        (l, i) =>
          `${i + 1}. ${l.match}\n   ${formatMarketName(l.market)} @ ${l.odds.toFixed(2)}`,
      ),
      '',
      `⚡ Generado por BetMind AI`,
    ]
    navigator.clipboard.writeText(lines.join('\n')).then(() => {
      setCopied(true)
      toast('Boleto copiado al portapapeles', {
        description: `${ticket.legs.length} selecciones listas para usar.`,
      })
      setTimeout(() => setCopied(false), 2000)
    })
  }

  function handleSave() {
    if (!ticket) return
    addToTracking(ticket)
    onTrack?.()
    toast('Añadido a seguimiento', {
      description: `${ticket.legs.length} selecciones en seguimiento.`,
    })
  }

  const activeProfile = RISK_PROFILES.find((r) => r.key === config.riskProfile)!
  const modeMeta = MODE_META[activeProfile.mode]

  const combinedOddsInRange =
    ticket && ticket.combinedOdds >= config.oddsMin && ticket.combinedOdds <= config.oddsMax

  /* ------------------------------------------------------------------ */
  /* Render                                                               */
  /* ------------------------------------------------------------------ */

  return (
    <div className="grid gap-4 lg:grid-cols-[380px_1fr]">
      {/* ── LEFT: Controls Panel ── */}
      <aside className="flex flex-col gap-4 rounded-xl border border-border bg-card p-5">
        <div className="flex items-center gap-2">
          <div className="flex size-7 items-center justify-center rounded-lg bg-primary/15 text-primary">
            <Zap size={14} aria-hidden />
          </div>
          <h2 className="text-sm font-bold text-foreground">Configurar Boleto</h2>
        </div>

        {/* ── 1. Selection Count ── */}
        <fieldset className="flex flex-col gap-2.5">
          <legend className="text-[11px] font-semibold uppercase tracking-wider text-subtle">
            Cantidad de Selecciones
          </legend>
          <div className="flex items-center gap-3">
            <button
              type="button"
              aria-label="Reducir selecciones"
              onClick={() => updateCount(-1)}
              disabled={config.selectionCount <= 2}
              className="flex size-9 items-center justify-center rounded-lg border border-border bg-surface text-foreground transition-colors hover:border-primary/40 hover:bg-primary/10 disabled:pointer-events-none disabled:opacity-30"
            >
              <ChevronDown size={16} aria-hidden />
            </button>
            <span className="num flex min-w-[3.5rem] items-center justify-center gap-1 rounded-lg border border-primary/30 bg-primary/10 px-3 py-1.5 text-xl font-bold text-primary">
              {config.selectionCount}
              <span className="text-xs font-medium text-primary/60">sel.</span>
            </span>
            <button
              type="button"
              aria-label="Aumentar selecciones"
              onClick={() => updateCount(1)}
              disabled={config.selectionCount >= 7}
              className="flex size-9 items-center justify-center rounded-lg border border-border bg-surface text-foreground transition-colors hover:border-primary/40 hover:bg-primary/10 disabled:pointer-events-none disabled:opacity-30"
            >
              <ChevronUp size={16} aria-hidden />
            </button>
            <div className="flex flex-1 gap-1">
              {[2, 3, 4, 5, 6, 7].map((n) => (
                <button
                  key={n}
                  type="button"
                  aria-label={`${n} selecciones`}
                  aria-pressed={config.selectionCount === n}
                  onClick={() => setConfig((prev) => ({ ...prev, selectionCount: n }))}
                  className={cn(
                    'flex h-1.5 flex-1 rounded-full transition-all duration-200',
                    config.selectionCount >= n
                      ? 'bg-primary'
                      : 'bg-border',
                  )}
                />
              ))}
            </div>
          </div>
        </fieldset>

        <div className="h-px bg-border-subtle" />

        {/* ── 2. Risk Profile ── */}
        <fieldset className="flex flex-col gap-2.5">
          <legend className="text-[11px] font-semibold uppercase tracking-wider text-subtle">
            Perfil de Riesgo
          </legend>
          <div className="grid grid-cols-3 gap-2">
            {RISK_PROFILES.map((profile) => {
              const Icon = profile.icon
              const active = config.riskProfile === profile.key
              return (
                <button
                  key={profile.key}
                  type="button"
                  aria-pressed={active}
                  onClick={() =>
                    setConfig((prev) => ({ ...prev, riskProfile: profile.key }))
                  }
                  className={cn(
                    'flex flex-col items-center gap-1.5 rounded-xl border px-2 py-3 text-center transition-all duration-200',
                    active
                      ? cn(
                          'shadow-lg',
                          profile.border,
                          profile.bg,
                          profile.color,
                          profile.glowColor,
                        )
                      : 'border-border bg-surface/40 text-muted-foreground hover:border-border hover:bg-surface',
                  )}
                >
                  <Icon size={16} aria-hidden />
                  <span className="text-[11px] font-bold leading-none">
                    {profile.label}
                  </span>
                  <span className="text-[9px] font-medium opacity-70 leading-none">
                    {profile.sublabel}
                  </span>
                </button>
              )
            })}
          </div>
        </fieldset>

        <div className="h-px bg-border-subtle" />

        {/* ── 3. Odds Range ── */}
        <fieldset className="flex flex-col gap-2.5">
          <legend className="text-[11px] font-semibold uppercase tracking-wider text-subtle">
            Rango de Cuota Combinada
          </legend>
          <div className="flex gap-3">
            <OddsRangeInput
              label="Mínimo"
              value={config.oddsMin}
              onChange={(v) => updateOddsWithDebounce('oddsMin', v)}
              min={1.01}
              max={config.oddsMax - 0.5}
              step={0.1}
            />
            <OddsRangeInput
              label="Máximo"
              value={config.oddsMax}
              onChange={(v) => updateOddsWithDebounce('oddsMax', v)}
              min={config.oddsMin + 0.5}
              max={50}
              step={0.5}
            />
          </div>
          {/* Presets */}
          <div className="flex gap-1.5">
            {ODDS_PRESETS.map((preset) => (
              <button
                key={preset.label}
                type="button"
                onClick={() => {
                  setConfig((prev) => ({
                    ...prev,
                    oddsMin: preset.min,
                    oddsMax: preset.max,
                  }))
                  setGenerationKey((k) => k + 1)
                }}
                className={cn(
                  'rounded-md border px-2.5 py-1 text-[10px] font-semibold transition-colors',
                  config.oddsMin === preset.min && config.oddsMax === preset.max
                    ? 'border-primary/40 bg-primary/10 text-primary'
                    : 'border-border bg-transparent text-muted-foreground hover:text-foreground',
                )}
              >
                {preset.label}
              </button>
            ))}
          </div>
        </fieldset>

        {/* ── 4. League Filter ── */}
        {leaguePills.length > 0 && (
          <>
            <div className="h-px bg-border-subtle" />
            <fieldset className="flex flex-col gap-2.5">
              <div className="flex items-center justify-between">
                <legend className="text-[11px] font-semibold uppercase tracking-wider text-subtle">
                  Filtrar por Liga
                </legend>
                {config.selectedLeagues.length > 0 && (
                  <button
                    type="button"
                    onClick={() =>
                      setConfig((prev) => ({ ...prev, selectedLeagues: [] }))
                    }
                    className="text-[10px] text-muted-foreground underline hover:text-foreground"
                  >
                    Limpiar
                  </button>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {leaguePills.map((pill) => {
                  const active = config.selectedLeagues.includes(pill.id)
                  return (
                    <button
                      key={pill.id}
                      type="button"
                      aria-pressed={active}
                      onClick={() => toggleLeague(pill.id)}
                      className={cn(
                        'flex items-center gap-1 rounded-md border px-2 py-1 text-[10px] font-medium transition-colors',
                        active
                          ? 'border-primary/50 bg-primary/15 text-primary'
                          : 'border-border bg-transparent text-muted-foreground hover:text-foreground',
                      )}
                    >
                      {pill.logoUrl && (
                        <LeagueLogo
                          logoUrl={pill.logoUrl}
                          flag=""
                          size="sm"
                          className={active ? '' : 'brightness-0 invert opacity-50'}
                        />
                      )}
                      {pill.name}
                    </button>
                  )
                })}
              </div>
            </fieldset>
          </>
        )}

        {/* ── Generate button ── */}
        <button
          type="button"
          onClick={() => setGenerationKey((k) => k + 1)}
          disabled={loading}
          className="mt-auto flex items-center justify-center gap-2 rounded-xl border border-primary/30 bg-primary/10 px-4 py-3 text-sm font-semibold text-primary transition-all hover:border-primary/60 hover:bg-primary/20 disabled:opacity-50"
        >
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} aria-hidden />
          {loading ? 'Generando…' : 'Regenerar Boleto'}
        </button>
      </aside>

      {/* ── RIGHT: Ticket Preview ── */}
      <section
        className="flex flex-col rounded-xl border border-border bg-card overflow-hidden"
        aria-label="Vista previa del boleto generado"
      >
        {/* Mode accent strip */}
        <div
          className={cn('h-[3px] w-full shrink-0', modeMeta.accent)}
          aria-hidden
        />

        {/* Header */}
        <div className="flex flex-col gap-3 p-5 pb-3">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span
                className={cn(
                  'inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-semibold tracking-wide',
                  modeMeta.border,
                  modeMeta.bg,
                  modeMeta.text,
                )}
              >
                <span aria-hidden>{modeMeta.glyph}</span>
                {modeMeta.label}
              </span>
              <span className="text-xs text-muted-foreground">
                · {config.selectionCount} selecciones
              </span>
            </div>

            {/* Combined odds — the hero number */}
            {ticket && !loading ? (
              <div className="flex flex-col items-end">
                <span
                  className={cn(
                    'num font-mono text-3xl font-bold tracking-tight',
                    combinedOddsInRange ? 'text-positive' : 'text-warning',
                  )}
                >
                  {ticket.combinedOdds.toFixed(2)}
                </span>
                <span className="text-[9px] font-semibold uppercase tracking-wider text-subtle">
                  Cuota combinada
                </span>
              </div>
            ) : (
              <div className="h-9 w-20 skeleton rounded" />
            )}
          </div>

          {/* Stats row */}
          {ticket && !loading ? (
            <div className="flex items-center gap-4 rounded-lg border border-border/60 bg-surface/50 px-3.5 py-2.5">
              {/* Probability */}
              <div className="flex flex-col gap-0.5">
                <span className="text-[9px] font-semibold uppercase tracking-wider text-subtle">
                  Probabilidad IA
                </span>
                <span className="num text-base font-bold text-foreground">
                  {Math.round(ticket.confidence * 100)}%
                </span>
              </div>
              <div className="h-6 w-px bg-border-subtle" />
              {/* EV */}
              <div className="flex flex-col gap-0.5">
                <span className="text-[9px] font-semibold uppercase tracking-wider text-subtle">
                  +EV Promedio
                </span>
                <span className="num text-base font-bold text-positive">
                  +{(ticket.evAverage * 100).toFixed(1)}%
                </span>
              </div>
              <div className="h-6 w-px bg-border-subtle" />
              {/* Range indicator */}
              <div className="flex flex-col gap-0.5">
                <span className="text-[9px] font-semibold uppercase tracking-wider text-subtle">
                  Rango
                </span>
                <div className="flex items-center gap-1">
                  {combinedOddsInRange ? (
                    <CheckCircle2 size={13} className="text-positive" aria-hidden />
                  ) : (
                    <AlertCircle size={13} className="text-warning" aria-hidden />
                  )}
                  <span className={cn('text-xs font-semibold', combinedOddsInRange ? 'text-positive' : 'text-warning')}>
                    {combinedOddsInRange ? 'En rango' : 'Fuera de rango'}
                  </span>
                </div>
              </div>
            </div>
          ) : (
            <div className="h-14 w-full skeleton rounded-lg" />
          )}
        </div>

        {/* Legs list */}
        <div className="flex flex-1 flex-col px-5 pb-3">
          {loading ? (
            <ul className="flex flex-col gap-2.5">
              {Array.from({ length: config.selectionCount }).map((_, i) => (
                <li key={i}>
                  <LegSkeleton />
                </li>
              ))}
            </ul>
          ) : error ? (
            <div className="flex flex-col items-center justify-center py-10 text-center">
              <AlertCircle size={20} className="text-negative mb-2" aria-hidden />
              <p className="text-sm text-muted-foreground">
                No se pudo generar el boleto. Intenta de nuevo.
              </p>
            </div>
          ) : ticket && ticket.legs.length > 0 ? (
            <ul className="flex flex-col gap-2.5" key={generationKey}>
              {ticket.legs.map((leg, i) => (
                <GeneratorLeg key={`${leg.match}-${leg.market}-${i}`} leg={leg} index={i} />
              ))}
            </ul>
          ) : (
            <div className="flex flex-col items-center justify-center py-10 text-center">
              <RefreshCw size={20} className="text-subtle mb-2" aria-hidden />
              <p className="text-sm text-muted-foreground">
                No hay selecciones disponibles para esta configuración.
              </p>
              <p className="mt-1 text-xs text-subtle">
                Ajusta los filtros o cambia el perfil de riesgo.
              </p>
            </div>
          )}
        </div>

        {/* Analysis snippet */}
        {ticket?.analysis && !loading && (
          <div className="border-t border-border/40 bg-surface/30 px-5 py-3">
            <p className="text-xs leading-relaxed text-muted-foreground line-clamp-2">
              <span className="font-semibold text-foreground">Análisis IA: </span>
              {ticket.analysis}
            </p>
          </div>
        )}

        {/* Footer actions */}
        <div className="border-t border-border/40 bg-surface-raised/50 p-4">
          <div className="flex gap-2">
            <button
              type="button"
              id="generator-copy-ticket"
              onClick={handleCopy}
              disabled={!ticket || loading}
              className={cn(
                'flex flex-1 items-center justify-center gap-2 rounded-xl border px-4 py-2.5 text-sm font-semibold transition-all duration-200 disabled:opacity-40',
                copied
                  ? 'border-positive/40 bg-positive/15 text-positive'
                  : 'border-border bg-surface text-foreground hover:border-primary/40 hover:bg-primary/10 hover:text-primary',
              )}
            >
              {copied ? (
                <CheckCircle2 size={14} aria-hidden />
              ) : (
                <Copy size={14} aria-hidden />
              )}
              {copied ? 'Copiado' : 'Copiar Boleto'}
            </button>

            <button
              type="button"
              id="generator-save-ticket"
              onClick={handleSave}
              disabled={!ticket || loading}
              className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-primary/30 bg-primary/10 px-4 py-2.5 text-sm font-semibold text-primary transition-all hover:border-primary/60 hover:bg-primary/20 disabled:opacity-40"
            >
              <Star size={14} aria-hidden />
              Guardar en Seguimiento
            </button>
          </div>

          <p className="mt-2 text-center text-[9px] text-subtle">
            Confianza basada en datos Poisson + modelo IA. No es asesoría financiera.
          </p>
        </div>
      </section>
    </div>
  )
}
