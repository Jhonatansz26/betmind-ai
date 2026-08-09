'use client'

import * as React from 'react'
import { ArrowUpRight, CalendarDays, ChevronRight, CircleAlert, RefreshCw, Sparkles, Ticket, Trophy } from 'lucide-react'

import type { Match, Ticket as BetmindTicket } from '@/lib/betmind'
import { formatEV, formatOdds } from '@/lib/formatters'
import { useAuthSession } from '@/lib/hooks/use-auth-session'
import { summarizeTrackedTickets } from '@/lib/tracking'
import { cn } from '@/lib/utils'
import { StatDisclaimer } from './stat-disclaimer'
import { useTicketHistory } from './use-ticket-history'

interface HomeViewProps {
  greeting: string
  dateLabel: string
  tickets: BetmindTicket[]
  ticketsLoading: boolean
  ticketsError: boolean
  ticketCount: number | null
  onRetryTickets: () => void
  matches: Match[]
  matchesLoading: boolean
  matchesError: boolean
  onRetryMatches: () => void
  onOpenTickets: () => void
  onOpenGenerator: () => void
  onOpenMatches: () => void
}

function BlockSkeleton({ type }: { type: 'signals' | 'matches' | 'summary' }) {
  if (type === 'summary') {
    return <div aria-busy="true" className="grid grid-cols-2 gap-3 sm:grid-cols-4">{[0, 1, 2, 3].map((item) => <div key={item} className="h-16 rounded-xl bg-surface-raised skeleton" />)}</div>
  }
  return <div aria-busy="true" className={cn('grid gap-3', type === 'signals' ? 'md:grid-cols-3' : 'md:grid-cols-3')}>{[0, 1, 2].map((item) => <div key={item} className={cn('rounded-2xl border border-border bg-card p-4 skeleton', type === 'signals' ? 'h-52' : 'h-32')} />)}</div>
}

function BlockError({ label, onRetry }: { label: string; onRetry: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-2xl border border-negative/25 bg-negative/5 p-5 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3">
        <CircleAlert size={18} className="mt-0.5 shrink-0 text-negative" aria-hidden="true" />
        <div>
          <p className="text-sm font-semibold text-foreground">No pudimos cargar {label}</p>
          <p className="mt-1 text-xs leading-5 text-muted-foreground">Revisá tu conexión e intentá actualizar este bloque.</p>
        </div>
      </div>
      <button type="button" onClick={onRetry} className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-border bg-surface px-3 text-xs font-semibold text-foreground transition-colors hover:bg-surface-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
        <RefreshCw size={14} aria-hidden="true" /> Reintentar
      </button>
    </div>
  )
}

function SignalCard({ ticket, onOpen }: { ticket: BetmindTicket; onOpen: () => void }) {
  const topLeg = ticket.legs[0]
  return (
    <article className="flex min-h-52 flex-col rounded-2xl border border-border bg-card p-4 transition-colors hover:border-primary/40">
      <div className="flex items-center justify-between gap-3">
        <span className="rounded-md border border-positive/30 bg-positive/10 px-2 py-1 text-[10px] font-bold uppercase tracking-wider text-positive">{ticket.mode} · +EV</span>
        <span className="font-mono text-lg font-bold tabular-nums text-positive">{formatEV(ticket.evAverage)}</span>
      </div>
      <div className="mt-5 min-w-0">
        <p className="truncate text-sm font-semibold text-foreground">{topLeg?.match ?? 'Selección del modelo'}</p>
        <p className="mt-1 truncate text-xs text-muted-foreground">{topLeg?.market ?? 'Mercado recomendado'} · cuota {formatOdds(topLeg?.odds ?? ticket.combinedOdds)}</p>
      </div>
      <div className="mt-auto flex items-center justify-between gap-3 border-t border-border/60 pt-4">
        <span className="font-mono text-[10px] uppercase tracking-wider text-subtle">{ticket.confidence}% confianza</span>
        <button type="button" onClick={onOpen} className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
          Ver boleto completo <ArrowUpRight size={14} aria-hidden="true" />
        </button>
      </div>
    </article>
  )
}

function MatchCard({ match }: { match: Match }) {
  return (
    <article className="rounded-2xl border border-border bg-card p-4">
      <div className="flex items-center justify-between gap-3 text-[10px] font-semibold uppercase tracking-wider text-subtle">
        <span className="truncate">{match.league}</span>
        <span className="shrink-0">{match.time}</span>
      </div>
      <div className="mt-4 flex items-center justify-between gap-3 text-sm font-semibold text-foreground">
        <span className="truncate">{match.home}</span>
        <span className="font-mono text-xs text-subtle">vs</span>
        <span className="truncate text-right">{match.away}</span>
      </div>
    </article>
  )
}

export function HomeView({
  greeting,
  dateLabel,
  tickets,
  ticketsLoading,
  ticketsError,
  ticketCount,
  onRetryTickets,
  matches,
  matchesLoading,
  matchesError,
  onRetryMatches,
  onOpenTickets,
  onOpenGenerator,
  onOpenMatches,
}: HomeViewProps) {
  const { isAuthenticated, isLoading: authLoading } = useAuthSession()
  const { entries: trackedEntries, loading: summaryLoading } = useTicketHistory(isAuthenticated, authLoading)
  const summary = React.useMemo(() => summarizeTrackedTickets(trackedEntries), [trackedEntries])
  const roiLabel = summary.roiApprox == null ? 'No disponible' : `${summary.roiApprox >= 0 ? '+' : ''}${summary.roiApprox.toFixed(1)}%`
  const featuredTickets = React.useMemo(
    () => [...tickets].sort((a, b) => b.evAverage - a.evAverage).slice(0, 3),
    [tickets],
  )
  const featuredMatches = matches.slice(0, 3)

  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-4 rounded-3xl border border-border bg-card p-5 sm:p-7">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Tu tablero de hoy</p>
            <h1 className="mt-2 text-3xl font-bold tracking-tight text-foreground sm:text-4xl">{greeting}</h1>
            <p className="mt-2 text-sm text-muted-foreground">{dateLabel}</p>
          </div>
          <div className="flex items-center gap-2 rounded-xl border border-border/70 bg-surface/70 px-3 py-2 text-xs text-muted-foreground">
            <CalendarDays size={15} className="text-primary" aria-hidden="true" />
            <span>Hoy hay <strong className="font-mono text-foreground">{ticketCount ?? '—'}</strong> señales +EV</span>
          </div>
        </div>
      </section>

      {!summaryLoading && summary.total > 0 && (
        <section aria-labelledby="home-summary-title" className="flex flex-col gap-3">
          <div className="flex items-center gap-2">
            <Trophy size={16} className="text-primary" aria-hidden="true" />
            <h2 id="home-summary-title" className="text-base font-semibold text-foreground">Tu resumen</h2>
          </div>
          <div className="grid grid-cols-2 gap-3 rounded-2xl border border-border bg-card p-4 sm:grid-cols-4">
            <div><p className="text-[10px] font-semibold uppercase tracking-wider text-subtle">Boletos activos</p><p className="mt-1 font-mono text-2xl font-bold tabular-nums text-foreground">{summary.active}</p></div>
            <div><p className="text-[10px] font-semibold uppercase tracking-wider text-subtle">Ganados</p><p className="mt-1 font-mono text-2xl font-bold tabular-nums text-positive">{summary.won}</p></div>
            <div><p className="text-[10px] font-semibold uppercase tracking-wider text-subtle">Perdidos</p><p className="mt-1 font-mono text-2xl font-bold tabular-nums text-negative">{summary.lost}</p></div>
            <div><p className="text-[10px] font-semibold uppercase tracking-wider text-subtle">ROI</p><p className={cn('mt-1 font-mono text-2xl font-bold tabular-nums', summary.roiApprox == null ? 'text-muted-foreground' : summary.roiApprox >= 0 ? 'text-positive' : 'text-negative')}>{roiLabel}</p></div>
          </div>
          {summary.roiApprox === null ? <p className="text-[11px] text-subtle">El ROI aparecerá cuando exista información persistida de stake y payout.</p> : summary.roiTicketCount < summary.total ? <p className="text-[11px] text-subtle">Calculado sobre {summary.roiTicketCount} de {summary.total} boletos con seguimiento de bankroll.</p> : null}
        </section>
      )}
      {summaryLoading && <section aria-label="Cargando tu resumen"><BlockSkeleton type="summary" /></section>}

      <section aria-labelledby="home-signals-title" className="flex flex-col gap-3">
        <div className="flex items-end justify-between gap-3">
          <div>
            <div className="flex items-center gap-2"><Sparkles size={16} className="text-positive" aria-hidden="true" /><h2 id="home-signals-title" className="text-base font-semibold text-foreground">Señales de hoy</h2></div>
            <p className="mt-1 text-xs text-muted-foreground">Las oportunidades con mayor valor esperado disponible ahora.</p>
          </div>
          <span className="hidden font-mono text-[10px] uppercase tracking-wider text-subtle sm:block">Top 3 por EV</span>
        </div>
        {ticketsLoading ? <BlockSkeleton type="signals" /> : ticketsError ? <BlockError label="las señales" onRetry={onRetryTickets} /> : featuredTickets.length > 0 ? <div className="grid gap-3 md:grid-cols-3">{featuredTickets.map((ticket) => <SignalCard key={ticket.mode} ticket={ticket} onOpen={onOpenTickets} />)}</div> : <div className="rounded-2xl border border-dashed border-border bg-card/60 p-8 text-center"><p className="text-sm font-semibold text-foreground">No hay señales +EV disponibles todavía</p><button type="button" onClick={onRetryTickets} className="mt-3 text-xs font-semibold text-primary hover:underline">Actualizar señales</button></div>}
        <StatDisclaimer />
      </section>

      <section aria-labelledby="home-matches-title" className="flex flex-col gap-3">
        <div className="flex items-end justify-between gap-3">
          <div><div className="flex items-center gap-2"><Ticket size={16} className="text-primary" aria-hidden="true" /><h2 id="home-matches-title" className="text-base font-semibold text-foreground">Explorar partidos</h2></div><p className="mt-1 text-xs text-muted-foreground">Una mirada rápida a la cartelera de hoy.</p></div>
          <button type="button" onClick={onOpenMatches} className="inline-flex items-center gap-1 text-xs font-semibold text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">Ver toda la cartelera <ChevronRight size={14} aria-hidden="true" /></button>
        </div>
        {matchesLoading ? <BlockSkeleton type="matches" /> : matchesError ? <BlockError label="los partidos" onRetry={onRetryMatches} /> : featuredMatches.length > 0 ? <div className="grid gap-3 md:grid-cols-3">{featuredMatches.map((match) => <MatchCard key={match.id} match={match} />)}</div> : <div className="rounded-2xl border border-dashed border-border bg-card/60 p-8 text-center text-sm text-muted-foreground">No hay partidos en esta ventana.</div>}
      </section>

      <div className="h-12 md:h-0">
        <div className="fixed inset-x-4 bottom-[calc(4.5rem+env(safe-area-inset-bottom))] z-30 flex justify-center md:inset-x-auto md:bottom-6 md:right-8 md:justify-end">
          <button type="button" onClick={onOpenGenerator} className="inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-2xl bg-primary px-6 text-sm font-bold text-primary-foreground shadow-xl shadow-primary/20 transition-transform hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary sm:w-auto">
          <Sparkles size={17} aria-hidden="true" /> Generar mi boleto
          </button>
        </div>
      </div>
    </div>
  )
}
