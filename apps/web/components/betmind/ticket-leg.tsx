'use client'

import * as React from 'react'
import { RotateCw } from 'lucide-react'

import type { TicketLegData } from '@/lib/betmind'
import { formatEV, formatOdds, formatPercent, formatxG } from '@/lib/formatters'
import { cn } from '@/lib/utils'

interface TicketLegProps {
  leg: TicketLegData
  index?: number
  onSwap?: () => void
}

export function TicketLeg({ leg, index = 0, onSwap }: TicketLegProps) {
  const [detailsOpen, setDetailsOpen] = React.useState(false)
  const [detailsPinned, setDetailsPinned] = React.useState(false)
  const hasPositiveEv = leg.ev >= 0

  return (
    <li
      className="stagger-item relative grid grid-cols-[minmax(0,1fr)_auto] items-center gap-3 border-b border-border/50 py-3 last:border-b-0"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      <div className="min-w-0">
        <p className="truncate text-xs font-semibold text-foreground">{leg.market}</p>
        <p className="mt-1 truncate text-xs text-muted-foreground" title={leg.match}>{leg.match}</p>
      </div>

      <div className="flex items-center gap-2">
        <div
          className="relative"
          onMouseEnter={() => setDetailsOpen(true)}
          onMouseLeave={() => {
            if (!detailsPinned) setDetailsOpen(false)
          }}
        >
          <button
            type="button"
            aria-expanded={detailsOpen}
            aria-label={`Ver detalle cuantitativo de ${leg.market}`}
            onClick={() => {
              setDetailsPinned((pinned) => !pinned)
              setDetailsOpen((open) => !open)
            }}
            className={cn(
              'rounded border px-2 py-1 font-mono text-xs font-bold tabular-nums transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60',
              hasPositiveEv
                ? 'border-positive/30 bg-positive/10 text-positive hover:bg-positive/15'
                : 'border-negative/30 bg-negative/10 text-negative hover:bg-negative/15',
            )}
          >
            {formatEV(leg.ev)} EV
          </button>

          {detailsOpen ? (
            <div
              role="dialog"
              aria-label="Ficha cuantitativa"
              className="absolute right-0 top-full z-20 mt-2 w-72 rounded-lg border border-border bg-popover p-3 text-left shadow-xl shadow-black/30"
            >
              <div className="flex items-start justify-between gap-3 border-b border-border/60 pb-2">
                <div>
                  <p className="terminal-label">Ficha cuantitativa</p>
                  <p className="mt-1 text-xs font-medium text-foreground">{leg.market}</p>
                </div>
                <span className="font-mono text-sm font-bold tabular-nums text-positive">{formatEV(leg.ev)} EV</span>
              </div>
              <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-2 text-xs">
                <div>
                  <dt className="text-muted-foreground">Goles esperados (xG)</dt>
                  <dd className="mt-0.5 font-mono tabular-nums text-foreground">
                    {leg.xgHome != null && leg.xgAway != null ? `${formatxG(leg.xgHome)} · ${formatxG(leg.xgAway)}` : '—'}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Cuota</dt>
                  <dd className="mt-0.5 font-mono tabular-nums text-foreground">@{formatOdds(leg.odds)}</dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Modelo vs. casa</dt>
                  <dd className="mt-0.5 font-mono tabular-nums text-foreground">
                    {leg.fairProb != null ? formatPercent(leg.fairProb) : '—'} / {leg.bookmakerProb != null ? formatPercent(leg.bookmakerProb) : '—'}
                  </dd>
                </div>
                <div>
                  <dt className="text-muted-foreground">Stake quarter-Kelly</dt>
                  <dd className="mt-0.5 font-mono tabular-nums text-foreground">
                    {leg.kellyStake != null ? formatPercent(leg.kellyStake) : '—'}
                  </dd>
                </div>
              </dl>
              <p className="mt-3 border-t border-border/60 pt-2 text-xs leading-5 text-muted-foreground">
                {leg.varianceNote || leg.reasoning || 'Varianza dentro del rango del perfil seleccionado.'}
              </p>
            </div>
          ) : null}
        </div>

        <span className="font-mono text-sm font-bold tabular-nums text-foreground">@{formatOdds(leg.odds)}</span>
        {onSwap ? (
          <button
            type="button"
            onClick={onSwap}
            aria-label={`Rotar selección ${index + 1}`}
            title="Rotar selección"
            className="flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-surface-raised hover:text-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60"
          >
            <RotateCw className="size-3.5" aria-hidden="true" />
          </button>
        ) : null}
      </div>
    </li>
  )
}
