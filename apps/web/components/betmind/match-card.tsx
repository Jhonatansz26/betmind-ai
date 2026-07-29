'use client'

import Link from 'next/link'
import { ArrowRightIcon } from 'lucide-react'

import { Card } from '@/components/ui/card'
import {
  bestOpportunity,
  buildModel,
  marketRows,
  type Match,
} from '@/lib/betmind'
import { cn } from '@/lib/utils'
import { resolveLeague } from '@/lib/league-metadata'
import { PoissonMiniChart } from './poisson-mini-chart'
import { LeagueLogo } from './league-logo'
import { TeamLogo } from './team-logo'

function StatusPill({ match }: { match: Match }) {
  if (match.status === 'LIVE') {
    const minute = match.minute ?? 0
    return (
      <span className="num inline-flex items-center gap-1.5 rounded-sm border border-positive/30 bg-positive/10 px-1.5 py-0.5 text-[11px] font-medium text-positive">
        <span className="live-dot size-1.5 rounded-full bg-positive" aria-hidden />
        {`EN VIVO ${minute}'`}
      </span>
    )
  }
  return (
    <span className="inline-flex items-center rounded-sm border border-border bg-muted/60 px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">
      {match.status === 'UPCOMING' ? 'POR JUGAR' : match.status}
    </span>
  )
}

export function MatchCard({ match }: { match: Match }) {
  const model = buildModel(match.lambdaHome, match.lambdaAway)
  const rows = marketRows(match, model)
  const best = bestOpportunity(rows)
  const leagueMeta = resolveLeague(match.leagueExternalId, match.league)
  const hasLambda = match.lambdaHome > 0 || match.lambdaAway > 0

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
            <LeagueLogo logoUrl={match.leagueLogoUrl} flag={leagueMeta.flag} size="sm" />
            {leagueMeta.name}
          </p>
          <p className="num text-sm font-medium text-foreground">{match.time}</p>
          <StatusPill match={match} />
        </div>

        {/* CENTER — teams + distribution */}
        <div className="flex flex-col gap-2 lg:w-[50%]">
          <div className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-2 truncate text-sm font-medium text-foreground">
              <TeamLogo logoUrl={match.homeLogoUrl} teamName={match.home} size="sm" />
              {match.home}
            </span>
            {hasLambda && (
              <span className="num text-xs text-muted-foreground">{`${(model.home * 100).toFixed(1)}%`}</span>
            )}
          </div>

          {hasLambda ? (
            <div className="flex items-center gap-3">
              <PoissonMiniChart lambdaHome={match.lambdaHome} lambdaAway={match.lambdaAway} />
              <div className="flex flex-col gap-0.5">
                <span className="num text-[11px] text-subtle">
                  {`Más probable: ${model.mostLikely.score} (${(model.mostLikely.probability * 100).toFixed(1)}%)`}
                </span>
                <span className="num text-[11px] text-subtle">
                  {`xG: ${match.lambdaHome.toFixed(2)} - ${match.lambdaAway.toFixed(2)}`}
                </span>
                {match.score ? (
                  <span className="num text-[11px] text-positive">
                    {`Live score: ${match.score[0]}-${match.score[1]}`}
                  </span>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2 rounded-md border border-border bg-surface-inset px-2.5 py-1.5">
              <span className="text-[11px] text-subtle">Modelo por calcular</span>
            </div>
          )}

          <div className="flex items-center justify-between gap-3">
            <span className="flex items-center gap-2 truncate text-sm font-medium text-foreground">
              <TeamLogo logoUrl={match.awayLogoUrl} teamName={match.away} size="sm" />
              {match.away}
            </span>
            {hasLambda && (
              <span className="num text-xs text-muted-foreground">{`${(model.away * 100).toFixed(1)}%`}</span>
            )}
          </div>
        </div>

        {/* RIGHT — edge + 1X2 + link */}
        <div className="flex flex-col gap-2 border-t border-border pt-3 lg:w-[30%] lg:border-t-0 lg:pt-0 lg:pl-6">
          {best ? (
            <span className="num inline-flex w-fit items-center gap-2 rounded-md border border-positive/30 bg-gradient-to-b from-positive/20 to-positive/5 px-2.5 py-1 text-sm font-semibold text-positive">
              EV+
              <span className="text-xs font-medium">{`+${(best.edge * 100).toFixed(1)}%`}</span>
            </span>
          ) : (
            <span className="w-fit text-xs font-medium tracking-wide text-subtle">SIN EDGE</span>
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
                className="num rounded-sm border border-border bg-surface-inset px-1.5 py-0.5 text-[11px] text-muted-foreground"
              >
                {`${label}: ${(value * 100).toFixed(1)}%`}
              </span>
            ))}
          </div>

          {/* Link to full-page analysis — replaces modal trigger */}
          <Link
            href={`/partidos/${match.id}`}
            className="inline-flex w-fit items-center gap-1 text-sm font-medium text-primary transition-opacity hover:opacity-80"
          >
            Ver Análisis
            <ArrowRightIcon className="size-3.5" aria-hidden />
          </Link>
        </div>
      </div>
    </Card>
  )
}
