'use client'

import * as React from 'react'
import { AlertCircle, RefreshCw, Sparkles, SlidersHorizontal, BrainCircuit, Filter } from 'lucide-react'

import { type Match, type Ticket, buildModel, marketRows, bestOpportunity } from '@/lib/betmind'
import { fetchTickets, fetchMatches, fetchLeagues, type LeagueData } from '@/lib/api'
import { resolveLeague } from '@/lib/league-metadata'
import { cn } from '@/lib/utils'
import { LeagueSidebar } from './league-sidebar'
import { LeagueAccordion } from './league-accordion'
import { LeagueLogo } from './league-logo'
import { ScannerEmptyState } from './scanner-empty-state'
import { TicketCard } from './ticket-card'
import { TicketGenerator } from './ticket-generator'
import { TrackingPanel } from './tracking-panel'
import { BottomNav, TopNav, type NavTab } from './top-nav'
import { DateSelector, formatDateKey, formatDateTitle, type DateFilter } from './date-selector'

/* ------------------------------------------------------------------ */
/* Skeletons                                                           */
/* ------------------------------------------------------------------ */

function TicketSkeleton() {
  return (
    <div className="flex h-full flex-col overflow-hidden rounded-xl border border-border bg-card">
      <div className="h-[3px] w-full bg-muted" />
      <div className="flex flex-col gap-3 p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="h-6 w-24 skeleton rounded-md" />
          <div className="h-5 w-16 skeleton rounded" />
        </div>
        <div className="h-[3px] w-full skeleton rounded-full" />
        <div className="h-3 w-32 skeleton rounded" />
      </div>
      <div className="flex flex-1 flex-col px-4 pb-0">
        {[0, 1, 2].map((i) => (
          <div key={i} className="grid grid-cols-[20px_1fr_auto] items-center gap-3 border-b border-border-subtle py-3 last:border-b-0">
            <div className="h-4 w-4 skeleton rounded" />
            <div className="flex flex-col gap-1.5">
              <div className="h-3 w-28 skeleton rounded" />
              <div className="h-2.5 w-20 skeleton rounded" />
            </div>
            <div className="h-6 w-10 skeleton rounded" />
          </div>
        ))}
      </div>
      <div className="flex flex-col gap-2 border-t border-border bg-surface-raised/50 p-4">
        <div className="h-7 w-full skeleton rounded-md" />
        <div className="h-2 w-48 skeleton rounded" />
      </div>
    </div>
  )
}

function MatchSkeleton() {
  return (
    <div className="flex items-center gap-4 rounded-xl border border-border bg-card px-4 py-3">
      {/* COLUMN 1 — Time / Status (100px) */}
      <div className="flex w-[100px] shrink-0 flex-col items-start gap-1">
        <div className="h-4 w-16 skeleton rounded" />
        <div className="h-4 w-14 skeleton rounded-full" />
      </div>

      {/* COLUMN 2 — Teams + Model (flex-1) */}
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex items-center gap-2">
          <div className="h-6 w-6 shrink-0 skeleton rounded" />
          <div className="h-4 w-28 skeleton rounded" />
          <div className="ml-auto h-4 w-10 skeleton rounded" />
        </div>
        <div className="flex items-center gap-2">
          <div className="h-6 w-6 shrink-0 skeleton rounded" />
          <div className="h-4 w-24 skeleton rounded" />
          <div className="ml-auto h-4 w-10 skeleton rounded" />
        </div>
        <div className="flex items-center gap-2">
          <div className="h-3 w-16 skeleton rounded" />
          <div className="h-3 w-36 skeleton rounded" />
        </div>
      </div>

      {/* COLUMN 3 — Edge + 1X2 + Link (180px) */}
      <div className="flex w-[180px] shrink-0 flex-col items-end gap-1.5">
        <div className="h-6 w-20 skeleton rounded-full" />
        <div className="flex gap-1.5">
          <div className="h-5 w-14 skeleton rounded-sm" />
          <div className="h-5 w-14 skeleton rounded-sm" />
          <div className="h-5 w-14 skeleton rounded-sm" />
        </div>
        <div className="h-3 w-20 skeleton rounded" />
      </div>
    </div>
  )
}

function LoadingState({ type }: { type: 'tickets' | 'matches' }) {
  return (
    <div aria-busy="true" aria-live="polite" className="flex flex-col gap-3">
      <span className="sr-only">Cargando {type === 'tickets' ? 'boletos' : 'partidos'}…</span>
      {type === 'tickets' ? (
        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {[0, 1, 2].map((i) => <TicketSkeleton key={i} />)}
        </div>
      ) : (
        [0, 1, 2, 3].map((i) => <MatchSkeleton key={i} />)
      )}
    </div>
  )
}

function formatUpdatedAt(value?: string | null) {
  if (!value) return 'Aún no hay una actualización registrada'
  return `Actualizado ${new Intl.DateTimeFormat('es-CO', {
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'America/Bogota',
  }).format(new Date(value))}`
}

function formatAge(value?: string | null) {
  if (!value) return 'Actualizando datos…'
  const minutes = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 60000))
  return minutes < 1 ? 'Actualizado ahora' : `Actualizado hace ${minutes} min`
}

function EmptyState({
  type,
  timestamp,
  onRefresh,
}: {
  type: 'tickets' | 'matches'
  timestamp?: string | null
  onRefresh: () => void
}) {
  const tickets = type === 'tickets'
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/60 px-6 py-12 text-center">
      <div className="mb-4 flex size-11 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary">
        <Sparkles size={18} aria-hidden="true" />
      </div>
      <h2 className="text-base font-semibold text-foreground">
        {tickets ? 'Todavía no hay una señal con valor' : 'No hay partidos en esta ventana'}
      </h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">
        {tickets
          ? 'El modelo revisa las cuotas y solo muestra boletos cuando encuentra una ventaja medible. Vuelve a consultar después de la próxima actualización.'
          : 'La cartelera se actualiza continuamente. Prueba otra fecha o vuelve a consultar cuando comiencen a publicarse nuevos fixtures.'}
      </p>
      <p className="mt-3 text-xs font-mono text-subtle">{formatUpdatedAt(timestamp)}</p>
      <button
        type="button"
        onClick={onRefresh}
        className="mt-6 inline-flex min-h-11 items-center gap-2 rounded-lg border border-border bg-surface px-4 text-sm font-semibold text-foreground transition-colors hover:border-primary/50 hover:bg-surface-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        <RefreshCw size={15} aria-hidden="true" />
        Actualizar ahora
      </button>
    </div>
  )
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-center justify-center rounded-2xl border border-negative/25 bg-negative/5 px-6 py-10 text-center">
      <AlertCircle size={20} className="text-negative" aria-hidden="true" />
      <h2 className="mt-3 text-base font-semibold text-foreground">No pudimos actualizar los datos</h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">
        La conexión con el modelo o la cartelera falló. Tus datos guardados no se han modificado.
      </p>
      <button
        type="button"
        onClick={onRetry}
        className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
      >
        <RefreshCw size={15} aria-hidden="true" />
        Reintentar
      </button>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Dashboard                                                           */
/* ------------------------------------------------------------------ */

type TicketViewMode = 'ia' | 'generator'
type CardFilter = 'all' | 'high_confidence' | 'best_value'

export function Dashboard() {
  const [tab, setTab] = React.useState<NavTab>('Boletos')
  const [ticketViewMode, setTicketViewMode] = React.useState<TicketViewMode>('ia')
  const [league, setLeague] = React.useState('all')
  const [cardFilter, setCardFilter] = React.useState<CardFilter>('all')
  const [sidebarOpen, setSidebarOpen] = React.useState(false)
  const [dateFilter, setDateFilter] = React.useState<DateFilter>('today')
  const [today, setToday] = React.useState('')
  const [tickets, setTickets] = React.useState<Ticket[]>([])
  const [ticketsLoading, setTicketsLoading] = React.useState(true)
  const [matches, setMatches] = React.useState<Match[]>([])
  const [leagues, setLeagues] = React.useState<LeagueData[]>([])
  const [matchesLoading, setMatchesLoading] = React.useState(true)
  const [ticketsError, setTicketsError] = React.useState(false)
  const [matchesError, setMatchesError] = React.useState(false)
  const [matchesUpdatedAt, setMatchesUpdatedAt] = React.useState<string | null>(null)
  const [retryKey, setRetryKey] = React.useState(0)
  const [ticketMeta, setTicketMeta] = React.useState<{
    matchesAnalyzed: number
    totalEv: number
    generatedAt: string
  } | null>(null)

  // refreshKey bumps whenever user tracks a ticket, causing TrackingPanel to re-read localStorage
  const [trackRefreshKey, setTrackRefreshKey] = React.useState(0)

  React.useEffect(() => {
    setToday(
      new Intl.DateTimeFormat('es-CO', {
        weekday: 'long',
        month: 'long',
        day: 'numeric',
        year: 'numeric',
        timeZone: 'America/Bogota',
      }).format(new Date()),
    )
  }, [])

  React.useEffect(() => {
    let cancelled = false
    async function load() {
      setTicketsLoading(true)
      setTicketsError(false)
      try {
        const filterParam = dateFilter === 'all' ? undefined : dateFilter
        const result = await fetchTickets(['EDGE', 'VALUE', 'BOLD'], undefined, filterParam)
        if (!cancelled) {
          if (!result.ok) throw new Error(result.error.message)
          setTickets(result.data.tickets)
          setTicketMeta({
            matchesAnalyzed: result.data.matchesAnalyzed,
            totalEv: result.data.totalEvOpportunities,
            generatedAt: result.data.generatedAt,
          })
        }
      } catch {
        if (!cancelled) {
          setTickets([])
          setTicketsError(true)
        }
      } finally {
        if (!cancelled) setTicketsLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [dateFilter, retryKey])

  React.useEffect(() => {
    let cancelled = false
    async function loadLeagues() {
      const result = await fetchLeagues(formatDateKey(dateFilter, new Date()))
      if (!cancelled) setLeagues(result.ok ? result.data : [])
    }
    loadLeagues()
    return () => { cancelled = true }
  }, [dateFilter, retryKey])

  React.useEffect(() => {
    let cancelled = false
    async function loadMatches() {
      setMatchesLoading(true)
      setMatchesError(false)
      try {
        const filterParam = dateFilter === 'all' ? undefined : dateFilter
        const fetchedMatches = await fetchMatches(filterParam)
        if (!cancelled) {
          if (!fetchedMatches.ok) throw new Error(fetchedMatches.error.message)
          setMatches(fetchedMatches.data.length > 0 ? fetchedMatches.data : [])
          setMatchesUpdatedAt(new Date().toISOString())
        }
      } catch {
        if (!cancelled) {
          setMatches([])
          setMatchesError(true)
        }
      } finally {
        if (!cancelled) setMatchesLoading(false)
      }
    }
    loadMatches()
    return () => { cancelled = true }
  }, [dateFilter, retryKey])

  const [openLeagues, setOpenLeagues] = React.useState<Record<string, boolean>>({})

  // Derive league pills from actual matches for the selected date
  const leaguePills = React.useMemo(() => {
    const countByLeague = new Map<string, { id: string; name: string; count: number; logoUrl: string | null }>()

    for (const m of matches) {
      const lid = String(m.leagueExternalId ?? 'other')
      if (!countByLeague.has(lid)) {
        const meta = resolveLeague(m.leagueExternalId, m.league)
        countByLeague.set(lid, {
          id: lid,
          name: meta.shortName,
          count: 0,
          logoUrl: m.leagueLogoUrl || meta.logoUrl,
        })
      }
      countByLeague.get(lid)!.count++
    }

    const pills = Array.from(countByLeague.values())
      .filter((l) => l.count > 0)
      .sort((a, b) => b.count - a.count)

    const total = matches.length
    return [
      { id: 'all', name: `Todas las Ligas (${total})`, count: total, logoUrl: null },
      ...pills,
    ]
  }, [matches])

  const filteredMatches = React.useMemo(
    () => (league === 'all' ? matches : matches.filter((m) => String(m.leagueExternalId ?? '') === league)),
    [league, matches],
  )

  // Quick card filter applied after league filter
  const quickFilteredMatches = React.useMemo(() => {
    if (cardFilter === 'all') return filteredMatches
    return filteredMatches.filter((m) => {
      const model = buildModel(m.lambdaHome, m.lambdaAway)
      if (cardFilter === 'high_confidence') {
        return model.home > 0.75 || model.away > 0.75
      }
      if (cardFilter === 'best_value') {
        const rows = marketRows(m, model)
        return bestOpportunity(rows) !== null
      }
      return true
    })
  }, [filteredMatches, cardFilter])

  const groupedMatches = React.useMemo(() => {
    const map = new Map<string, { key: string; externalId?: number | null; name: string; matches: Match[] }>()
    for (const m of quickFilteredMatches) {
      const key = String(m.leagueExternalId ?? m.league ?? 'other')
      if (!map.has(key)) {
        map.set(key, { key, externalId: m.leagueExternalId, name: m.league ?? 'Otras Ligas', matches: [] })
      }
      map.get(key)!.matches.push(m)
    }
    return Array.from(map.values())
  }, [quickFilteredMatches])

  function selectLeague(id: string) {
    setLeague(id)
    setSidebarOpen(false)
    if (tab === 'Boletos') setTab('Partidos')
  }

  // ── Isolated view flags ──────────────────────────────────────────────
  const showTickets = tab === 'Boletos'
  const showBoard   = tab === 'Partidos'
  const showScanner = tab === 'Escáner'

  const dateInfo = React.useMemo(() => formatDateTitle(dateFilter, new Date()), [dateFilter])

  return (
    <div className="min-h-svh bg-background pb-[calc(4rem+env(safe-area-inset-bottom))] md:pb-0">
      <TopNav
        active={tab}
        onChange={setTab}
        onToggleSidebar={() => setSidebarOpen((v) => !v)}
        activeLeagueCount={leagues.filter((league) => league.active_matches > 0).length}
      />

      <div className="mx-auto flex w-full max-w-[1600px] gap-6 px-4 py-6">
        {/* Sidebar — only shown on Partidos tab on mobile, always on desktop */}
        <aside
          className={cn(
            'w-[280px] shrink-0 lg:block',
            sidebarOpen
              ? 'fixed inset-y-14 left-0 z-30 overflow-y-auto border-r border-border bg-background p-4 lg:static lg:z-auto lg:border-r-0 lg:bg-transparent lg:p-0'
              : 'hidden',
          )}
        >
          <LeagueSidebar active={league} onSelect={selectLeague} matches={matches} leagues={leagues} />
        </aside>

        {sidebarOpen ? (
          <button
            type="button"
            aria-label="Close sidebar"
            onClick={() => setSidebarOpen(false)}
            className="fixed inset-0 z-20 bg-black/60 backdrop-blur-sm lg:hidden"
          />
        ) : null}

        <main className="flex min-w-0 flex-1 flex-col gap-8">
          {/* ── BOLETOS TAB — tickets + tracking only ── */}
          {showTickets ? (
            <>
              <section className="flex flex-col gap-4">
                {/* ── View mode toggle ── */}
                <div className="flex flex-wrap items-end justify-between gap-2">
                  <div>
                    <h1 className="text-xl font-bold tracking-tight text-foreground">
                      {ticketViewMode === 'ia'
                        ? `Oportunidades de ${dateInfo.title.toLowerCase()}`
                        : 'Generador de Boletos'}
                    </h1>
                    <p className="mt-0.5 text-xs text-subtle">
                      {ticketViewMode === 'ia' ? dateInfo.subtitle : 'Configura tu boleto con los controles de abajo'}
                    </p>
                  </div>

                  <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
                    {ticketViewMode === 'ia' && (
                      <DateSelector value={dateFilter} onChange={setDateFilter} />
                    )}
                    {/* Toggle */}
                    <div
                      role="group"
                      aria-label="Vista de boletos"
                      className="flex items-center rounded-lg border border-border bg-surface p-0.5"
                    >
                      <button
                        id="view-mode-ia"
                        type="button"
                        aria-pressed={ticketViewMode === 'ia'}
                        onClick={() => setTicketViewMode('ia')}
                        className={cn(
                          'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-colors duration-200',
                          ticketViewMode === 'ia'
                            ? 'bg-primary text-primary-foreground shadow-sm'
                            : 'text-muted-foreground hover:text-foreground',
                        )}
                      >
                        <BrainCircuit size={12} aria-hidden />
                        Boletos IA
                      </button>
                      <button
                        id="view-mode-generator"
                        type="button"
                        aria-pressed={ticketViewMode === 'generator'}
                        onClick={() => setTicketViewMode('generator')}
                        className={cn(
                          'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition-colors duration-200',
                          ticketViewMode === 'generator'
                            ? 'bg-primary text-primary-foreground shadow-sm'
                            : 'text-muted-foreground hover:text-foreground',
                        )}
                      >
                        <SlidersHorizontal size={12} aria-hidden />
                        Generador
                      </button>
                    </div>
                  </div>

                  {ticketViewMode === 'ia' && (
                    <p className="num w-full text-xs text-muted-foreground">
                      {ticketMeta
                        ? `${ticketMeta.totalEv} señales +EV · ${formatAge(ticketMeta.generatedAt)}`
                        : 'Consultando modelo…'}
                    </p>
                  )}
                </div>

                {/* ── IA mode: auto-generated tickets ── */}
                {ticketViewMode === 'ia' && (
                  ticketsLoading ? <LoadingState type="tickets" /> : ticketsError ? <ErrorState onRetry={() => setRetryKey((key) => key + 1)} /> : tickets.length > 0 ? (
                    <div className={cn(
                      'grid items-stretch gap-4',
                      tickets.length === 1 ? 'max-w-md' : tickets.length === 2 ? 'md:grid-cols-2 max-w-2xl' : 'md:grid-cols-2 xl:grid-cols-3',
                    )}>
                      {tickets.map((ticket) => (
                        <TicketCard
                          key={ticket.mode}
                          ticket={ticket}
                          onTrack={() => setTrackRefreshKey((k) => k + 1)}
                        />
                      ))}
                    </div>
                  ) : (
                    <EmptyState type="tickets" timestamp={ticketMeta?.generatedAt} onRefresh={() => setRetryKey((key) => key + 1)} />
                  )
                )}

                {/* ── Generator mode: interactive panel ── */}
                {ticketViewMode === 'generator' && (
                  <TicketGenerator
                    matches={matches}
                    leagues={leagues}
                    onTrack={() => setTrackRefreshKey((k) => k + 1)}
                  />
                )}
              </section>

              {/* Tracking panel — isolated below tickets */}
              <section className="flex flex-col gap-3">
                <h2 className="text-sm font-semibold text-foreground">Panel de Seguimiento</h2>
                <TrackingPanel refreshKey={trackRefreshKey} />
              </section>
            </>
          ) : null}

          {/* ── PARTIDOS TAB — match board only ── */}
          {showBoard ? (
            <section className="flex flex-col gap-4">
              <div className="flex flex-col gap-3">
                <h1 className="text-xl font-bold tracking-tight text-foreground">
                  Partidos de {dateInfo.title}
                </h1>
                <div className="flex items-center gap-3">
                  <DateSelector value={dateFilter} onChange={setDateFilter} />
                </div>
                <div className="no-scrollbar flex items-center gap-2 overflow-x-auto pb-1">
                  {leaguePills.map((pill) => (
                    <button
                      key={pill.id}
                      type="button"
                      onClick={() => setLeague(pill.id)}
                      aria-current={league === pill.id}
                      className={cn(
                        'flex items-center gap-1.5 rounded-sm border px-2.5 py-1 text-[11px] font-medium whitespace-nowrap transition-colors',
                        league === pill.id
                          ? 'border-primary bg-primary text-primary-foreground'
                          : 'border-border bg-background/40 text-muted-foreground hover:text-foreground',
                      )}
                    >
                      {pill.id !== 'all' && pill.logoUrl && (
                        <LeagueLogo logoUrl={pill.logoUrl} flag="" size="sm" className="brightness-0 invert" />
                      )}
                      {pill.name}
                    </button>
                  ))}
                </div>
              </div>

              {/* ── Filtros rápidos de predicción ── */}
              <div className="flex items-center gap-2">
                <Filter size={12} className="shrink-0 text-subtle" aria-hidden />
                <div className="no-scrollbar flex items-center gap-1.5 overflow-x-auto">
                  {([
                    { id: 'all', label: 'Todos' },
                    { id: 'high_confidence', label: 'ALTA CONFIANZA (>75%)' },
                    { id: 'best_value', label: '+EV MEJOR VALOR' },
                  ] as const).map((f) => (
                    <button
                      key={f.id}
                      id={`card-filter-${f.id}`}
                      type="button"
                      onClick={() => setCardFilter(f.id)}
                      aria-pressed={cardFilter === f.id}
                      className={cn(
                        'whitespace-nowrap rounded-full border px-3 py-1 text-[11px] font-semibold transition-colors duration-150',
                        cardFilter === f.id
                          ? f.id === 'best_value'
                            ? 'border-positive/40 bg-positive/15 text-positive shadow-[0_0_10px_-4px_var(--positive)]'
                            : f.id === 'high_confidence'
                              ? 'border-primary/40 bg-primary/15 text-primary'
                              : 'border-border bg-surface text-foreground'
                          : 'border-border/60 bg-transparent text-muted-foreground hover:border-border hover:text-foreground',
                      )}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
                {cardFilter !== 'all' && (
                  <span className="num text-[10px] text-subtle">
                    {quickFilteredMatches.length} partido{quickFilteredMatches.length !== 1 ? 's' : ''}
                  </span>
                )}
              </div>

              <div className="flex flex-col gap-3">
                {matchesLoading ? <LoadingState type="matches" /> : matchesError ? <ErrorState onRetry={() => setRetryKey((key) => key + 1)} /> : groupedMatches.length > 0 ? (
                  groupedMatches.map((group) => (
                    <LeagueAccordion
                      key={group.key}
                      leagueExternalId={group.externalId}
                      leagueName={group.name}
                      matches={group.matches}
                      isOpen={openLeagues[group.key] !== false}
                      onToggle={() =>
                        setOpenLeagues((prev) => ({ ...prev, [group.key]: prev[group.key] === false ? true : false }))
                      }
                    />
                  ))
                ) : <EmptyState type="matches" timestamp={matchesUpdatedAt} onRefresh={() => setRetryKey((key) => key + 1)} />}
              </div>
            </section>
          ) : null}

          {/* ── ESCÁNER TAB ── */}
          {showScanner ? (
            <ScannerEmptyState />
          ) : null}
        </main>
      </div>

      <BottomNav active={tab} onChange={setTab} />
    </div>
  )
}
