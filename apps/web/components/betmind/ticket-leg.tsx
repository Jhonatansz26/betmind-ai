import type { TicketLegData } from '@/lib/betmind'
import { cn } from '@/lib/utils'
import { OddsPill } from './odds-pill'

const SPORT_ICON = '⚽'

export function TicketLeg({ leg, index = 0 }: { leg: TicketLegData; index?: number }) {
  const evPositive = leg.ev > 0
  const evText = `${evPositive ? '+' : ''}${(leg.ev * 100).toFixed(1)}% EV`

  return (
    <li
      className="grid grid-cols-[20px_1fr_auto] items-center gap-3 border-b border-border-subtle py-3 last:border-b-0"
      style={{ animationDelay: `${index * 80}ms` }}
    >
      {/* Sport icon */}
      <span aria-hidden className="text-base leading-none">
        {SPORT_ICON}
      </span>

      {/* Center: market name / teams / EV on separate lines */}
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-foreground">{leg.market}</p>
        <p className="truncate text-xs text-muted-foreground">{leg.match}</p>
        <p className={cn('text-[11px] font-medium', evPositive ? 'text-positive' : 'text-negative')}>
          {evText}
        </p>
      </div>

      {/* Odds pill — right anchored */}
      <OddsPill value={leg.odds} />
    </li>
  )
}
