'use client'

import * as React from 'react'

import { type Match, type Ticket } from '@/lib/betmind'
import { fetchTickets, fetchMatches, fetchLeagues } from '@/lib/api'
import { cn } from '@/lib/utils'
import { LeagueSidebar } from './league-sidebar'
import { MatchCard } from './match-card'
import { MatchModal } from './match-modal'
import { ScannerEmptyState } from './scanner-empty-state'
import { TicketCard } from './ticket-card'
import { BottomNav, TopNav, type NavTab } from './top-nav'

function TicketSkeleton() {
  return (
    <div className="flex h-[420px] flex-col gap-0 overflow-hidden rounded-xl border border-border bg-card">
      <div className="h-[3px] w-full bg-muted" />
      <div className="flex flex-col gap-4 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="h-6 w-24 animate-pulse rounded-md bg-muted" />
          <div className="h-8 w-16 animate-pulse rounded bg-muted" />
        </div>
        <div className="flex flex-col gap-2">
          <div className="h-9 w-32 animate-pulse rounded bg-muted" />
          <div className="h-4 w-48 animate-pulse rounded bg-muted" />
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-3 p-4 pt-0">
        {[0, 1, 2].map((i) => (
          <div key={i} className="flex flex-col gap-2 rounded-md border border-border bg-background/40 p-3">
            <div className="flex items-center gap-2">
              <div className="h-4 w-4 animate-pulse rounded bg-muted" />
              <div className="h-3 w-32 animate-pulse rounded bg-muted" />
            </div>
            <div className="flex items-center justify-between gap-2">
              <div className="h-4 w-24 animate-pulse rounded bg-muted" />
              <div className="h-5 w-14 animate-pulse rounded-md bg-muted" />
            </div>
            <div className="flex items-center gap-2">
              <div className="h-5 w-16 animate-pulse rounded-sm bg-muted" />
              <div className="h-3 w-12 animate-pulse rounded bg-muted" />
            </div>
          </div>
        ))}
        <div className="mt-auto flex items-center justify-between rounded-md border border-border px-3 py-2">
          <div className="h-3 w-36 animate-pulse rounded bg-muted" />
          <div className="h-3 w-3 animate-pulse rounded bg-muted" />
        </div>
      </div>
      <div className="flex flex-col gap-3 border-t border-border p-4">
        <div className="flex items-center gap-2">
          <div className="h-7 flex-1 animate-pulse rounded-md bg-muted" />
          <div className="h-7 flex-1 animate-pulse rounded-md bg-muted" />
        </div>
        <div className="h-3 w-48 animate-pulse rounded bg-muted" />
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

export function Dashboard() {
  const [tab, setTab] = React.useState<NavTab>("Boletos de Hoy")
  const [league, setLeague] = React.useState('all')
  const [sidebarOpen, setSidebarOpen] = React.useState(false)
  const [activeMatch, setActiveMatch] = React.useState<Match | null>(null)
  const [modalOpen, setModalOpen] = React.useState(false)
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

  React.useEffect(() => {
    setToday(
      new Intl.DateTimeFormat('en-US', {
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

  function openMatch(match: Match) {
    setActiveMatch(match)
    setModalOpen(true)
  }

  function selectLeague(id: string) {
    setLeague(id)
    setSidebarOpen(false)
    if (tab === "Boletos de Hoy") setTab('Cartelera')
  }

  const showTickets = tab === "Boletos de Hoy"
  const showBoard = tab === "Boletos de Hoy" || tab === 'Cartelera'
  const showScanner = tab === 'Escáner'

  return (
    <div className="min-h-svh bg-background pb-16 md:pb-0">
      <TopNav active={tab} onChange={setTab} onToggleSidebar={() => setSidebarOpen((v) => !v)} />

      <div className="mx-auto flex w-full max-w-[1600px] gap-6 px-4 py-6">
        {/* Sidebar */}
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

        <main className="flex min-w-0 flex-1 flex-col gap-10">
          {/* SECTION 1 — tickets */}
          {showTickets ? (
            <section className="flex flex-col gap-4">
              <div className="flex flex-col gap-2">
                <div className="flex flex-wrap items-end justify-between gap-2">
                  <h1 className="font-serif text-2xl italic text-foreground sm:text-3xl">
                    Informe de Inteligencia de Hoy
                  </h1>
                  <p className="num text-xs text-muted-foreground">{today}</p>
                </div>
                <p className="max-w-2xl text-pretty text-sm leading-relaxed text-muted-foreground">
                  {ticketMeta
                    ? `${ticketMeta.matchesAnalyzed} partidos analizados · ${ticketMeta.totalEv} oportunidades +EV detectadas`
                    : 'Consultando datos del modelo...'}
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
                    <TicketCard key={ticket.mode} ticket={ticket} />
                  ))}
                </div>
              )}
            </section>
          ) : null}

          {/* SECTION 2 — match board */}
          {showBoard ? (
            <section className="flex flex-col gap-4">
              <div className="flex flex-col gap-3">
                <h2 className="font-serif text-2xl italic text-foreground">
                  {"Partidos de Hoy"}
                </h2>
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
                    <MatchCard key={match.id} match={match} onOpen={openMatch} />
                  ))
                ) : (
                  <p className="rounded-lg border border-border bg-card p-6 text-center text-sm text-muted-foreground">
                    No hay partidos programados para esta liga hoy.
                  </p>
                )}
              </div>
            </section>
          ) : null}

          {/* SECTION 3 — scanner */}
          {showScanner ? (
            <ScannerEmptyState />
          ) : null}
        </main>
      </div>

      <MatchModal match={activeMatch} open={modalOpen} onOpenChange={setModalOpen} />
      <BottomNav active={tab} onChange={setTab} />
    </div>
  )
}
