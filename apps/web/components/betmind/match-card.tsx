'use client'

import { ArrowRightIcon } from 'lucide-react'

import { Card } from '@/components/ui/card'
import {
  bestOpportunity,
  buildModel,
  marketRows,
  type Match,
} from '@/lib/betmind'
import { cn } from '@/lib/utils'
import { PoissonMiniChart } from './poisson-mini-chart'

function StatusPill({ match }: { match: Match }) {
  if (match.status === 'LIVE') {
    return (
      <span className="num inline-flex items-center gap-1.5 rounded-sm border border-positive/30 bg-positive/10 px-1.5 py-0.5 text-[11px] font-medium text-positive">
        <span className="live-dot size-1.5 rounded-full bg-positive" aria-hidden />
        {`LIVE ${match.minute}'`}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center rounded-sm border border-border bg-muted/60 px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">
      {match.status}
    </span>
  )
}

export function MatchCard({ match, onOpen }: { match: Match; onOpen: (match: Match) => void }) {
  const model = buildModel(match.lambdaHome, match.lambdaAway)
  const rows = marketRows(match, model)
  const best = bestOpportunity(rows)

  return (
    <Card
      className={cn(
        'group gap-0 border-border bg-card p-0 transition-colors',
        best
          ? 'border-positive/40 shadow-[0_0_24px_-10px_var(--positive)]'
          : 'hover:border-primary/30',
      )}
    >
      <div className="flex flex-col gap-4 p-4 lg:flex-row lg:items-center lg:gap-6">
        {/* LEFT — meta */}
        <div className="flex items-center justify-between gap-3 lg:w-[20%] lg:flex-col lg:items-start lg:justify-start lg:gap-1.5">
          <p className="flex items-center gap-1.5 text-xs text-subtle">
            <span aria-hidden>{match.flag}</span>
            {match.league}
          </p>
          <p className="num text-sm font-medium text-foreground">{match.time}</p>
          <StatusPill match={match} />
        </div>

        {/* CENTER — teams + distribution */}
        <div className="flex flex-col gap-2 lg:w-[50%]">
          <div className="flex items-center justify-between gap-3">
            <span className="truncate text-sm font-medium text-foreground">{match.home}</span>
            <span className="num text-xs text-muted-foreground">{`${(model.home * 100).toFixed(1)}%`}</span>
          </div>

          <div className="flex items-center gap-3">
            <PoissonMiniChart lambdaHome={match.lambdaHome} lambdaAway={match.lambdaAway} />
            <div className="flex flex-col gap-0.5">
              <span className="num text-[11px] text-subtle">
                {`Most likely: ${model.mostLikely.score} (${(model.mostLikely.probability * 100).toFixed(1)}%)`}
              </span>
              <span className="num text-[11px] text-subtle">
                {`λ ${match.lambdaHome.toFixed(2)} · ${match.lambdaAway.toFixed(2)}`}
              </span>
              {match.score ? (
                <span className="num text-[11px] text-positive">
                  {`Live score: ${match.score[0]}-${match.score[1]}`}
                </span>
              ) : null}
            </div>
          </div>

          <div className="flex items-center justify-between gap-3">
            <span className="truncate text-sm font-medium text-foreground">{match.away}</span>
            <span className="num text-xs text-muted-foreground">{`${(model.away * 100).toFixed(1)}%`}</span>
          </div>
        </div>

        {/* RIGHT — edge + 1X2 */}
        <div className="flex flex-col gap-2 border-t border-border pt-3 lg:w-[30%] lg:border-t-0 lg:pt-0 lg:pl-6">
          {best ? (
            <span className="num inline-flex w-fit items-center gap-2 rounded-md border border-positive/30 bg-gradient-to-b from-positive/20 to-positive/5 px-2.5 py-1 text-sm font-semibold text-positive">
              EV+
              <span className="text-xs font-medium">{`+${(best.edge * 100).toFixed(1)}%`}</span>
            </span>
          ) : (
            <span className="w-fit text-xs font-medium tracking-wide text-subtle">NO EDGE</span>
          )}

          <div className="flex flex-wrap gap-1.5">
            {(
              [
                ['1', model.home],
                ['X', model.draw],
                ['2', model.away],
              ] as const
            ).map(([label, value]) => (
              <span
                key={label}
                className="num rounded-sm border border-border bg-background/50 px-1.5 py-0.5 text-[11px] text-muted-foreground"
              >
                {`${label}: ${(value * 100).toFixed(1)}%`}
              </span>
            ))}
          </div>

          <button
            type="button"
            onClick={() => onOpen(match)}
            className="inline-flex w-fit items-center gap-1 text-sm font-medium text-primary transition-opacity hover:opacity-80"
          >
            View Analysis
            <ArrowRightIcon className="size-3.5" aria-hidden />
          </button>
        </div>
      </div>
    </Card>
  )
}
