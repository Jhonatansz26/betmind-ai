import { GlobeIcon } from 'lucide-react'
import type { TicketLegData } from '@/lib/betmind'
import { cn } from '@/lib/utils'

export function TicketLeg({ leg, index = 0 }: { leg: TicketLegData; index?: number }) {
  const evPositive = leg.ev > 0
  const evText = `${evPositive ? '+' : ''}${(leg.ev * 100).toFixed(1)}% EV`

  return (
    <li
      className="flex items-center justify-between rounded-lg border border-border/60 bg-surface/60 px-3.5 py-3 transition-colors hover:border-border"
      style={{ animationDelay: `${index * 80}ms` }}
    >
      {/* Left: market name / teams / EV */}
      <div className="flex flex-col gap-0.5 min-w-0 pr-3">
        <span className="truncate text-sm font-semibold text-foreground">{leg.market}</span>
        <div className="flex items-center gap-1.5 text-subtle">
          <GlobeIcon className="size-3 shrink-0" aria-hidden />
          <span className="truncate text-xs text-muted-foreground">{leg.match}</span>
        </div>
        <span className={cn('text-[10px] font-semibold', evPositive ? 'text-positive' : 'text-negative')}>
          {evText}
        </span>
      </div>

      {/* Right: Odds box */}
      <span className="num ml-2 shrink-0 rounded-md bg-surface-raised/80 px-2.5 py-1 text-base font-bold text-foreground">
        {leg.odds.toFixed(2)}
      </span>
    </li>
  )
}
