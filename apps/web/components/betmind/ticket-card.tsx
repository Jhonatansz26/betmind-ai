'use client'

import { toast } from 'sonner'
import { StarIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { MODE_META, type Ticket } from '@/lib/betmind'
import { cn } from '@/lib/utils'
import { TicketLeg } from './ticket-leg'
import { addToTracking } from './tracking-panel'

export function TicketCard({ ticket, onTrack }: { ticket: Ticket; onTrack?: (ticket: Ticket) => void }) {
  const meta = MODE_META[ticket.mode]

  async function handleTrack() {
    await addToTracking(ticket)
    onTrack?.(ticket)
    toast('Añadido a seguimiento', {
      description: `${ticket.legs.length} selecciones en seguimiento.`,
    })
  }

  return (
    <div className="flex h-full flex-col rounded-xl border border-border bg-card ring-1 ring-white/5">
      {/* Mode accent strip — top 3px bar */}
      <div className={cn('h-[3px] w-full shrink-0 rounded-t-xl', meta.accent)} aria-hidden />

      {/* ── HEADER — mode badge + combined odds ── */}
      <div className="flex flex-col gap-3 p-4 pb-1">
        {/* Row 1: mode badge + combined odds */}
        <div className="flex items-center justify-between gap-3">
          <span
            className={cn(
              'inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-semibold tracking-wide',
              meta.border,
              meta.bg,
              meta.text,
            )}
          >
            <span aria-hidden>{meta.glyph}</span>
            {meta.label}
          </span>

          <div className="flex flex-col items-end">
            <span className="font-mono text-4xl font-bold tabular-nums tracking-tight leading-none text-foreground">
              {ticket.combinedOdds.toFixed(2)}
            </span>
            <span className="mt-0.5 text-[10px] font-mono uppercase tracking-widest text-muted-foreground">
              Cuota Combinada
            </span>
          </div>
        </div>

        <div className="my-2 flex items-center justify-between divide-x divide-border/50 rounded-lg border border-border/60 bg-surface/30 px-4 py-2 text-xs">
          <div className="flex flex-col gap-0.5 pr-3">
            <span className="text-[9px] font-bold uppercase tracking-widest text-subtle">Confianza IA</span>
            <span className="font-mono font-bold tabular-nums text-foreground">{ticket.confidence}%</span>
          </div>
          <div className="flex flex-col gap-0.5 px-3">
            <span className="text-[9px] font-bold uppercase tracking-widest text-subtle">+EV Promedio</span>
            <span className="font-mono font-bold tabular-nums text-positive">+{(ticket.evAverage * 100).toFixed(1)}%</span>
          </div>
          <div className="flex flex-col gap-0.5 pl-3">
            <span className="text-[9px] font-bold uppercase tracking-widest text-subtle">Rango</span>
            <span className="flex items-center gap-1 text-xs font-bold text-positive">
              <span className="size-1.5 rounded-full bg-positive" aria-hidden />
              En rango
            </span>
          </div>
        </div>
      </div>

      <div className="mx-4 mb-3 rounded-lg border border-primary/15 bg-primary/[0.06] px-3 py-2.5">
        <p className="text-[10px] font-bold uppercase tracking-widest text-primary">Por qué esta selección</p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {ticket.rationale.map((item) => (
            <span key={item} className="rounded-md border border-border/60 bg-surface/60 px-2 py-1 text-[10px] font-medium text-muted-foreground">
              {item}
            </span>
          ))}
        </div>
        <p className="mt-2 text-[10px] leading-relaxed text-subtle" title={ticket.correlation}>
          Seguridad del motor: {ticket.correlation}
        </p>
      </div>

      {/* ── LEGS — fills remaining vertical space ── */}
      <ul className="flex flex-1 list-none flex-col px-4 pb-4">
        {ticket.legs.map((leg, i) => (
          <TicketLeg key={`${leg.match}-${leg.market}`} leg={leg} index={i} />
        ))}
      </ul>

      {/* ── FOOTER — pinned to bottom ── */}
      <div className="mt-auto flex flex-col gap-2 border-t border-border/40 px-4 py-3">
        <Button variant="outline" size="sm" className="w-full" onClick={handleTrack}>
          <StarIcon data-icon="inline-start" aria-hidden="true" />
          Añadir a Seguimiento
        </Button>
        <p className="text-[10px] leading-tight text-subtle">
          Confianza basada en datos de 90 min. No es asesoría financiera.
        </p>
      </div>
    </div>
  )
}
