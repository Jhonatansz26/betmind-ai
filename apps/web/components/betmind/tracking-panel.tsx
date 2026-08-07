'use client'

import * as React from 'react'
import { Trash2Icon } from 'lucide-react'
import { toast } from 'sonner'

import { type Mode, type Ticket } from '@/lib/betmind'
import {
  fetchTicketHistory,
  claimAnonymousTickets,
  saveTicket,
  updateTicketStatus,
  type SavedTicketStatus,
} from '@/lib/api'
import { cn } from '@/lib/utils'
import { formatEV, formatOdds, formatCOTDate } from '@/lib/formatters'

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

export type TrackStatus = SavedTicketStatus

export interface TrackedTicket {
  id: string
  mode: Mode
  combinedOdds: number
  evAverage: number
  confidence: number
  legsCount: number
  trackedAt: string // ISO string
  status: TrackStatus
  remote?: boolean
}

/* ------------------------------------------------------------------ */
/* Storage helpers                                                     */
/* ------------------------------------------------------------------ */

const STORAGE_KEY = 'betmind_tracked_tickets'

function loadTracked(): TrackedTicket[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    const parsed = raw ? (JSON.parse(raw) as TrackedTicket[]) : []
    return parsed.map((ticket) => ({ ...ticket, evAverage: ticket.evAverage ?? 0 }))
  } catch {
    return []
  }
}

function saveTracked(tickets: TrackedTicket[]) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(tickets))
  } catch {
    // quota exceeded — silently fail
  }
}

export async function claimPendingTickets(): Promise<number> {
  const pending = loadTracked().filter((ticket) => ticket.remote && /^\d+$/.test(ticket.id))
  const ticketIds = pending.map((ticket) => Number(ticket.id))
  if (!ticketIds.length) return 0

  const result = await claimAnonymousTickets(ticketIds)
  if (!result.ok || result.data.claimed_count <= 0) return 0

  const pendingIds = new Set(ticketIds.map(String))
  saveTracked(loadTracked().filter((ticket) => !pendingIds.has(ticket.id)))
  return result.data.claimed_count
}

export async function addToTracking(ticket: Ticket): Promise<void> {
  const remoteResult = await saveTicket(ticket)
  if (remoteResult.ok) {
    const existing = loadTracked()
    const entry: TrackedTicket = {
      id: String(remoteResult.data.id),
      mode: ticket.mode,
      combinedOdds: remoteResult.data.total_odds,
      evAverage: remoteResult.data.total_ev,
      confidence: ticket.confidence,
      legsCount: ticket.legs.length,
      trackedAt: remoteResult.data.created_at,
      status: remoteResult.data.status,
      remote: true,
    }
    saveTracked([entry, ...existing.filter((item) => item.id !== entry.id)].slice(0, 10))
    return
  }

  const existing = loadTracked()
  const entryId = `${ticket.mode}-${Date.now()}`
  const entry: TrackedTicket = {
    id: entryId,
    mode: ticket.mode,
    combinedOdds: ticket.combinedOdds,
    evAverage: ticket.evAverage,
    confidence: ticket.confidence,
    legsCount: ticket.legs.length,
    trackedAt: new Date().toISOString(),
    status: 'PENDING',
    remote: false,
  }
  const updated = [entry, ...existing].slice(0, 10)
  saveTracked(updated)
}

/* ------------------------------------------------------------------ */
/* Status config                                                       */
/* ------------------------------------------------------------------ */

const STATUS_CONFIG: Record<
  TrackStatus,
  { label: string; className: string }
> = {
  PENDING: {
    label: 'PENDING',
    className: 'border-warning/40 bg-warning/10 text-warning',
  },
  WON: {
    label: 'WON',
    className: 'border-positive/40 bg-positive/10 text-positive',
  },
  LOST: {
    label: 'LOST',
    className: 'border-negative/40 bg-negative/10 text-negative',
  },
  VOID: {
    label: 'VOID',
    className: 'border-border bg-surface text-muted-foreground',
  },
}

/* ------------------------------------------------------------------ */
/* Row component                                                       */
/* ------------------------------------------------------------------ */

function TrackRow({
  entry,
  onStatusChange,
  onRemove,
}: {
  entry: TrackedTicket
  onStatusChange: (id: string, status: TrackStatus) => void
  onRemove: (id: string) => void
}) {
  const statusCfg = STATUS_CONFIG[entry.status]
  const date = formatCOTDate(entry.trackedAt)

  const nextStatus: Record<TrackStatus, TrackStatus> = {
    PENDING: 'WON',
    WON: 'LOST',
    LOST: 'VOID',
    VOID: 'PENDING',
  }

  return (
    <li className="flex items-center justify-between gap-4 border-b border-border/40 px-4 py-3 text-xs transition-colors hover:bg-surface/40 last:border-b-0">
      <div className="flex min-w-0 items-center gap-2">
        <span className="shrink-0 rounded border border-border/60 bg-surface px-1.5 py-0.5 font-mono text-[10px] font-bold uppercase text-foreground">{entry.mode}</span>
        <div className="min-w-0">
          <p className="truncate font-mono text-xs text-muted-foreground">{entry.legsCount} selecciones</p>
          <p className="truncate font-mono text-[10px] tabular-nums text-muted-foreground">{date}</p>
        </div>
      </div>

      <div className="flex shrink-0 items-center gap-4">
        <div className="text-right">
          <p className="font-mono text-sm font-bold tabular-nums text-foreground">{formatOdds(entry.combinedOdds)}</p>
          <p className="font-mono text-xs font-semibold tabular-nums text-positive">{formatEV(entry.evAverage)} EV</p>
        </div>
        <button
          type="button"
          title="Cambiar estado"
          onClick={() => onStatusChange(entry.id, nextStatus[entry.status])}
          className={cn(
            'inline-flex shrink-0 cursor-pointer rounded border px-2 py-1 font-mono text-[10px] font-bold uppercase tabular-nums transition-opacity hover:opacity-80',
            statusCfg.className,
          )}
        >
          {statusCfg.label}
        </button>

        <button
          type="button"
          title="Eliminar de seguimiento"
          onClick={() => onRemove(entry.id)}
          className="shrink-0 text-subtle transition-colors hover:text-negative"
        >
          <Trash2Icon className="size-3.5" aria-hidden />
        </button>
      </div>
    </li>
  )
}

/* ------------------------------------------------------------------ */
/* Main panel                                                          */
/* ------------------------------------------------------------------ */

export function TrackingPanel({ refreshKey }: { refreshKey?: number }) {
  const [entries, setEntries] = React.useState<TrackedTicket[]>([])

  React.useEffect(() => {
    let cancelled = false
    async function loadHistory() {
      await claimPendingTickets()
      const result = await fetchTicketHistory()
      if (cancelled) return
      if (result.ok) {
        setEntries(result.data.map((saved) => {
          const mode = saved.ticket_data.mode
          return {
            id: String(saved.id),
            mode,
            combinedOdds: saved.total_odds,
            evAverage: saved.total_ev,
            confidence: saved.ticket_data.confidence,
            legsCount: saved.ticket_data.legs.length,
            trackedAt: saved.created_at,
            status: saved.status,
            remote: true,
          }
        }))
      } else {
        setEntries(loadTracked())
      }
    }
    void loadHistory()
    const resync = () => { void loadHistory() }
    window.addEventListener('storage', resync)
    window.addEventListener('betmind:auth-changed', resync)
    document.addEventListener('visibilitychange', resync)
    const interval = window.setInterval(resync, 30_000)
    return () => {
      cancelled = true
      window.removeEventListener('storage', resync)
      window.removeEventListener('betmind:auth-changed', resync)
      document.removeEventListener('visibilitychange', resync)
      window.clearInterval(interval)
    }
  }, [refreshKey])

  async function handleStatusChange(id: string, status: TrackStatus) {
    const current = entries.find((entry) => entry.id === id)
    const next = entries.map((entry) => (entry.id === id ? { ...entry, status } : entry))
    setEntries(next)
    if (current?.remote && /^\d+$/.test(id)) {
      const result = await updateTicketStatus(Number(id), status)
      if (!result.ok) saveTracked(next)
    } else {
      saveTracked(next)
    }
  }

  function handleRemove(id: string) {
    setEntries((prev) => {
      const next = prev.filter((e) => e.id !== id)
      saveTracked(next)
      return next
    })
    toast('Boleto eliminado del seguimiento')
  }

  const averageOdds = entries.length
    ? entries.reduce((sum, entry) => sum + entry.combinedOdds, 0) / entries.length
    : 0
  const averageEv = entries.length
    ? entries.reduce((sum, entry) => sum + entry.evAverage, 0) / entries.length
    : 0
  const pending = entries.filter((e) => e.status === 'PENDING').length

  return (
    <div className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4">
      <div className="grid grid-cols-2 divide-x divide-y divide-border/50 rounded-lg border border-border/60 bg-surface/30 px-4 py-3 text-xs sm:grid-cols-4 sm:divide-y-0">
        <div className="pr-3"><span className="block text-[9px] font-mono font-bold uppercase tracking-wider text-muted-foreground">Boletos guardados</span><span className="font-mono text-sm font-bold tabular-nums text-foreground">{entries.length}</span></div>
        <div className="px-3"><span className="block text-[9px] font-mono font-bold uppercase tracking-wider text-muted-foreground">Cuota promedio</span><span className="font-mono text-sm font-bold tabular-nums text-foreground">{formatOdds(averageOdds)}</span></div>
        <div className="px-3"><span className="block text-[9px] font-mono font-bold uppercase tracking-wider text-muted-foreground">+EV medio</span><span className="font-mono text-sm font-bold tabular-nums text-positive">{formatEV(averageEv)}</span></div>
        <div className="pl-3"><span className="block text-[9px] font-mono font-bold uppercase tracking-wider text-muted-foreground">En seguimiento</span><span className="font-mono text-sm font-bold tabular-nums text-foreground">{pending}</span></div>
      </div>

      <div className="flex items-center justify-between gap-3 rounded-lg border border-primary/25 bg-primary/[0.04] px-4 py-2.5 text-xs">
        <p className="font-mono text-xs font-medium text-foreground">MODO ANÓNIMO ACTIVO • Sincroniza tu Track Record en la nube y activa gestión de bankroll PRO</p>
        <button type="button" onClick={() => toast('Cuenta PRO', { description: 'La conexión de cuenta estará disponible próximamente.' })} className="shrink-0 rounded-md border border-primary/40 bg-primary/10 px-3 py-1 text-[11px] font-semibold text-primary transition-colors hover:bg-primary/20">Conectar Cuenta PRO</button>
      </div>

      <div className="flex items-center justify-between gap-3 border-b border-border/50 px-1 pb-2">
        <h2 className="text-sm font-semibold text-foreground">Ledger de seguimiento</h2>
        <span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">{entries.length ? 'Historial cargado' : 'Sin registros'}</span>
      </div>

      {entries.length > 0 ? (
        <ul className="-mx-4">
          {entries.map((entry) => (
            <TrackRow
              key={entry.id}
              entry={entry}
              onStatusChange={handleStatusChange}
              onRemove={handleRemove}
            />
          ))}
        </ul>
      ) : (
        <div className="px-4 py-6 text-center">
          <p className="text-sm font-medium text-foreground">Sin boletos en seguimiento</p>
          <p className="mt-1 text-xs text-muted-foreground">Pulsa Seguir en cualquier boleto para agregarlo aquí.</p>
        </div>
      )}

      <p className="border-t border-border/40 px-1 pt-2.5 text-[10px] text-muted-foreground">
        Historial sincronizado · Se usa almacenamiento local solo si la API no responde
      </p>
    </div>
  )
}
