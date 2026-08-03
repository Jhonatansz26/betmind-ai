'use client'
import Link from 'next/link'
import { ArrowRightIcon, TrendingUp, Trophy } from 'lucide-react'

import { Card } from '@/components/ui/card'
import {
  bestOpportunity,
  buildModel,
  marketRows,
  type Match,
} from '@/lib/betmind'
import { cn } from '@/lib/utils'
import { PoissonMiniChart } from './poisson-mini-chart'
import { TeamLogo } from '@/components/ui/team-logo'

function StatusBadge({ match }: { match: Match }) {
  const isLive = match.status === 'IN_PLAY' || match.status === 'LIVE'
  const isPaused = match.status === 'PAUSED'
  const isFinished = match.status === 'FINISHED' || match.status === 'FT'
  const hasElapsed = match.elapsed != null && match.elapsed > 0

  if (isLive) {
    return (
      <span className="num inline-flex items-center gap-1.5 rounded-full border border-positive/30 bg-positive/10 px-2 py-0.5 text-[10px] font-semibold text-positive">
        <span className="live-dot size-1.5 rounded-full bg-positive" aria-hidden />
        {hasElapsed ? `${match.elapsed}'` : 'EN VIVO'}
      </span>
    )
  }
  if (isPaused) {
    return (
      <span className="num inline-flex items-center gap-1.5 rounded-full border border-warning/30 bg-warning/10 px-2 py-0.5 text-[10px] font-semibold text-warning">
        <span className="size-1.5 rounded-full bg-warning" aria-hidden />
        PAUSADO
      </span>
    )
  }
  if (isFinished) {
    return (
      <span className="inline-flex items-center rounded-full border border-muted bg-muted/60 px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
        FINALIZADO
      </span>
    )
  }
  return null
}

/** Badge de match_type: muestra "COPA" para knockouts */
function MatchTypeBadge({ matchType }: { matchType: string }) {
  if (matchType !== 'KNOCKOUT_CUP') return null
  return (
    <span className="inline-flex items-center gap-1 rounded-sm border border-warning/30 bg-warning/10 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-warning">
      <Trophy className="size-2.5" aria-hidden />
      Copa
    </span>
  )
}

export function MatchCard({ match }: { match: Match }) {
  const model = buildModel(match.lambdaHome, match.lambdaAway)
  const rows = marketRows(match, model)
  const best = bestOpportunity(rows)
  const hasLambda = match.lambdaHome > 0 || match.lambdaAway > 0
  const isLive = match.status === 'IN_PLAY' || match.status === 'LIVE'
  const isFinished = match.status === 'FINISHED' || match.status === 'FT'
  const isScheduled = !isLive && !isFinished
  const hasRealScore =
    match.score != null
    && match.score.length === 2
    && typeof match.score[0] === 'number'
    && typeof match.score[1] === 'number'
  const showScore = (isLive || isFinished) && hasRealScore

  // Determinar si mostrar el banner de apuesta recomendada
  const showBestBet = isScheduled && best != null && hasLambda

  return (
    <Link href={`/partidos/${match.id}`} className="group block" aria-label={`Ver análisis de ${match.home} contra ${match.away}`}>
    <Card
      className={cn(
        'group gap-0 border-border bg-card p-0 transition-all duration-200',
        isLive && 'border-positive/30',
        isFinished && 'opacity-80',
        isScheduled && best && 'border-positive/40 shadow-[0_0_24px_-10px_var(--positive)]',
        isScheduled && !best && 'hover:border-primary/30',
      )}
    >
      {/* ── BANNER: Apuesta Recomendada Principal ── */}
      {showBestBet && (
        <div
          className="flex items-center gap-2.5 rounded-t-xl border-b border-positive/20 bg-positive/[0.07] px-4 py-2"
          aria-label="Apuesta recomendada"
        >
          <TrendingUp className="size-3.5 shrink-0 text-positive" aria-hidden />
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <span className="truncate text-[11px] font-bold text-positive">
              👉 {best.label}
            </span>
          </div>
          {/* Prob % chip */}
          <span className="num shrink-0 rounded-md border border-positive/30 bg-positive/15 px-2 py-0.5 text-[11px] font-bold tabular-nums text-positive">
            {(best.probability * 100).toFixed(1)}%
          </span>
          {/* Cuota chip */}
          {best.odds > 0 && (
            <span className="num shrink-0 rounded-md border border-border bg-surface-inset px-2 py-0.5 text-[11px] font-semibold tabular-nums text-foreground">
              @{best.odds.toFixed(2)}
            </span>
          )}
          {/* EV+ chip */}
          <span className="num ev-glow shrink-0 rounded-full border border-positive/30 bg-positive/10 px-2 py-0.5 text-[10px] font-bold text-positive shadow-[0_0_8px_-3px_var(--positive)]">
            🔥 EV+{(best.edge * 100).toFixed(1)}%
          </span>
        </div>
      )}

      <div className="flex items-center gap-4 px-4 py-3">
        {/* COLUMN 1 — Time / Status (100px) */}
        <div className="flex w-[100px] shrink-0 flex-col items-start gap-1">
          <p className="num text-sm font-semibold text-foreground">{match.time}</p>
          <StatusBadge match={match} />
          <MatchTypeBadge matchType={match.matchType ?? 'LEAGUE'} />
          {isScheduled && !best && (
            <span className="inline-flex items-center rounded-full border border-border/50 bg-surface/50 px-1.5 py-0.5 text-[9px] font-medium text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100">
              PROGRAMADO
            </span>
          )}
        </div>

        {/* COLUMN 2 — Teams + Score / Model (flex-1) */}
        <div className="flex min-w-0 flex-1 flex-col gap-1">
          {/* Home team */}
          <div className="flex items-center gap-2">
            <TeamLogo
              src={match.homeLogoUrl}
              teamName={match.home}
              teamId={match.homeTeamId}
              size={24}
            />
            <span className="truncate text-sm font-semibold text-foreground">
              {match.home}
            </span>
            {showScore && (
              <span className="num ml-auto text-lg font-black tabular-nums tracking-wider text-foreground">
                {match.score![0]}
              </span>
            )}
            {isScheduled && hasLambda && (
              <span className="num ml-auto text-xs font-medium text-subtle">
                {(model.home * 100).toFixed(1)}%
              </span>
            )}
          </div>

          {/* Away team */}
          <div className="flex items-center gap-2">
            <TeamLogo
              src={match.awayLogoUrl}
              teamName={match.away}
              teamId={match.awayTeamId}
              size={24}
            />
            <span className="truncate text-sm font-semibold text-foreground">
              {match.away}
            </span>
            {showScore && (
              <span className="num ml-auto text-lg font-black tabular-nums tracking-wider text-foreground">
                {match.score![1]}
              </span>
            )}
            {isScheduled && hasLambda && (
              <span className="num ml-auto text-xs font-medium text-subtle">
                {(model.away * 100).toFixed(1)}%
              </span>
            )}
          </div>

          {/* Model sub-strip */}
          {isFinished && showScore && hasLambda ? (
            <div className="flex items-center gap-2 opacity-50">
              <PoissonMiniChart lambdaHome={match.lambdaHome} lambdaAway={match.lambdaAway} />
              <span className="num text-[10px] text-subtle">
                {`xG ${match.lambdaHome.toFixed(2)} – ${match.lambdaAway.toFixed(2)}`}
              </span>
            </div>
          ) : isFinished && !showScore ? (
            <span className="text-[10px] italic text-subtle">Resultado pendiente</span>
          ) : isScheduled && hasLambda ? (
            <div className="flex items-center gap-2">
              <PoissonMiniChart lambdaHome={match.lambdaHome} lambdaAway={match.lambdaAway} />
              <span className="num text-[10px] text-subtle">
                {`Más probable ${model.mostLikely.score} (${(model.mostLikely.probability * 100).toFixed(1)}%) · xG ${match.lambdaHome.toFixed(2)}–${match.lambdaAway.toFixed(2)}`}
              </span>
            </div>
          ) : isScheduled && !hasLambda ? (
            <div className="flex items-center gap-2">
              <div className="h-3 w-16 animate-pulse rounded-sm bg-muted" aria-hidden />
              <span className="text-[10px] text-subtle">Calculando métricas…</span>
            </div>
          ) : null}
        </div>

        {/* COLUMN 3 — Edge + 1X2 + Link (200px) */}
        <div className="flex w-[180px] shrink-0 flex-col items-end gap-1.5">
          {isFinished ? (
            <span className="num inline-flex items-center gap-1 rounded-full border border-muted bg-surface-inset px-2.5 py-0.5 text-[11px] font-medium text-muted-foreground">
              Finalizado
            </span>
          ) : best ? (
            <div className="flex flex-col items-end gap-1">
              {/* Probabilidad destacada */}
              <span className="num text-lg font-black leading-none tabular-nums text-positive">
                {(best.probability * 100).toFixed(0)}%
              </span>
              <span className="num text-[10px] font-medium text-subtle">probabilidad</span>
            </div>
          ) : (
            <span className="text-[11px] font-medium tracking-wide text-subtle">SIN EDGE</span>
          )}

          {/* 1X2 probabilities — only for upcoming */}
          {isScheduled && (
            <div className="flex gap-1.5">
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
                  {`${label} ${(value * 100).toFixed(1)}%`}
                </span>
              ))}
            </div>
          )}

          <div className="inline-flex min-h-11 items-center gap-1 text-xs font-medium text-primary transition-opacity group-hover:opacity-80">
            {isFinished ? 'Ver Detalle' : 'Ver Análisis'}
            <ArrowRightIcon className="size-3" aria-hidden />
          </div>
        </div>
      </div>
    </Card>
    </Link>
  )
}
