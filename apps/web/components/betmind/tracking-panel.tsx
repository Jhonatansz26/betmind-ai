'use client'

import * as React from 'react'
import { CheckCircle2Icon, CircleDotIcon, ClockIcon, XCircleIcon, Trash2Icon } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import { MODE_META, type Mode, type Ticket } from '@/lib/betmind'
import { cn } from '@/lib/utils'

/* ------------------------------------------------------------------ */
/* Types                                                               */
/* ------------------------------------------------------------------ */

export type TrackStatus = 'PENDING' | 'LIVE' | 'WON' | 'LOST'

export interface TrackedTicket {
  id: string
  mode: Mode
  combinedOdds: number
  confidence: number
  legsCount: number
  trackedAt: string // ISO string
  status: TrackStatus
}

/* ------------------------------------------------------------------ */
/* Storage helpers                                                     */
/* ------------------------------------------------------------------ */

const STORAGE_KEY = 'betmind_tracked_tickets'

function loadTracked(): TrackedTicket[] {
  if (typeof window === 'undefined') return []
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as TrackedTicket[]) : []
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

export function addToTracking(ticket: Ticket): void {
  const existing = loadTracked()
  const already = existing.some((t) => t.id === ticket.mode)
  if (already) return
  const entry: TrackedTicket = {
    id: ticket.mode,
    mode: ticket.mode,
    combinedOdds: ticket.combinedOdds,
    confidence: ticket.confidence,
    legsCount: ticket.legs.length,
    trackedAt: new Date().toISOString(),
    status: 'PENDING',
  }
  const updated = [entry, ...existing].slice(0, 10) // cap at 10
  saveTracked(updated)
}

/* ------------------------------------------------------------------ */
/* Status config                                                       */
/* ------------------------------------------------------------------ */

const STATUS_CONFIG: Record<
  TrackStatus,
  { label: string; icon: React.ReactNode; className: string }
> = {
  PENDING: {
    label: 'Pendiente',
    icon: <ClockIcon className="size-3.5" aria-hidden />,
    className: 'border-border bg-muted/60 text-muted-foreground',
  },
  LIVE: {
    label: 'En Juego',
    icon: <CircleDotIcon className="size-3.5" aria-hidden />,
    className: 'border-primary/40 bg-primary/10 text-primary',
  },
  WON: {
    label: 'Ganada',
    icon: <CheckCircle2Icon className="size-3.5" aria-hidden />,
    className: 'border-positive/40 bg-positive/10 text-positive',
  },
  LOST: {
    label: 'Perdida',
    icon: <XCircleIcon className="size-3.5" aria-hidden />,
    className: 'border-negative/40 bg-negative/10 text-negative',
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
  const meta = MODE_META[entry.mode]
  const statusCfg = STATUS_CONFIG[entry.status]
  const date = new Date(entry.trackedAt).toLocaleDateString('es-CO', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
  })

  const nextStatus: Record<TrackStatus, TrackStatus> = {
    PENDING: 'LIVE',
    LIVE: 'WON',
    WON: 'LOST',
    LOST: 'PENDING',
  }

  return (
    <li className="grid grid-cols-[auto_1fr_auto_auto] items-center gap-3 border-b border-border-subtle py-3 last:border-b-0">
      {/* Mode badge */}
      <span
        className={cn(
          'shrink-0 rounded border px-1.5 py-0.5 text-[10px] font-semibold tracking-wide',
          meta.border,
          meta.bg,
          meta.text,
        )}
      >
        {meta.glyph}
      </span>

      {/* Info */}
      <div className="min-w-0">
        <p className="text-sm font-medium text-foreground">
          {meta.label.replace('MODO ', '')}
          <span className="num ml-1.5 text-xs text-subtle">×{entry.combinedOdds.toFixed(2)}</span>
        </p>
        <p className="text-[10px] text-subtle">
          {entry.legsCount} selecciones · {date}
        </p>
      </div>

      {/* Status badge — click to cycle */}
      <button
        type="button"
        title="Cambiar estado"
        onClick={() => onStatusChange(entry.id, nextStatus[entry.status])}
        className={cn(
          'inline-flex shrink-0 items-center gap-1 rounded-sm border px-1.5 py-0.5 text-[10px] font-medium transition-colors hover:opacity-80',
          statusCfg.className,
        )}
      >
        {statusCfg.icon}
        {statusCfg.label}
      </button>

      {/* Remove */}
      <button
        type="button"
        title="Eliminar de seguimiento"
        onClick={() => onRemove(entry.id)}
        className="shrink-0 text-subtle transition-colors hover:text-negative"
      >
        <Trash2Icon className="size-3.5" aria-hidden />
      </button>
    </li>
  )
}

/* ------------------------------------------------------------------ */
/* Main panel                                                          */
/* ------------------------------------------------------------------ */

export function TrackingPanel({ refreshKey }: { refreshKey?: number }) {
  const [entries, setEntries] = React.useState<TrackedTicket[]>([])

  // Load from localStorage on mount + whenever refreshKey changes (ticket added externally)
  React.useEffect(() => {
    setEntries(loadTracked())
  }, [refreshKey])

  function handleStatusChange(id: string, status: TrackStatus) {
    setEntries((prev) => {
      const next = prev.map((e) => (e.id === id ? { ...e, status } : e))
      saveTracked(next)
      return next
    })
  }

  function handleRemove(id: string) {
    setEntries((prev) => {
      const next = prev.filter((e) => e.id !== id)
      saveTracked(next)
      return next
    })
    toast('Boleto eliminado del seguimiento')
  }

  if (entries.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-card p-5 text-center">
        <p className="text-sm font-medium text-foreground">Sin boletos en seguimiento</p>
        <p className="mt-1 text-xs text-subtle">
          Pulsa <span className="font-semibold text-foreground">Seguir</span> en cualquier boleto para
          agregarlo aquí.
        </p>
      </div>
    )
  }

  const won = entries.filter((e) => e.status === 'WON').length
  const lost = entries.filter((e) => e.status === 'LOST').length
  const pending = entries.filter((e) => e.status === 'PENDING' || e.status === 'LIVE').length

  return (
    <div className="rounded-xl border border-border bg-card">
      {/* Panel header */}
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <h2 className="text-sm font-semibold text-foreground">Seguimiento</h2>
        <div className="flex items-center gap-3 text-[11px]">
          <span className="num text-subtle">{pending} pendiente{pending !== 1 ? 's' : ''}</span>
          {won > 0 && <span className="num text-positive">✓ {won} ganado{won !== 1 ? 's' : ''}</span>}
          {lost > 0 && <span className="num text-negative">✗ {lost} perdido{lost !== 1 ? 's' : ''}</span>}
        </div>
      </div>

      {/* Rows */}
      <ul className="px-4">
        {entries.map((entry) => (
          <TrackRow
            key={entry.id}
            entry={entry}
            onStatusChange={handleStatusChange}
            onRemove={handleRemove}
          />
        ))}
      </ul>

      <p className="border-t border-border-subtle px-4 py-2.5 text-[10px] text-subtle">
        Estado local · Los datos se guardan en este navegador
      </p>
    </div>
  )
}
