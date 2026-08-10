'use client'

import * as React from 'react'
import { ChevronLeft, ChevronRight, Trash2 } from 'lucide-react'
import Link from 'next/link'
import { usePathname, useRouter, useSearchParams } from 'next/navigation'
import { toast } from 'sonner'

import { updateTicketStatus } from '@/lib/api'
import { formatCOP, formatCOTDate, formatEV, formatOdds } from '@/lib/formatters'
import { saveTrackedTickets, summarizeTrackedTickets, type TrackStatus } from '@/lib/tracking'
import { cn } from '@/lib/utils'
import { useAuthSession } from '@/lib/hooks/use-auth-session'
import { invalidateBankroll } from '@/lib/hooks/use-bankroll'

import { AppShell } from './app-shell'
import { StatDisclaimer } from './stat-disclaimer'
import { useTicketHistory } from './use-ticket-history'

const PAGE_SIZE = 10
const MODES = ['ALL', 'EDGE', 'VALUE', 'BOLD'] as const
const STATUSES = ['ALL', 'PENDING', 'WON', 'LOST', 'VOID'] as const

function FilterSelect({ label, value, options, onChange }: { label: string; value: string; options: readonly string[]; onChange: (value: string) => void }) {
  return (
    <label className="flex items-center gap-2 rounded-lg border border-border bg-surface/70 px-3 py-2 text-xs text-muted-foreground">
      <span className="font-semibold">{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)} className="bg-transparent font-mono text-xs font-semibold text-foreground outline-none">
        {options.map((option) => <option key={option} value={option}>{option === 'ALL' ? 'Todos' : option}</option>)}
      </select>
    </label>
  )
}

export function HistoryPage() {
  const router = useRouter()
  const pathname = usePathname()
  const searchParams = useSearchParams()
  const rawStatusFilter = (searchParams.get('estado') ?? 'ALL').toUpperCase()
  const rawModeFilter = (searchParams.get('modo') ?? 'ALL').toUpperCase()
  const statusFilter = STATUSES.includes(rawStatusFilter as typeof STATUSES[number]) ? rawStatusFilter : 'ALL'
  const modeFilter = MODES.includes(rawModeFilter as typeof MODES[number]) ? rawModeFilter : 'ALL'
  const page = Math.max(1, Number(searchParams.get('page') ?? '1') || 1)
  const { isAuthenticated, isLoading: authLoading } = useAuthSession()
  const { entries, setEntries, loading, error, reload } = useTicketHistory(isAuthenticated, authLoading)

  function updateQuery(changes: { estado?: string; modo?: string; page?: number }) {
    const next = new URLSearchParams(searchParams.toString())
    if (changes.estado !== undefined) changes.estado === 'ALL' ? next.delete('estado') : next.set('estado', changes.estado)
    if (changes.modo !== undefined) changes.modo === 'ALL' ? next.delete('modo') : next.set('modo', changes.modo)
    if (changes.page !== undefined) changes.page <= 1 ? next.delete('page') : next.set('page', String(changes.page))
    const query = next.toString()
    router.replace(query ? `${pathname}?${query}` : pathname)
  }

  const filteredEntries = React.useMemo(() => entries.filter((entry) => (statusFilter === 'ALL' || entry.status === statusFilter) && (modeFilter === 'ALL' || entry.mode === modeFilter)), [entries, modeFilter, statusFilter])
  const totalPages = Math.max(1, Math.ceil(filteredEntries.length / PAGE_SIZE))
  const currentPage = Math.min(page, totalPages)
  const visibleEntries = filteredEntries.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)
  const summary = React.useMemo(() => summarizeTrackedTickets(entries), [entries])
  const roiLabel = summary.roiApprox == null ? 'No disponible' : `${summary.roiApprox >= 0 ? '+' : ''}${summary.roiApprox.toFixed(1)}%`

  async function changeStatus(id: string, status: TrackStatus) {
    const current = entries.find((entry) => entry.id === id)
    const next = entries.map((entry) => entry.id === id ? { ...entry, status } : entry)
    setEntries(next)
    if (isAuthenticated && current?.remote && /^\d+$/.test(id)) {
      const result = await updateTicketStatus(Number(id), status)
      if (!result.ok) {
        if (current) setEntries(entries.map((entry) => entry.id === id ? current : entry))
        if (result.error.code === 'HTTP_409') {
          toast.error('Este boleto ya fue liquidado y no se puede cambiar de estado. Si fue un error, ajustá tu bankroll manualmente desde /bankroll.')
        } else {
          toast.error(result.error.message)
        }
        return
      }
      const movement = result.data.bankroll_movement
      if (movement) {
        if (movement.amount > 0) toast.success(`Tu bankroll subió ${formatCOP(movement.amount)}`)
        else if (movement.amount < 0) toast.success(`Tu bankroll bajó ${formatCOP(Math.abs(movement.amount))}`)
        else toast.success('Tu bankroll no cambió: boleto anulado.')
        void invalidateBankroll()
      }
    } else {
      saveTrackedTickets(next)
    }
  }

  function removeEntry(id: string) {
    const next = entries.filter((entry) => entry.id !== id)
    setEntries(next)
    saveTrackedTickets(next)
    toast('Boleto eliminado del seguimiento')
  }

  const statusConfig: Record<TrackStatus, string> = {
    PENDING: 'border-warning/40 bg-warning/10 text-warning',
    WON: 'border-positive/40 bg-positive/10 text-positive',
    LOST: 'border-negative/40 bg-negative/10 text-negative',
    VOID: 'border-border bg-surface text-muted-foreground',
  }

  if (!loading && error) {
    return (
      <AppShell>
        <div className="mx-auto flex min-h-[70vh] max-w-xl flex-col items-center justify-center text-center">
          <h1 className="text-xl font-semibold text-foreground">No pudimos cargar tu historial</h1>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">{error}</p>
          <button type="button" onClick={reload} className="mt-6 inline-flex min-h-11 items-center rounded-xl border border-border bg-surface px-5 text-sm font-semibold text-foreground hover:bg-surface-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">Reintentar</button>
        </div>
      </AppShell>
    )
  }

  if (!loading && entries.length === 0) {
    return (
      <AppShell>
        <div className="mx-auto flex min-h-[70vh] max-w-xl flex-col items-center justify-center text-center">
          <div className="flex size-14 items-center justify-center rounded-2xl border border-primary/20 bg-primary/10 text-primary">⌁</div>
          <h1 className="mt-5 text-2xl font-bold tracking-tight text-foreground">Tu historial está vacío</h1>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">Cuando guardes tu primer boleto, aquí verás tu track record.</p>
          <Link href="/generador" className="mt-6 inline-flex min-h-11 items-center rounded-xl bg-primary px-5 text-sm font-semibold text-primary-foreground hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">Generar mi primer boleto</Link>
        </div>
      </AppShell>
    )
  }

  return (
    <AppShell>
      <div className="flex flex-col gap-6">
        <header className="flex flex-wrap items-end justify-between gap-4">
          <div><p className="text-xs font-semibold uppercase tracking-[0.2em] text-primary">Ledger</p><h1 className="mt-2 text-2xl font-bold tracking-tight text-foreground">Historial</h1><p className="mt-1 text-sm text-subtle">Tu track record de boletos guardados.</p></div>
          <Link href="/generador" className="inline-flex min-h-10 items-center rounded-lg border border-border bg-surface px-3 text-xs font-semibold text-foreground hover:bg-surface-raised focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">Generar boleto</Link>
        </header>

        <section aria-label="Métricas del historial" className="grid grid-cols-2 gap-3 md:grid-cols-5">
          {[
            ['Ganados', summary.won, 'text-positive'],
            ['Perdidos', summary.lost, 'text-negative'],
            ['Pendientes', summary.active, 'text-warning'],
            ['Racha actual', summary.streakCount ? `${summary.streakCount} ${summary.streakStatus === 'WON' ? 'ganadas' : 'perdidas'}` : '—', 'text-foreground'],
            ['ROI', roiLabel, summary.roiApprox == null ? 'text-muted-foreground' : summary.roiApprox >= 0 ? 'text-positive' : 'text-negative'],
          ].map(([label, value, color]) => <div key={label} className="rounded-2xl border border-border bg-card p-4"><p className="text-[10px] font-semibold uppercase tracking-wider text-subtle">{label}</p><p className={cn('mt-2 font-mono text-xl font-bold tabular-nums', color)}>{value}</p></div>)}
        </section>
        {summary.roiApprox != null && summary.roiTicketCount < summary.total && <p className="-mt-3 text-[11px] text-subtle">Calculado sobre {summary.roiTicketCount} de {summary.total} boletos con seguimiento de bankroll.</p>}
        <StatDisclaimer />

        <div className="flex flex-wrap items-center gap-2">
          <FilterSelect label="Estado" value={STATUSES.includes(statusFilter as typeof STATUSES[number]) ? statusFilter : 'ALL'} options={STATUSES} onChange={(value) => updateQuery({ estado: value, page: 1 })} />
          <FilterSelect label="Modo" value={MODES.includes(modeFilter as typeof MODES[number]) ? modeFilter : 'ALL'} options={MODES} onChange={(value) => updateQuery({ modo: value, page: 1 })} />
          <span className="ml-auto text-xs text-subtle">{filteredEntries.length} boleto{filteredEntries.length === 1 ? '' : 's'}</span>
        </div>

         {loading ? <div aria-busy="true" className="h-64 rounded-2xl border border-border bg-card skeleton" /> : visibleEntries.length > 0 ? <div className="overflow-hidden rounded-2xl border border-border bg-card"><ul>{visibleEntries.map((entry) => <li key={entry.id} className="flex flex-wrap items-center justify-between gap-4 border-b border-border/40 px-4 py-4 last:border-b-0"><div className="flex min-w-0 items-center gap-3"><span className="rounded border border-border/60 bg-surface px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase text-foreground">{entry.mode}</span><div><p className="text-sm font-medium text-foreground">{entry.legsCount} selecciones · cuota {formatOdds(entry.combinedOdds)}</p><p className="mt-1 text-xs text-subtle">{formatCOTDate(entry.trackedAt)} · {entry.confidence}% confianza</p></div></div><div className="flex flex-wrap items-center justify-end gap-3"><span className="font-mono text-[11px] tabular-nums text-subtle">Stake: {entry.stakeAmount != null ? formatCOP(entry.stakeAmount) : '—'}</span><span className="font-mono text-sm font-semibold text-positive">{formatEV(entry.evAverage)} EV</span><select value={entry.status} onChange={(event) => void changeStatus(entry.id, event.target.value as TrackStatus)} className={cn('rounded border px-2 py-1 font-mono text-[10px] font-bold uppercase outline-none', statusConfig[entry.status])}>{STATUSES.filter((status) => status !== 'ALL').map((status) => <option key={status} value={status}>{status}</option>)}</select><button type="button" onClick={() => removeEntry(entry.id)} aria-label="Eliminar boleto" className="text-subtle hover:text-negative"><Trash2 size={15} aria-hidden="true" /></button></div></li>)}</ul></div> : <div className="rounded-2xl border border-dashed border-border p-10 text-center text-sm text-muted-foreground">No hay boletos con estos filtros.</div>}

        {totalPages > 1 && <nav aria-label="Paginación del historial" className="flex items-center justify-center gap-3"><button type="button" disabled={currentPage <= 1} onClick={() => updateQuery({ page: currentPage - 1 })} className="inline-flex size-9 items-center justify-center rounded-lg border border-border disabled:opacity-40"><ChevronLeft size={16} aria-hidden="true" /></button><span className="font-mono text-xs text-muted-foreground">Página {currentPage} de {totalPages}</span><button type="button" disabled={currentPage >= totalPages} onClick={() => updateQuery({ page: currentPage + 1 })} className="inline-flex size-9 items-center justify-center rounded-lg border border-border disabled:opacity-40"><ChevronRight size={16} aria-hidden="true" /></button></nav>}
      </div>
    </AppShell>
  )
}
