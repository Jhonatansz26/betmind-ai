'use client'

import * as React from 'react'

import { type Match, type Ticket } from '@/lib/betmind'
import { fetchTickets, fetchMatches, fetchLeagues } from '@/lib/api'
import { cn } from '@/lib/utils'
import { LeagueSidebar } from './league-sidebar'
import { MatchCard } from './match-card'
import { ScannerEmptyState } from './scanner-empty-state'
import { TicketCard } from './ticket-card'
import { TrackingPanel } from './tracking-panel'
import { BottomNav, TopNav, type NavTab } from './top-nav'

/* ------------------------------------------------------------------ */
/* Skeletons                                                           */
/* ------------------------------------------------------------------ */

function TicketSkeleton() {
  return (
    <div className="flex h-[380px] flex-col gap-0 overflow-hidden rounded-xl border border-border bg-card">
      <div className="h-[3px] w-full bg-muted" />
      <div className="flex flex-col gap-3 p-4">
        <div className="flex items-center justify-between gap-3">
          <div className="h-6 w-24 animate-pulse rounded-md bg-muted" />
          <div className="h-5 w-16 animate-pulse rounded bg-muted" />
        </div>
        <div className="h-[3px] w-full animate-pulse rounded-full bg-muted" />
        <div className="h-3 w-32 animate-pulse rounded bg-muted" />
      </div>
      <div className="flex flex-1 flex-col px-4 pb-0">
        {[0, 1, 2].map((i) => (
          <div key={i} className="grid grid-cols-[20px_1fr_auto] items-center gap-3 border-b border-border-subtle py-3 last:border-b-0">
            <div className="h-4 w-4 animate-pulse rounded bg-muted" />
            <div className="flex flex-col gap-1.5">
              <div className="h-3 w-28 animate-pulse rounded bg-muted" />
              <div className="h-2.5 w-20 animate-pulse rounded bg-muted" />
            </div>
            <div className="h-6 w-10 animate-pulse rounded bg-muted" />
          </div>
        ))}
      </div>
      <div className="flex flex-col gap-2 border-t border-border bg-surface-raised/50 p-4">
        <div className="flex items-center gap-2">
          <div className="h-7 flex-1 animate-pulse rounded-md bg-muted" />
          <div className="h-7 flex-1 animate-pulse rounded-md bg-muted" />
        </div>
        <div className="h-2 w-48 animate-pulse rounded bg-muted" />
      </div>
    </div>
  )
}

function MatchSkeleton() {
  return (
    <div className="flex flex-col gap-4 rounded-xl border border-border bg-card p-4 lg:flex-row lg:items-center lg:gap-6">
      <div className="flex items-center justify-between gap-3 lg:w-[20%] lg:flex-col lg:items-start lg:justify-start lg:gap-1.5">
        <div className="flex items-center gap-1.5">
          <div className="h-3 w-3 animate-pulse rounded bg-muted" />
          <div className="h-3 w-20 animate-pulse rounded bg-muted" />
        </div>
        <div className="h-4 w-16 animate-pulse rounded bg-muted" />
        <div className="h-5 w-16 animate-pulse rounded-sm bg-muted" />
      </div>
      <div className="flex flex-col gap-2 lg:w-[50%]">
        <div className="flex items-center justify-between gap-3">
          <div className="h-4 w-24 animate-pulse rounded bg-muted" />
          <div className="h-3 w-10 animate-pulse rounded bg-muted" />
        </div>
        <div className="flex items-center gap-3">
          <div className="h-12 w-[120px] animate-pulse rounded bg-muted" />
          <div className="flex flex-col gap-1">
            <div className="h-3 w-28 animate-pulse rounded bg-muted" />
            <div className="h-3 w-20 animate-pulse rounded bg-muted" />
          </div>
        </div>
        <div className="flex items-center justify-between gap-3">
          <div className="h-4 w-24 animate-pulse rounded bg-muted" />
          <div className="h-3 w-10 animate-pulse rounded bg-muted" />
        </div>
      </div>
      <div className="flex flex-col gap-2 border-t border-border pt-3 lg:w-[30%] lg:border-t-0 lg:pt-0 lg:pl-6">
        <div className="h-7 w-20 animate-pulse rounded-md bg-muted" />
        <div className="flex flex-wrap gap-1.5">
          <div className="h-5 w-14 animate-pulse rounded-sm bg-muted" />
          <div className="h-5 w-14 animate-pulse rounded-sm bg-muted" />
          <div className="h-5 w-14 animate-pulse rounded-sm bg-muted" />
        </div>
        <div className="h-4 w-24 animate-pulse rounded bg-muted" />
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
  const [leaguePills, setLeaguePills] = React.useState<{ id: string; name: string }[]>([{ id: 'all', name: 'Todas las Ligas' }])

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
        const result = await fetchTickets()
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
  }, [])

  React.useEffect(() => {
    let cancelled = false
    async function loadMatches() {
      try {
        const todayCot = new Date()
        const dateStr = todayCot.toLocaleDateString('en-CA', { timeZone: 'America/Bogota' })
        const fetchedMatches = await fetchMatches(dateStr)
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
  }, [])

  React.useEffect(() => {
    let cancelled = false
    async function loadLeagues() {
      try {
        const data = await fetchLeagues()
        if (!cancelled && data.length > 0) {
          setLeaguePills([
            { id: 'all', name: 'Todas las Ligas' },
            ...data.filter((l) => l.active_matches > 0).map((l) => ({ id: String(l.external_id), name: l.name })),
          ])
        }
      } catch {
        // keep default pills
      }
    }
    loadLeagues()
    return () => { cancelled = true }
  }, [])

  const filteredMatches = React.useMemo(
    () => (league === 'all' ? matches : matches.filter((m) => String(m.leagueExternalId ?? '') === league)),
    [league, matches],
  )

  function selectLeague(id: string) {
    setLeague(id)
    setSidebarOpen(false)
    if (tab === 'Boletos') setTab('Partidos')
  }

  // ── Isolated view flags ──────────────────────────────────────────────
  const showTickets = tab === 'Boletos'
  const showBoard   = tab === 'Partidos'
  const showScanner = tab === 'Escáner'

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
          <LeagueSidebar active={league} onSelect={selectLeague} />
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
                      Boletos de Hoy
                    </h1>
                    <p className="mt-0.5 text-xs text-subtle capitalize">{today}</p>
                  </div>
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
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
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
                  Partidos de Hoy
                </h1>
                <div className="no-scrollbar flex items-center gap-2 overflow-x-auto pb-1">
                  {leaguePills.map((pill) => (
                    <button
                      key={pill.id}
                      type="button"
                      onClick={() => setLeague(pill.id)}
                      aria-current={league === pill.id}
                      className={cn(
                        'rounded-sm border px-2.5 py-1 text-[11px] font-medium whitespace-nowrap transition-colors',
                        league === pill.id
                          ? 'border-primary bg-primary text-primary-foreground'
                          : 'border-border bg-background/40 text-muted-foreground hover:text-foreground',
                      )}
                    >
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
                ) : filteredMatches.length > 0 ? (
                  filteredMatches.map((match) => (
                    <MatchCard key={match.id} match={match} />
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
    </div>
  )
}
