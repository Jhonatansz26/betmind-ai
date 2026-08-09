'use client'

import * as React from 'react'
import {
  Copy,
  Star,
  RefreshCw,
  Minus,
  Plus,
  Zap,
  AlertCircle,
  Search,
  ChevronDown,
  LockKeyhole,
} from 'lucide-react'
import { toast } from 'sonner'

import { type Match, type Ticket, MODE_META } from '@/lib/betmind'
import { fetchTickets, type LeagueData } from '@/lib/api'
import { formatMarketName } from '@/lib/formatMarketName'
import { formatEV, formatOdds } from '@/lib/formatters'
import { shareOrDownloadTicket } from '@/lib/ticket-export'
import { cn } from '@/lib/utils'
import { addToTracking } from './tracking-panel'
import { TicketLeg } from './ticket-leg'
import { StakeConfirmDialog } from './stake-confirm-dialog'
import { useBankroll } from './use-bankroll'

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

type RiskProfile = 'conservative' | 'balanced' | 'aggressive'
type MarketKey = 'GOALS' | 'CORNERS' | '1X2' | 'CARDS' | 'SHOTS'

interface GeneratorConfig {
  selectionCount: number
  riskProfile: RiskProfile
  oddsMin: number
  oddsMax: number
  selectedMarkets: MarketKey[]
  selectedLeagues: string[]
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
  key: MarketKey
  label: string
  keywords: string[]
}> = [
  { key: 'GOALS', label: 'Goles', keywords: ['OVER_', 'UNDER_', 'BTTS'] },
  { key: 'CORNERS', label: 'Córneres', keywords: ['CORNERS_'] },
  { key: '1X2', label: '1X2', keywords: ['1X2'] },
  { key: 'CARDS', label: 'Tarjetas', keywords: ['CARDS_'] },
  { key: 'SHOTS', label: 'Remates', keywords: ['SHOTS_'] },
]

const DISPLAY_MARKET_KEYWORDS: Record<MarketKey, string[]> = {
  GOALS: ['OVER', 'UNDER', 'BTTS', 'GOL', 'AMBOS', 'GANA'],
  CORNERS: ['CORNER', 'CÓRNER'],
  '1X2': ['GANA', 'EMPATE', 'LOCAL', 'VISITANTE', '1X2'],
  CARDS: ['TARJETA', 'CARD'],
  SHOTS: ['REMATE', 'TIRO', 'SHOT'],
}

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
  categories: MarketKey[],
): Ticket['legs'] {
  if (!categories.length || categories.length === MARKET_CATEGORIES.length) return legs
  const keywords = categories.flatMap((category) => DISPLAY_MARKET_KEYWORDS[category] ?? [])
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
          {formatEV(leg.ev)} EV
        </span>
        <span className="font-mono text-sm font-bold tabular-nums text-foreground">@{formatOdds(leg.odds)}</span>
      </div>
    </li>
  )
}

/* ------------------------------------------------------------------ */
/* Main Component                                                      */
/* ------------------------------------------------------------------ */

export function TicketGenerator({
  matches,
  leagues = [],
  onTrack,
  isPro = true,
  onBeforeGenerate,
}: {
  matches: Match[]
  leagues?: LeagueData[]
  onTrack?: () => void
  isPro?: boolean
  onBeforeGenerate?: () => boolean
}) {
  /* ── Config state ── */
  const [config, setConfig] = React.useState<GeneratorConfig>({
    selectionCount: 3,
    riskProfile: isPro ? 'balanced' : 'conservative',
    oddsMin: 1.80,
    oddsMax: 10.00,
    selectedMarkets: MARKET_CATEGORIES.map((category) => category.key),
    selectedLeagues: [],
  })

  /* ── Result state ── */
  const [ticket, setTicket] = React.useState<Ticket | null>(null)
  const [loading, setLoading] = React.useState(false)
  const [error, setError] = React.useState(false)
  const [generationKey, setGenerationKey] = React.useState(0)
  const { bankroll, loading: bankrollLoading } = useBankroll(isPro)
  const [stakeDialogOpen, setStakeDialogOpen] = React.useState(false)

  /**
   * One-shot flag: set to `true` only when the user explicitly clicks
   * "Regenerar Boleto". The generation effect reads and immediately resets
   * this flag so that automatic re-runs (mount, config changes) never
   * invoke `onBeforeGenerate` and therefore never increment the counter.
   */
  const isExplicitGenerate = React.useRef(false)

  const activeLeagues = React.useMemo(
    () => leagues
      .filter((league) => league.active_matches > 0)
      .map((league) => ({
        ...league,
        label: league.name,
        activeMatches: league.active_matches,
        group: league.group ?? 'OTRAS LIGAS ACTIVAS',
      })),
    [leagues],
  )
  const activeLeagueKeys: string[] = activeLeagues.map((league) => league.key)
  const activeLeagueKeySet = new Set<string>(activeLeagueKeys)

  React.useEffect(() => {
    if (!leagues.length) return
    setConfig((previous) => {
      const next = previous.selectedLeagues.length === 0
        ? activeLeagueKeys
        : previous.selectedLeagues.filter((key) => activeLeagueKeySet.has(key))
      return next.length === previous.selectedLeagues.length
        ? previous
        : { ...previous, selectedLeagues: next }
    })
  }, [leagues, activeLeagueKeys.join(',')])

  /* ── Derived: filter legs by market category client-side ── */
  const displayedLegs = React.useMemo(() => {
    if (!ticket) return []
    // The API applies the technical market filter; do not re-filter display labels here.
    return ticket.legs.slice(0, config.selectionCount)
  }, [ticket, config.selectionCount])

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
      if (leagues.length > 0 && (activeLeagueKeys.length === 0 || config.selectedLeagues.length === 0)) {
        setTicket(null)
        setLoading(false)
        return
      }
      // Only gate/count against the daily limit when the user explicitly
      // clicked the generate button (isExplicitGenerate.current === true).
      // Auto-runs (mount, config changes) bypass this check entirely.
      if (isExplicitGenerate.current) {
        isExplicitGenerate.current = false
        if (onBeforeGenerate && !onBeforeGenerate()) return
      }
      setLoading(true)
      setError(false)

      try {
        const mode = RISK_MODE_MAP[config.riskProfile]
        const result = await fetchTickets(
          [mode],
          config.selectedLeagues.length === activeLeagueKeys.length ? undefined : config.selectedLeagues,
          undefined,
          config.selectionCount,
          config.selectedMarkets.length === MARKET_CATEGORIES.length ? undefined : config.selectedMarkets,
        )

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
  }, [config.riskProfile, config.selectedLeagues, config.selectedMarkets, config.selectionCount, generationKey, activeLeagueKeys.join(','), onBeforeGenerate])

  React.useEffect(() => {
    if (!isPro && config.riskProfile !== 'conservative') {
      setConfig((previous) => ({ ...previous, riskProfile: 'conservative' }))
    }
  }, [config.riskProfile, isPro])

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
      `BETMIND AI — BOLETO ${riskMeta.label}`,
      `CUOTA COMBINADA: ${formatOdds(combinedOddsDisplay)}`,
      ticket ? `EV PROMEDIO: ${formatEV(displayedLegs.reduce((sum, leg) => sum + leg.ev, 0) / displayedLegs.length)}` : '',
      ticket ? `CONFIANZA IA: ${ticket.confidence}%` : '',
      '',
      ...displayedLegs.map(
        (l, i) =>
          `${i + 1}. ${l.match}\n   ${formatMarketName(l.market)} @ ${formatOdds(l.odds)}`,
      ),
      '',
      `Generado por BetMind AI`,
    ].filter(Boolean)
    navigator.clipboard.writeText(lines.join('\n')).then(() => {
      toast('Boleto copiado al portapapeles', {
        description: `${displayedLegs.length} selecciones listas.`,
      })
    })
  }

  async function persistTicket(stakeAmount?: number) {
    if (!ticket) return
    const result = await addToTracking(ticket, stakeAmount)
    if (!result.saved) return
    onTrack?.()
    toast('Añadido a seguimiento', {
      description: `${displayedLegs.length} selecciones en seguimiento.`,
    })
  }

  function handleSave() {
    if (!ticket) return
    if (isPro && bankroll) {
      setStakeDialogOpen(true)
      return
    }
    void persistTicket()
  }

  async function handleShare() {
    if (!ticket) return
    const result = await shareOrDownloadTicket(ticket)
    if (result === 'shared') toast('Boleto compartido')
    if (result === 'downloaded') toast('Imagen descargada')
  }

  const activeProfile = RISK_PROFILES.find((r) => r.key === config.riskProfile)!
  const modeMeta = MODE_META[activeProfile.mode]
  const [leaguePopoverOpen, setLeaguePopoverOpen] = React.useState(false)
  const [leagueSearch, setLeagueSearch] = React.useState('')
  const selectedLeagueCount = config.selectedLeagues.filter((key) => activeLeagueKeySet.has(key)).length
  const filteredLeagues = activeLeagues.filter((league) =>
    `${league.label} ${league.key} ${league.group}`.toLowerCase().includes(leagueSearch.toLowerCase()),
  )
  const activeCountForGroup = (group?: string) => activeLeagues
    .filter((league) => !group || league.group === group)
    .reduce((total, league) => total + league.activeMatches, 0)
  const leaguePresets = [
    { label: 'Todas', group: undefined },
    { label: 'Big 5 Europa', group: 'Big 5 Europa' },
    { label: 'Sudamérica', group: 'Sudamérica' },
    { label: 'Copas UEFA', group: 'Copas UEFA' },
  ].map((preset) => ({ ...preset, count: activeCountForGroup(preset.group) }))
  const totalActive = activeCountForGroup()

  function toggleMarket(market: MarketKey) {
    setConfig((prev) => ({
      ...prev,
      selectedMarkets: prev.selectedMarkets.includes(market)
        ? prev.selectedMarkets.filter((item) => item !== market)
        : [...prev.selectedMarkets, market],
    }))
  }

  function toggleLeague(league: string) {
    setConfig((prev) => ({
      ...prev,
      selectedLeagues: prev.selectedLeagues.includes(league)
        ? prev.selectedLeagues.filter((item) => item !== league)
        : [...prev.selectedLeagues, league],
    }))
  }

  function applyLeaguePreset(group?: string) {
    setConfig((prev) => ({
      ...prev,
      selectedLeagues: group
        ? activeLeagues.filter((league) => league.group === group).map((league) => league.key)
        : activeLeagues.map((league) => league.key),
    }))
  }

  function swapLeg(index: number) {
    if (!ticket?.replacementCandidates?.length) return
    const usedMatches = new Set(ticket.legs.map((leg, legIndex) => legIndex === index ? '' : leg.match))
    const replacement = ticket.replacementCandidates.find((candidate) => !usedMatches.has(candidate.match))
    if (!replacement) return
    setTicket((current) => current ? {
      ...current,
      legs: current.legs.map((leg, legIndex) => legIndex === index ? replacement : leg),
      replacementCandidates: current.replacementCandidates?.filter((candidate) => candidate !== replacement),
    } : current)
  }

  /* ── empty-state reason ── */
  const emptyReason = React.useMemo(() => {
    if (leagues.length > 0 && (activeLeagues.length === 0 || selectedLeagueCount === 0)) {
      return 'No hay encuentros disponibles para este mercado hoy'
    }
    if (!ticket) return null
    if (ticket.legs.length === 0) {
      return 'No hay selecciones para los mercados y ligas actuales. Amplía los filtros o cambia el perfil de riesgo.'
    }
    return null
  }, [ticket, leagues.length, activeLeagues.length, selectedLeagueCount])

  /* ------------------------------------------------------------------ */
  /* Render                                                               */
  /* ------------------------------------------------------------------ */
  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <span className="text-[10px] font-bold uppercase tracking-widest text-subtle">Mercados permitidos</span>
        <div className="flex flex-wrap gap-1.5" role="group" aria-label="Mercados permitidos">
          {MARKET_CATEGORIES.map((market) => {
            const active = config.selectedMarkets.includes(market.key)
            return (
              <button key={market.key} type="button" aria-pressed={active} onClick={() => toggleMarket(market.key)} className={cn('cursor-pointer rounded-md border px-2.5 py-1 text-xs transition-colors', active ? 'border-primary/30 bg-primary/15 font-semibold text-primary' : 'border-border/50 bg-surface/40 text-muted-foreground hover:bg-surface')}>
                {market.label}
              </button>
            )
          })}
        </div>
      </div>

      <div className="relative flex flex-wrap items-center gap-1.5" aria-label="Presets y selección de ligas">
        {leaguePresets.filter((preset) => preset.label === 'Todas' || preset.count > 0).map((preset) => (
          <button key={preset.label} type="button" onClick={() => applyLeaguePreset(preset.group)} className="cursor-pointer rounded-md border border-border/50 bg-surface/40 px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-surface hover:text-foreground">
            {preset.label} ({preset.count})
          </button>
        ))}
        <button type="button" disabled={totalActive === 0} onClick={() => setLeaguePopoverOpen((open) => !open)} aria-expanded={leaguePopoverOpen} aria-label="Personalizar ligas activas" className="inline-flex cursor-pointer items-center gap-1 rounded-md border border-border/60 bg-surface/40 px-2.5 py-1 text-xs text-muted-foreground transition-colors hover:bg-surface hover:text-foreground disabled:pointer-events-none disabled:opacity-50">
          <Search size={12} aria-hidden /> Personalizar ligas ({selectedLeagueCount}) <ChevronDown size={12} aria-hidden />
        </button>
        {leaguePopoverOpen && (
          <div className="absolute left-0 top-full z-30 mt-2 w-full max-w-sm rounded-lg border border-border bg-card p-3 shadow-md">
            <div className="flex items-center gap-2 rounded-md border border-border/60 bg-surface/40 px-2 py-1.5">
              <Search size={13} className="text-muted-foreground" aria-hidden />
              <input aria-label="Buscar liga o país" name="league-search" autoComplete="off" value={leagueSearch} onChange={(event) => setLeagueSearch(event.target.value)} placeholder="Buscar liga o país" className="min-w-0 flex-1 bg-transparent text-xs text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/50 placeholder:text-muted-foreground" />
            </div>
            <div className="mt-2 max-h-60 space-y-1 overflow-y-auto">
              {filteredLeagues.length === 0 ? (
                <p className="p-2 font-mono text-xs text-muted-foreground">No hay encuentros disponibles para este mercado hoy</p>
              ) : filteredLeagues.map((league) => (
                <label key={league.key} className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1.5 text-xs text-muted-foreground hover:bg-surface hover:text-foreground">
                  <input type="checkbox" checked={config.selectedLeagues.includes(league.key)} onChange={() => toggleLeague(league.key)} className="accent-primary" />
                  <span>{league.label} <span className="font-mono text-[11px] tabular-nums text-muted-foreground">[{league.activeMatches}]</span></span>
                </label>
              ))}
            </div>
          </div>
        )}
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
                    aria-disabled={!isPro && profile.key !== 'conservative'}
                    disabled={!isPro && profile.key !== 'conservative'}
                    title={!isPro && profile.key !== 'conservative' ? 'Disponible en PRO' : undefined}
                    onClick={() =>
                      setConfig((prev) => ({ ...prev, riskProfile: profile.key }))
                    }
                    className={cn(
                      'flex flex-col items-center gap-1 rounded-lg border px-2 py-2.5 text-center transition-colors',
                      active
                        ? 'border-primary/60 bg-primary/10 text-primary'
                        : 'border-border bg-surface/40 text-muted-foreground hover:bg-surface hover:text-foreground',
                      !isPro && profile.key !== 'conservative' && 'cursor-not-allowed opacity-50',
                    )}
                  >
                    <span className="text-[11px] font-bold leading-none">
                      {!isPro && profile.key !== 'conservative' && <LockKeyhole className="mr-1 inline-block size-3" aria-hidden="true" />}
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

            <div className="flex items-center gap-1 rounded-lg border border-border/60 bg-surface/50 p-1">
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
                      'flex-1 rounded-md border py-2 text-[10px] font-bold transition-colors',
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
            onClick={() => {
              // Mark this as an explicit user-initiated generation so the
              // effect will call onBeforeGenerate() and count towards the
              // daily limit. Auto-runs must NOT set this flag.
              isExplicitGenerate.current = true
              setGenerationKey((k) => k + 1)
            }}
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
                    {modeMeta.label}
                </span>
                <span className="text-xs text-muted-foreground">
                  {config.selectionCount} selecciones ·{' '}
                  {config.selectedMarkets.length === MARKET_CATEGORIES.length
                    ? 'Todos los mercados'
                    : config.selectedMarkets.map((key) => MARKET_CATEGORIES.find((market) => market.key === key)?.label).join(', ')}
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
                    {formatOdds(combinedOddsDisplay)}
                  </span>
                  <div className="mt-1 flex items-center gap-2">
                    <span className="text-[10px] font-mono uppercase tracking-widest text-muted-foreground">Cuota Combinada</span>
                    <button type="button" onClick={handleCopy} title="Copiar texto del boleto" aria-label="Copiar texto del boleto" className="flex size-6 items-center justify-center rounded text-muted-foreground/60 transition-colors hover:bg-surface hover:text-foreground" disabled={!displayedLegs.length || loading}>
                      <Copy size={13} aria-hidden />
                    </button>
                  </div>
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
                     {formatEV(displayedLegs.reduce((total, leg) => total + leg.ev, 0) / Math.max(displayedLegs.length, 1))}
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
               <ul className="flex flex-col gap-2.5" key={`${generationKey}-${config.selectedMarkets.join('-')}-${config.selectionCount}`}>
                {displayedLegs.map((leg, i) => (
                  <TicketLeg
                    key={`${leg.match}-${leg.market}-${i}`}
                    leg={leg}
                    index={i}
                    onSwap={() => swapLeg(i)}
                    isPro={isPro}
                    bankroll={bankroll}
                    bankrollLoading={bankrollLoading}
                    ticketKellyStake={ticket?.kellyStake}
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

           {ticket?.optimizedCount && !loading && displayedLegs.length > 0 && (
             <div className="my-2 flex items-center gap-2 rounded-md border border-border/60 bg-surface/40 px-3.5 py-2 font-mono text-xs text-muted-foreground">
               Optimizado algorítmicamente: Reducimos tu boleto de {ticket.originalRequested} a {displayedLegs.length} selecciones para proteger tu Bankroll y mantener +EV real.
             </div>
           )}

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
                id="generator-save-ticket"
                onClick={handleSave}
                 disabled={!ticket || loading || (isPro && bankrollLoading)}
                className="flex w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-primary py-3 text-xs font-semibold text-primary-foreground shadow-sm transition-opacity hover:opacity-90 disabled:opacity-35"
              >
                <Star size={13} aria-hidden />
                Guardar en Ledger Cuantitativo
              </button>
              <button type="button" disabled={!ticket} onClick={handleShare} className="mt-2 w-full rounded-lg border border-border bg-transparent py-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-surface hover:text-foreground disabled:pointer-events-none disabled:opacity-50">
                Compartir / Descargar Imagen
              </button>
            </div>
          </div>
          {ticket && bankroll && (
            <StakeConfirmDialog
              open={stakeDialogOpen}
              onOpenChange={setStakeDialogOpen}
              ticket={ticket}
              bankroll={bankroll}
              onConfirm={(stakeAmount) => persistTicket(stakeAmount)}
            />
          )}
        </section>
      </div>
    </div>
  )
}
