'use client'

import * as React from 'react'
import { toast } from 'sonner'
import { CheckIcon, ChevronDownIcon, CopyIcon, MoveUpRightIcon, StarIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card'
import { Separator } from '@/components/ui/separator'
import { MODE_META, type Ticket } from '@/lib/betmind'
import { cn } from '@/lib/utils'
import { TicketLeg } from './ticket-leg'

function confidenceColor(score: number) {
  if (score > 70) return 'text-positive'
  if (score >= 50) return 'text-warning'
  return 'text-negative'
}

export function TicketCard({ ticket }: { ticket: Ticket }) {
  const [expanded, setExpanded] = React.useState(false)
  const [copied, setCopied] = React.useState(false)
  const meta = MODE_META[ticket.mode]

  function handleCopy() {
    const text = ticket.legs
      .map((leg) => `${leg.match} — ${leg.market} @ ${leg.odds.toFixed(2)}`)
      .join('\n')
    void navigator.clipboard?.writeText(
      `BetMind AI · ${meta.label}\n${text}\nCuota combinada: ${ticket.combinedOdds.toFixed(2)}`,
    )
    setCopied(true)
    toast.success('Ticket copied to clipboard ✓')
    window.setTimeout(() => setCopied(false), 2000)
  }

  return (
    <Card className="relative flex h-full flex-col gap-0 overflow-hidden border-border bg-card p-0">
      <div className={cn('h-[3px] w-full', meta.accent)} aria-hidden />

      <CardHeader className="gap-4 p-4">
        <div className="flex items-start justify-between gap-3">
          <span
            className={cn(
              'inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-[11px] font-medium tracking-wide',
              meta.border,
              meta.bg,
              meta.text,
            )}
          >
            <span aria-hidden>{meta.glyph}</span>
            {meta.label}
          </span>
          <span className="flex items-baseline gap-0.5">
            <span className={cn('num text-2xl leading-none font-semibold', confidenceColor(ticket.confidence))}>
              {ticket.confidence}
            </span>
            <span className="num text-xs text-subtle">/100</span>
          </span>
        </div>

        <div className="flex flex-col gap-1">
          <p className="num font-serif text-3xl leading-none text-foreground">
            {`× ${ticket.combinedOdds.toFixed(2)}`}
          </p>
          <p className="num text-xs text-positive">
            {`Valor Esperado: +${(ticket.evAverage * 100).toFixed(1)}% promedio`}
          </p>
        </div>
      </CardHeader>

      <CardContent className="flex flex-1 flex-col gap-3 p-4 pt-0">
        <ul className="flex flex-col gap-2">
          {ticket.legs.map((leg) => (
            <TicketLeg key={`${leg.match}-${leg.market}`} leg={leg} />
          ))}
        </ul>

        <p className="flex items-start gap-1.5 text-xs text-subtle">
          <MoveUpRightIcon
            className={cn('mt-0.5 size-3 shrink-0', ticket.correlationPositive ? 'text-positive' : 'text-warning')}
            aria-hidden
          />
          <span className="text-pretty">{ticket.correlation}</span>
        </p>

        <Separator className="mt-auto" />

        <button
          type="button"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
          className="flex w-full items-center justify-between rounded-md border border-border px-3 py-2 text-left text-xs font-medium text-muted-foreground transition-colors hover:bg-muted/50 hover:text-foreground"
        >
          Mostrar Análisis Táctico
          <ChevronDownIcon
            className={cn('size-3.5 transition-transform duration-200', expanded && 'rotate-180')}
            aria-hidden
          />
        </button>

        <div
          className={cn(
            'grid transition-all duration-300 ease-out',
            expanded ? 'grid-rows-[1fr] opacity-100' : 'grid-rows-[0fr] opacity-0',
          )}
        >
          <div className="overflow-hidden">
            <div className="flex flex-col gap-3 rounded-md border border-border bg-background/50 p-3">
              <p className="text-xs leading-relaxed text-muted-foreground">{ticket.analysis}</p>
              <ul className="flex flex-col gap-1.5">
                {ticket.pros.map((pro) => (
                  <li key={pro} className="flex items-start gap-2 text-xs text-muted-foreground">
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-positive" aria-hidden />
                    <span className="text-pretty">{pro}</span>
                  </li>
                ))}
                {ticket.cons.map((con) => (
                  <li key={con} className="flex items-start gap-2 text-xs text-muted-foreground">
                    <span className="mt-1.5 size-1.5 shrink-0 rounded-full bg-warning" aria-hidden />
                    <span className="text-pretty">{con}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      </CardContent>

      <CardFooter className="mt-auto flex-col items-stretch gap-3 border-t border-border bg-surface-raised/60 p-4">
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" className="flex-1" onClick={handleCopy}>
            {copied ? (
              <CheckIcon data-icon="inline-start" className="text-positive" />
            ) : (
              <CopyIcon data-icon="inline-start" />
            )}
            {copied ? 'Copiado' : 'Copiar Selecciones'}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            className="flex-1"
            onClick={() => toast('Añadido a lista de seguimiento', { description: `${ticket.legs.length} selecciones en seguimiento.` })}
          >
            <StarIcon data-icon="inline-start" />
            Añadir a Seguimiento
          </Button>
        </div>
        <p className="text-xs text-subtle">
          Confianza del modelo basada únicamente en datos de 90 min reglamentarios. No es asesoría financiera.
        </p>
      </CardFooter>
    </Card>
  )
}
