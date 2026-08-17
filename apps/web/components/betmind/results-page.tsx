'use client'

import * as React from 'react'
import { Trophy } from 'lucide-react'

import { formatMarketName } from '@/lib/formatMarketName'
import { MODE_META, type Mode } from '@/lib/betmind'
import { fetchPublicResults, type FeaturedTicketRecord, type PublicResultsResponse } from '@/lib/api'
import { formatEV, formatOdds } from '@/lib/formatters'
import { cn } from '@/lib/utils'

import { AppShell } from './app-shell'
import { RouteError } from './route-states'
import { StatDisclaimer } from './stat-disclaimer'

const COT_TIME_ZONE = 'America/Bogota'

function cotDateString(daysAgo: number): string {
  const date = new Date()
  date.setUTCDate(date.getUTCDate() - daysAgo)
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: COT_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date)
}

function dayTitle(daysAgo: number): string {
  const date = new Date()
  date.setUTCDate(date.getUTCDate() - daysAgo)
  return new Intl.DateTimeFormat('es-CO', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    timeZone: COT_TIME_ZONE,
  }).format(date)
}

const STATUS_META: Record<FeaturedTicketRecord['status'], { label: string; classes: string }> = {
  WON: { label: 'Ganado', classes: 'border-positive/40 bg-positive/10 text-positive' },
  LOST: { label: 'Perdido', classes: 'border-negative/40 bg-negative/10 text-negative' },
  PENDING: { label: 'Pendiente', classes: 'border-border bg-surface text-muted-foreground' },
}

function modeMeta(mode: string) {
  const key = mode.toUpperCase() as Mode
  return MODE_META[key] ?? MODE_META.EDGE
}

function winRateLabel(summary: PublicResultsResponse['summary_7d'] | undefined): string | null {
  if (!summary || summary.resolved === 0) return null
  return `${Math.round((summary.won / summary.resolved) * 100)}%`
}

function SummaryStrip({ data }: { data: PublicResultsResponse }) {
  const s7 = data.summary_7d
  const s30 = data.summary_30d
  const rate7 = winRateLabel(s7)
  const rate30 = winRateLabel(s30)

  return (
    <section aria-label="Resumen de resultados del sistema" className="grid gap-3 md:grid-cols-3">
      <div className="rounded-2xl border border-positive/30 bg-positive/5 p-5 ring-1 ring-positive/10">
        <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-positive">Últimos 7 días</p>
        <p className="mt-3 text-3xl font-bold tabular-nums tracking-tight text-foreground">
          {s7.resolved > 0 ? `${s7.won} de ${s7.resolved}` : '—'}
        </p>
        <p className="mt-1 text-sm text-subtle">boletos ganados</p>
        <p className={cn('mt-3 font-mono text-2xl font-bold tabular-nums', rate7 != null ? (s7.won / s7.resolved >= 0.5 ? 'text-positive' : 'text-negative') : 'text-muted-foreground')}>
          {rate7 ?? 'Sin datos'}
        </p>
        <p className="mt-1 text-[11px] text-subtle">Récord real del sistema, sin curar.</p>
      </div>

      <div className="rounded-2xl border border-border bg-card p-5">
        <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-subtle">Últimos 30 días</p>
        <p className="mt-3 text-3xl font-bold tabular-nums tracking-tight text-foreground">
          {s30.resolved > 0 ? `${s30.won} de ${s30.resolved}` : '—'}
        </p>
        <p className="mt-1 text-sm text-subtle">boletos ganados</p>
        <p className={cn('mt-3 font-mono text-2xl font-bold tabular-nums', rate30 != null ? (s30.won / s30.resolved >= 0.5 ? 'text-positive' : 'text-negative') : 'text-muted-foreground')}>
          {rate30 ?? 'Sin datos'}
        </p>
      </div>

      <div className="rounded-2xl border border-border bg-card p-5">
        <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-subtle">En juego (7 días)</p>
        <p className="mt-3 text-3xl font-bold tabular-nums tracking-tight text-foreground">{s7.pending}</p>
        <p className="mt-1 text-sm text-subtle">boletos pendientes de resolución</p>
        <p className="mt-3 font-mono text-xs text-muted-foreground">{s7.total} boletos generados</p>
      </div>
    </section>
  )
}

function TicketLegRow({ leg, index }: { leg: FeaturedTicketRecord['legs'][number]; index: number }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 border-b border-border/40 py-2.5 last:border-b-0">
      <div className="flex min-w-0 items-center gap-3">
        <span className="font-mono text-[10px] font-bold text-subtle">{index + 1}</span>
        <div className="min-w-0">
          <p className="truncate text-sm font-medium text-foreground">
            {leg.home_team} <span className="text-subtle">vs</span> {leg.away_team}
          </p>
          <p className="mt-0.5 text-xs text-subtle">{formatMarketName(leg.market_label)}</p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        <span className="font-mono text-xs text-muted-foreground">{Math.round(leg.our_probability * 100)}%</span>
        <span className="font-mono text-sm font-semibold tabular-nums text-foreground">{formatOdds(leg.bookmaker_odds)}</span>
      </div>
    </li>
  )
}

function FeaturedTicketCard({ ticket }: { ticket: FeaturedTicketRecord }) {
  const meta = modeMeta(ticket.mode)
  const status = STATUS_META[ticket.status]

  return (
    <article className="flex h-full flex-col rounded-xl border border-border bg-card ring-1 ring-white/5">
      <div className={cn('h-[3px] w-full shrink-0 rounded-t-xl', meta.accent)} aria-hidden />
      <div className="flex items-center justify-between gap-3 p-4 pb-2">
        <span className={cn('inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-semibold tracking-wide', meta.border, meta.bg, meta.text)}>
          {meta.label}
        </span>
        <span className={cn('inline-flex items-center rounded-md border px-2.5 py-1 text-[11px] font-bold uppercase tracking-wide', status.classes)}>
          {status.label}
        </span>
      </div>

      <div className="flex flex-col gap-1 px-4 pb-3">
        <div className="flex items-end justify-between gap-3">
          <div>
            <span className="font-mono text-4xl font-bold tabular-nums tracking-tight leading-none text-foreground">
              {formatOdds(ticket.combined_odds)}
            </span>
            <p className="mt-1 text-[10px] font-mono uppercase tracking-widest text-muted-foreground">Cuota combinada</p>
          </div>
          <div className="text-right">
            <span className={cn('font-mono text-lg font-bold tabular-nums', ticket.real_ev >= 0 ? 'text-positive' : 'text-negative')}>
              {formatEV(ticket.real_ev)}
            </span>
            <p className="mt-0.5 text-[10px] font-mono uppercase tracking-widest text-muted-foreground">EV real del parlay</p>
          </div>
        </div>
        <p className="text-xs text-subtle">{ticket.legs.length} selección{ticket.legs.length === 1 ? '' : 'es'} · {ticket.legs[0]?.league ?? ''}</p>
      </div>

      <ul className="flex flex-1 list-none flex-col px-4 pb-3">
        {ticket.legs.map((leg, index) => (
          <TicketLegRow key={`${leg.match_id}-${leg.market_name}-${index}`} leg={leg} index={index} />
        ))}
      </ul>
    </article>
  )
}

export function ResultsPage() {
  const [selectedDate, setSelectedDate] = React.useState<string>(() => cotDateString(0))
  const [data, setData] = React.useState<PublicResultsResponse | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState(false)
  const [retryKey, setRetryKey] = React.useState(0)

  const days = React.useMemo(
    () => Array.from({ length: 7 }, (_, offset) => ({
      value: cotDateString(offset),
      label: offset === 0 ? 'Hoy' : dayTitle(offset),
    })),
    [],
  )

  React.useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(false)
      const result = await fetchPublicResults(selectedDate)
      if (cancelled) return
      if (result.ok) {
        setData(result.data)
      } else {
        setData(null)
        setError(true)
      }
      setLoading(false)
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [selectedDate, retryKey])

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Confianza pública</p>
            <h1 className="mt-2 flex items-center gap-2 text-2xl font-bold tracking-tight text-foreground">
              <Trophy className="size-6 text-primary" aria-hidden="true" />
              Resultados
            </h1>
            <p className="mt-1 text-sm text-subtle">
              Boletos destacados del sistema con su récord real, sin curar: los perdidos se muestran igual que los ganados.
            </p>
          </div>
        </header>

        {data && <SummaryStrip data={data} />}

        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-subtle">Día</span>
          {days.map((day) => (
            <button
              key={day.value}
              type="button"
              aria-pressed={selectedDate === day.value}
              onClick={() => setSelectedDate(day.value)}
              className={cn(
                'rounded-lg border px-3 py-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60',
                selectedDate === day.value
                  ? 'border-border/70 bg-surface-raised text-foreground shadow-sm'
                  : 'border-border bg-surface/70 text-muted-foreground hover:text-foreground',
              )}
            >
              {day.label}
            </button>
          ))}
        </div>

        {loading ? (
          <div aria-busy="true" className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {[0, 1, 2].map((item) => (
              <div key={item} className="flex h-72 flex-col rounded-xl border border-border bg-card p-4">
                <div className="h-6 w-32 rounded skeleton" />
                <div className="mt-5 h-10 w-24 self-end rounded skeleton" />
                <div className="mt-6 h-4 w-48 rounded skeleton" />
                <div className="mt-3 h-4 w-40 rounded skeleton" />
                <div className="mt-auto h-8 rounded-lg skeleton" />
              </div>
            ))}
          </div>
        ) : error ? (
          <RouteError label="los resultados" onRetry={() => setRetryKey((key) => key + 1)} />
        ) : data && data.tickets.length > 0 ? (
          <div className="grid items-start gap-4 md:grid-cols-2 xl:grid-cols-3">
            {data.tickets.map((ticket) => (
              <FeaturedTicketCard key={ticket.id} ticket={ticket} />
            ))}
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/60 px-6 py-12 text-center">
            <Trophy className="size-6 text-subtle" aria-hidden="true" />
            <h2 className="mt-4 text-base font-semibold text-foreground">No hubo boletos destacados ese día</h2>
            <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">
              El generador del sistema no encontró oportunidades +EV ese día. Probá con otro día de la semana.
            </p>
          </div>
        )}

        <StatDisclaimer />
      </div>
    </AppShell>
  )
}