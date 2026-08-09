'use client'

import * as React from 'react'
import { SlidersHorizontal, Sparkles } from 'lucide-react'
import Link from 'next/link'

import { type Ticket } from '@/lib/betmind'
import { fetchTickets } from '@/lib/api'
import { cn } from '@/lib/utils'

import { AppShell } from './app-shell'
import { DateSelector, formatDateTitle, type DateFilter } from './date-selector'
import { RouteError } from './route-states'
import { StatDisclaimer } from './stat-disclaimer'
import { TicketCard } from './ticket-card'

function formatAge(value?: string | null) {
  if (!value) return 'Actualizando datos…'
  const minutes = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 60000))
  return minutes < 1 ? 'Actualizado ahora' : `Actualizado hace ${minutes} min`
}

function TicketLoadingGrid() {
  return (
    <div aria-busy="true" className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      <span className="sr-only">Cargando señales…</span>
      {[0, 1, 2].map((item) => (
        <div key={item} className="flex h-[28rem] flex-col rounded-xl border border-border bg-card p-4">
          <div className="h-6 w-24 rounded-md skeleton" />
          <div className="mt-5 h-12 w-32 self-end rounded skeleton" />
          <div className="mt-8 h-4 w-48 rounded skeleton" />
          <div className="mt-3 h-20 rounded-lg skeleton" />
          <div className="mt-auto h-10 rounded skeleton" />
        </div>
      ))}
    </div>
  )
}

function EmptySignals({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/60 px-6 py-12 text-center">
      <div className="mb-4 flex size-11 items-center justify-center rounded-xl border border-primary/20 bg-primary/10 text-primary"><Sparkles size={18} aria-hidden="true" /></div>
      <h2 className="text-base font-semibold text-foreground">Todavía no hay una señal con valor</h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">El modelo revisa las cuotas y solo muestra boletos cuando encuentra una ventaja medible.</p>
      <button type="button" onClick={onRetry} className="mt-6 inline-flex min-h-11 items-center rounded-lg border border-border bg-surface px-4 text-sm font-semibold text-foreground hover:bg-surface-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">Actualizar ahora</button>
    </div>
  )
}

export function SignalsPage() {
  const [dateFilter, setDateFilter] = React.useState<DateFilter>('today')
  const [tickets, setTickets] = React.useState<Ticket[]>([])
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState(false)
  const [retryKey, setRetryKey] = React.useState(0)
  const [meta, setMeta] = React.useState<{ totalEv: number; generatedAt: string } | null>(null)

  React.useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      setError(false)
      const result = await fetchTickets(['EDGE', 'VALUE', 'BOLD'], undefined, dateFilter === 'all' ? undefined : dateFilter)
      if (cancelled) return
      if (result.ok) {
        setTickets(result.data.tickets)
        setMeta({ totalEv: result.data.totalEvOpportunities, generatedAt: result.data.generatedAt })
      } else {
        setTickets([])
        setMeta(null)
        setError(true)
      }
      setLoading(false)
    }
    void load()
    return () => { cancelled = true }
  }, [dateFilter, retryKey])

  const dateInfo = React.useMemo(() => formatDateTitle(dateFilter, new Date()), [dateFilter])

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <section className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Signal desk</p>
            <h1 className="mt-2 text-2xl font-bold tracking-tight text-foreground">Oportunidades de {dateInfo.title.toLowerCase()}</h1>
            <p className="mt-1 text-sm text-subtle">{dateInfo.subtitle}</p>
          </div>
          <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto">
            <DateSelector value={dateFilter} onChange={setDateFilter} />
            <Link href="/generador" className="inline-flex min-h-10 items-center gap-2 rounded-lg border border-border bg-surface px-3 text-xs font-semibold text-foreground transition-colors hover:bg-surface-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
              <SlidersHorizontal size={14} aria-hidden="true" /> Generador
            </Link>
          </div>
          <p className="w-full text-xs text-muted-foreground">{meta ? `${meta.totalEv} señales +EV · ${formatAge(meta.generatedAt)}` : 'Consultando modelo…'}</p>
        </section>

        {loading ? <TicketLoadingGrid /> : error ? <RouteError label="las señales" onRetry={() => setRetryKey((key) => key + 1)} /> : tickets.length > 0 ? (
          <div className={cn('grid items-stretch gap-4', tickets.length === 1 ? 'max-w-md' : tickets.length === 2 ? 'md:grid-cols-2 max-w-2xl' : 'md:grid-cols-2 xl:grid-cols-3')}>
            {tickets.map((ticket) => <TicketCard key={ticket.mode} ticket={ticket} />)}
          </div>
        ) : <EmptySignals onRetry={() => setRetryKey((key) => key + 1)} />}
        <StatDisclaimer />
      </div>
    </AppShell>
  )
}
