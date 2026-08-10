'use client'

import * as React from 'react'
import { Filter, RefreshCw } from 'lucide-react'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'

import { type Match, buildModel, marketRows, bestOpportunity } from '@/lib/betmind'
import { resolveLeague } from '@/lib/league-metadata'
import { cn } from '@/lib/utils'
import { useMatches } from '@/lib/hooks/use-matches'
import { useLeagues } from '@/lib/hooks/use-leagues'

import { AppShell } from './app-shell'
import { DateSelector, formatDateKey, formatDateTitle, type DateFilter } from './date-selector'
import { LeagueAccordion } from './league-accordion'
import { LeagueLogo } from './league-logo'
import { LeagueSidebar } from './league-sidebar'
import { RouteError } from './route-states'

function MatchesSkeleton() {
  return <div aria-busy="true" className="flex flex-col gap-3"><span className="sr-only">Cargando partidos…</span>{[0, 1, 2, 3].map((item) => <div key={item} className="h-24 rounded-xl border border-border bg-card skeleton" />)}</div>
}

function EmptyMatches({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/60 px-6 py-12 text-center">
      <h2 className="text-base font-semibold text-foreground">No hay partidos en esta ventana</h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">La cartelera se actualiza continuamente. Prueba otra fecha o vuelve a consultar cuando comiencen a publicarse nuevos fixtures.</p>
      <button type="button" onClick={onRetry} className="mt-6 inline-flex min-h-11 items-center gap-2 rounded-lg border border-border bg-surface px-4 text-sm font-semibold text-foreground hover:bg-surface-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"><RefreshCw size={15} aria-hidden="true" /> Actualizar ahora</button>
    </div>
  )
}

function queryDateToFilter(value: string | null): DateFilter {
  if (value === 'all') return 'all'
  if (value === 'tomorrow' || value === formatDateKey('tomorrow')) return 'tomorrow'
  return 'today'
}

function apiDateValue(value: string | null, filter: DateFilter) {
  if (value && value !== 'all') return value
  return filter === 'all' ? undefined : filter
}

export function MatchesPage() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const urlDate = searchParams.get('fecha')
  const selectedLeague = searchParams.get('liga') ?? 'all'
  const dateFilter = queryDateToFilter(urlDate)
  const apiDate = apiDateValue(urlDate, dateFilter)

  const [sidebarOpen, setSidebarOpen] = React.useState(false)
  const [cardFilter, setCardFilter] = React.useState<'all' | 'high_confidence' | 'best_value'>('all')
  const [openLeagues, setOpenLeagues] = React.useState<Record<string, boolean>>({})

  // SWR-backed — shared with HomePage and GeneratorPage for the same apiDate.
  const { matches, isLoading: loading, error, revalidate } = useMatches(apiDate)
  const { leagues } = useLeagues(formatDateKey(dateFilter, new Date()))

  const updatedAt = React.useMemo(
    () => !loading && matches.length > 0 ? new Date().toISOString() : null,
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [loading],
  )

  function updateQuery(changes: { liga?: string; fecha?: string }) {
    const next = new URLSearchParams(searchParams.toString())
    if (changes.liga === undefined) {
      // Keep the current league filter when changing the date.
    } else if (changes.liga === 'all') {
      next.delete('liga')
    } else {
      next.set('liga', changes.liga)
    }
    if (changes.fecha === undefined) next.delete('fecha')
    else if (changes.fecha === 'all') next.set('fecha', 'all')
    else next.set('fecha', changes.fecha)
    const query = next.toString()
    router.replace(query ? `${pathname}?${query}` : pathname)
  }

  const leaguePills = React.useMemo(() => {
    const countByLeague = new Map<string, { id: string; name: string; count: number; logoUrl: string | null }>()
    for (const match of matches) {
      const id = String(match.leagueExternalId ?? 'other')
      if (!countByLeague.has(id)) {
        const meta = resolveLeague(match.leagueExternalId, match.league)
        countByLeague.set(id, { id, name: meta.shortName, count: 0, logoUrl: match.leagueLogoUrl || meta.logoUrl })
      }
      countByLeague.get(id)!.count++
    }
    return [
      { id: 'all', name: `Todas las Ligas (${matches.length})`, count: matches.length, logoUrl: null },
      ...Array.from(countByLeague.values()).filter((league) => league.count > 0).sort((a, b) => b.count - a.count),
    ]
  }, [matches])

  const filteredMatches = React.useMemo(() => selectedLeague === 'all' ? matches : matches.filter((match) => String(match.leagueExternalId ?? '') === selectedLeague), [matches, selectedLeague])
  const quickFilteredMatches = React.useMemo(() => {
    if (cardFilter === 'all') return filteredMatches
    return filteredMatches.filter((match) => {
      const model = buildModel(match.lambdaHome, match.lambdaAway)
      if (cardFilter === 'high_confidence') return model.home > 0.75 || model.away > 0.75
      return bestOpportunity(marketRows(match, model)) !== null
    })
  }, [cardFilter, filteredMatches])
  const groupedMatches = React.useMemo(() => {
    const groups = new Map<string, { key: string; externalId?: number | null; name: string; matches: Match[] }>()
    for (const match of quickFilteredMatches) {
      const key = String(match.leagueExternalId ?? match.league ?? 'other')
      if (!groups.has(key)) groups.set(key, { key, externalId: match.leagueExternalId, name: match.league ?? 'Otras Ligas', matches: [] })
      groups.get(key)!.matches.push(match)
    }
    return Array.from(groups.values())
  }, [quickFilteredMatches])

  const dateInfo = React.useMemo(() => formatDateTitle(dateFilter, new Date()), [dateFilter])

  return (
    <AppShell onToggleSidebar={() => setSidebarOpen((open) => !open)} activeLeagueCount={leagues.filter((league) => league.active_matches > 0).length}>
      <div className="flex gap-6">
        <aside className={cn('w-[280px] shrink-0 lg:block', sidebarOpen ? 'fixed inset-y-16 left-0 z-30 overflow-y-auto border-r border-border bg-background p-4 lg:static lg:z-auto lg:border-r-0 lg:bg-transparent lg:p-0' : 'hidden')}>
          <LeagueSidebar active={selectedLeague} onSelect={(league) => { updateQuery({ liga: league }); setSidebarOpen(false) }} matches={matches} leagues={leagues} />
        </aside>
        {sidebarOpen && <button type="button" aria-label="Cerrar catálogo de ligas" onClick={() => setSidebarOpen(false)} className="fixed inset-0 z-20 bg-black/60 backdrop-blur-sm lg:hidden" />}

        <section className="flex min-w-0 flex-1 flex-col gap-5">
          <div className="flex flex-col gap-3">
            <div className="flex flex-wrap items-end justify-between gap-3">
              <div><p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Cartelera</p><h1 className="mt-2 text-2xl font-bold tracking-tight text-foreground">Partidos de {dateInfo.title}</h1></div>
              <DateSelector value={dateFilter} onChange={(next) => updateQuery({ fecha: next === 'all' ? 'all' : formatDateKey(next, new Date()) })} />
            </div>
            <div className="no-scrollbar flex items-center gap-2 overflow-x-auto pb-1">
              {leaguePills.map((pill) => <button key={pill.id} type="button" onClick={() => updateQuery({ liga: pill.id })} aria-current={selectedLeague === pill.id ? 'page' : undefined} className={cn('flex items-center gap-1.5 rounded-sm border px-2.5 py-1 text-[11px] font-medium whitespace-nowrap transition-colors', selectedLeague === pill.id ? 'border-primary bg-primary text-primary-foreground' : 'border-border bg-background/40 text-muted-foreground hover:text-foreground')}>
                {pill.id !== 'all' && pill.logoUrl && <LeagueLogo logoUrl={pill.logoUrl} flag="" size="sm" className="brightness-0 invert" />}
                {pill.name}
              </button>)}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Filter size={12} className="shrink-0 text-subtle" aria-hidden="true" />
            <div className="no-scrollbar flex items-center gap-1.5 overflow-x-auto">
              {([
                { id: 'all', label: 'Todos' },
                { id: 'high_confidence', label: 'ALTA CONFIANZA (>75%)' },
                { id: 'best_value', label: '+EV MEJOR VALOR' },
              ] as const).map((filter) => <button key={filter.id} type="button" onClick={() => setCardFilter(filter.id)} aria-pressed={cardFilter === filter.id} className={cn('whitespace-nowrap rounded-full border px-3 py-1 text-[11px] font-semibold transition-colors', cardFilter === filter.id ? filter.id === 'best_value' ? 'border-positive/40 bg-positive/15 text-positive' : filter.id === 'high_confidence' ? 'border-primary/40 bg-primary/15 text-primary' : 'border-border bg-surface text-foreground' : 'border-border/60 bg-transparent text-muted-foreground hover:border-border hover:text-foreground')}>{filter.label}</button>)}
            </div>
          </div>

          {loading ? <MatchesSkeleton /> : error ? <RouteError label="los partidos" onRetry={revalidate} /> : groupedMatches.length > 0 ? <div className="flex flex-col gap-3">{groupedMatches.map((group) => <LeagueAccordion key={group.key} leagueExternalId={group.externalId} leagueName={group.name} matches={group.matches} isOpen={openLeagues[group.key] !== false} onToggle={() => setOpenLeagues((current) => ({ ...current, [group.key]: current[group.key] === false }))} />)}</div> : <EmptyMatches onRetry={revalidate} />}
          {updatedAt && <p className="text-right text-[10px] font-mono text-subtle">Actualizado {new Intl.DateTimeFormat('es-CO', { hour: 'numeric', minute: '2-digit', timeZone: 'America/Bogota' }).format(new Date(updatedAt))}</p>}
        </section>
      </div>
    </AppShell>
  )
}
