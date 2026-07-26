'use client'

import { toast } from 'sonner'
import { StarIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card'
import { MODE_META, type Ticket } from '@/lib/betmind'
import { cn } from '@/lib/utils'
import { ConfidenceBar } from './confidence-bar'
import { TicketLeg } from './ticket-leg'
import { addToTracking } from './tracking-panel'

export function TicketCard({ ticket, onTrack }: { ticket: Ticket; onTrack?: (ticket: Ticket) => void }) {
  const meta = MODE_META[ticket.mode]

  function handleTrack() {
    addToTracking(ticket)
    onTrack?.(ticket)
    toast('Añadido a seguimiento', {
      description: `${ticket.legs.length} selecciones en seguimiento.`,
    })
  }

  return (
    <Card className="relative flex h-full flex-col gap-0 overflow-hidden border-border bg-card p-0">
      {/* Mode accent strip — top 3px bar */}
      <div className={cn('h-[3px] w-full shrink-0', meta.accent)} aria-hidden />

      {/* ── HEADER — mode badge + combined odds ── */}
      <CardHeader className="gap-3 p-4 pb-0">
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

          {/* Combined odds — @ X.XX format, prominent, modern tabular style */}
          <span 
            style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' }}
            className="num font-mono text-2xl font-bold tracking-tight text-slate-100"
          >
            @ {ticket.combinedOdds.toFixed(2)}
          </span>
        </div>

        {/* Row 2: confidence bar */}
        <ConfidenceBar score={ticket.confidence} />

        {/* Row 3: EV average only — no correlation text */}
        <div className="pb-1">
          <span className="num text-xs font-semibold text-positive">
            +EV {(ticket.evAverage * 100).toFixed(1)}% promedio
          </span>
        </div>
      </CardHeader>

      {/* ── LEGS — Betano-style rows with horizontal dividers ── */}
      <CardContent className="flex-1 px-4 pt-1 pb-0">
        <ul>
          {ticket.legs.map((leg, i) => (
            <TicketLeg key={`${leg.match}-${leg.market}`} leg={leg} index={i} />
          ))}
        </ul>
      </CardContent>

      {/* ── FOOTER — single action ── */}
      <CardFooter className="mt-auto flex-col items-stretch gap-2 border-t border-border bg-surface-raised/50 p-4">
        <Button variant="outline" size="sm" className="w-full" onClick={handleTrack}>
          <StarIcon data-icon="inline-start" />
          Añadir a Seguimiento
        </Button>
        <p className="text-[10px] leading-tight text-subtle">
          Confianza basada en datos de 90 min. No es asesoría financiera.
        </p>
      </CardFooter>
    </Card>
  )
}
