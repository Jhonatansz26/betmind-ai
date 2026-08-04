'use client'

import { toast } from 'sonner'
import { StarIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { MODE_META, type Ticket } from '@/lib/betmind'
import { cn } from '@/lib/utils'
import { ConfidenceBar } from './confidence-bar'
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

          {/* Combined odds — @ X.XX format */}
          <span className="num font-mono text-2xl font-bold tracking-tight text-foreground">
            @ {ticket.combinedOdds.toFixed(2)}
          </span>
        </div>

        {/* Row 2: confidence bar */}
        <ConfidenceBar score={ticket.confidence} />

        {/* Row 3: EV average */}
        <span className="num text-xs font-semibold text-positive">
          +EV {(ticket.evAverage * 100).toFixed(1)}% promedio
        </span>
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
      <ul className="flex flex-1 list-none flex-col gap-2 px-4 pb-4">
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
