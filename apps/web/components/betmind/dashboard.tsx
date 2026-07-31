'use client'

import * as React from 'react'

import { type Match, type Ticket } from '@/lib/betmind'
import { fetchTickets, fetchMatches } from '@/lib/api'
import { resolveLeague } from '@/lib/league-metadata'
import { cn } from '@/lib/utils'
import { LeagueSidebar } from './league-sidebar'
import { LeagueAccordion } from './league-accordion'
import { LeagueLogo } from './league-logo'
import { ScannerEmptyState } from './scanner-empty-state'
import { TicketCard } from './ticket-card'
import { TrackingPanel } from './tracking-panel'
import { BottomNav, TopNav, type NavTab } from './top-nav'
import { DateSelector, formatDateTitle, type DateFilter } from './date-selector'

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

/* ------------------------------------------------------------------ */
/* Dashboard                                                           */
/* ------------------------------------------------------------------ */

export function Dashboard() {
  const [tab, setTab] = React.useState<NavTab>('Boletos')
  const [league, setLeague] = React.useState('all')
  const [sidebarOpen, setSidebarOpen] = React.useState(false)
  const [dateFilter, setDateFilter] = React.useState<DateFilter>('today')
  const [today, setToday] = React.useState('')
  const [tickets, setTickets] = React.useState<Ticket[]>([])
  const [ticketsLoading, setTicketsLoading] = React.useState(true)
  const [matches, setMatches] = React.useState<Match[]>([])
  const [matchesLoading, setMatchesLoading] = React.useState(true)
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
      try {
        const filterParam = dateFilter === 'all' ? undefined : dateFilter
        const result = await fetchTickets(['EDGE', 'VALUE', 'BOLD'], undefined, filterParam)
        if (!cancelled) {
          setTickets(result.tickets)
          setTicketMeta({
            matchesAnalyzed: result.matchesAnalyzed,
            totalEv: result.totalEvOpportunities,
            generatedAt: result.generatedAt,
          })
        }
      } catch {
        if (!cancelled) setTickets([])
      } finally {
        if (!cancelled) setTicketsLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [dateFilter])

  React.useEffect(() => {
    let cancelled = false
    async function loadMatches() {
      try {
        const filterParam = dateFilter === 'all' ? undefined : dateFilter
        const fetchedMatches = await fetchMatches(filterParam)
        if (!cancelled) {
          setMatches(fetchedMatches.length > 0 ? fetchedMatches : [])
        }
      } catch {
        if (!cancelled) setMatches([])
      } finally {
        if (!cancelled) setMatchesLoading(false)
      }
    }
    loadMatches()
    return () => { cancelled = true }
  }, [dateFilter])

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

  const groupedMatches = React.useMemo(() => {
    const map = new Map<string, { key: string; externalId?: number | null; name: string; matches: Match[] }>()
    for (const m of filteredMatches) {
      const key = String(m.leagueExternalId ?? m.league ?? 'other')
      if (!map.has(key)) {
        map.set(key, { key, externalId: m.leagueExternalId, name: m.league ?? 'Otras Ligas', matches: [] })
      }
      map.get(key)!.matches.push(m)
    }
    return Array.from(map.values())
  }, [filteredMatches])

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
    <div className="min-h-svh bg-background pb-16 md:pb-0">
      <TopNav active={tab} onChange={setTab} onToggleSidebar={() => setSidebarOpen((v) => !v)} />

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
          <LeagueSidebar active={league} onSelect={selectLeague} matches={matches} />
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
                <div className="flex flex-wrap items-end justify-between gap-2">
                  <div>
                    <h1 className="text-xl font-bold tracking-tight text-foreground">
                      Boletos de {dateInfo.title}
                    </h1>
                    <p className="mt-0.5 text-xs text-subtle capitalize">{dateInfo.subtitle}</p>
                  </div>
                  <DateSelector value={dateFilter} onChange={setDateFilter} />
                  <p className="num text-xs text-muted-foreground">
                    {ticketMeta
                      ? `${ticketMeta.matchesAnalyzed} partidos · ${ticketMeta.totalEv} oportunidades +EV`
                      : 'Consultando modelo…'}
                  </p>
                </div>

                {ticketsLoading ? (
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                    {[0, 1, 2].map((i) => (
                      <TicketSkeleton key={i} />
                    ))}
                  </div>
                ) : (
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

              <div className="flex flex-col gap-3">
                {matchesLoading ? (
                  <div className="flex flex-col gap-3">
                    {[0, 1, 2, 3].map((i) => (
                      <MatchSkeleton key={i} />
                    ))}
                  </div>
                ) : groupedMatches.length > 0 ? (
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
                ) : (
                  <p className="rounded-lg border border-border bg-card p-6 text-center text-sm text-muted-foreground">
                    No hay partidos programados para esta liga hoy.
                  </p>
                )}
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
