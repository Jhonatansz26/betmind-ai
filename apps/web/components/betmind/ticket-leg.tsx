import type { TicketLegData } from '@/lib/betmind'
import { EVBadge } from './ev-badge'

export function TicketLeg({ leg }: { leg: TicketLegData }) {
  return (
    <li className="flex flex-col gap-1.5 rounded-md border border-border bg-background/40 px-3 py-3">
      <div className="flex items-center gap-2">
        <span aria-hidden className="text-sm leading-none">
          {leg.flag}
        </span>
        <span className="truncate text-xs text-muted-foreground">{leg.match}</span>
      </div>
      <div className="flex items-center justify-between gap-2">
        <span className="truncate text-sm font-medium text-foreground">{leg.market}</span>
        <EVBadge value={leg.ev} />
      </div>
      <div className="flex items-center gap-2">
        <span className="num rounded-sm border border-primary/30 bg-primary/10 px-1.5 py-0.5 text-[11px] text-primary">
          {`P: ${(leg.prob * 100).toFixed(1)}%`}
        </span>
        <span className="num text-[11px] text-muted-foreground">
          {`@ ${leg.odds.toFixed(2)}`}
        </span>
      </div>
    </li>
  )
}
