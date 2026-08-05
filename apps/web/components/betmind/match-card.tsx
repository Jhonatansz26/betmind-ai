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
import { PoissonMiniChart } from './poisson-mini-chart'
import { TeamLogo } from '@/components/ui/team-logo'

function StatusBadge({ match }: { match: Match }) {
  const isLive = match.status === 'IN_PLAY' || match.status === 'LIVE'
  const isPaused = match.status === 'PAUSED'
  const isFinished = match.status === 'FINISHED' || match.status === 'FT'
  const hasElapsed = match.elapsed != null && match.elapsed > 0

  if (isLive) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-positive/30 bg-positive/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-positive">
        <span className="live-dot size-1.5 rounded-full bg-positive" aria-hidden />
        {hasElapsed ? `${match.elapsed}'` : 'EN VIVO'}
      </span>
    )
  }
  if (isPaused) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-warning/30 bg-warning/10 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-warning">
        <span className="size-1.5 rounded-full bg-warning" aria-hidden />
        PAUSADO
      </span>
    )
  }
  if (isFinished) {
    return (
      <span className="inline-flex items-center rounded-full border border-muted bg-muted/60 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
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
    <span className="inline-flex items-center rounded-sm border border-warning/30 bg-warning/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-warning">
      COPA
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
      {/* ── BANNER: Alpha Strip ── */}
      {showBestBet && (
        <div
          className="flex items-center justify-between border-b border-positive/20 bg-positive/[0.04] px-4 py-2 text-xs"
          title={`Modelo Poisson calibrado · Confianza cuantitativa: ${(best.probability * 100).toFixed(0)}%`}
        >
          {/* Lado Izquierdo */}
          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold text-foreground">
              {best.label}
            </span>
            <span className="font-mono tabular-nums font-bold text-positive">
              {(best.probability * 100).toFixed(1)}%
            </span>
          </div>
          
          {/* Lado Derecho */}
          <div className="flex items-center gap-2">
            <span className="font-mono tabular-nums text-muted-foreground">
              @{best.odds.toFixed(2)}
            </span>
            <span className="rounded border border-positive/30 bg-positive/10 px-2 py-0.5 font-mono text-xs font-bold text-positive">
              +EV {(best.ev * 100).toFixed(1)}%
            </span>
          </div>
        </div>
      )}

      <div className="flex items-center gap-4 px-4 py-3">
        {/* COLUMN 1 — Time / Status (100px) */}
        <div className="flex w-[100px] shrink-0 flex-col items-start gap-1">
          <p className="font-mono tabular-nums text-xs font-medium text-muted-foreground">{match.time}</p>
          <StatusBadge match={match} />
          <MatchTypeBadge matchType={match.matchType ?? 'LEAGUE'} />
          {isScheduled && !best && (
            <span className="inline-flex items-center rounded-full border border-border/50 bg-surface/50 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100">
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
              <span className="ml-auto font-mono tabular-nums text-base font-bold text-foreground">
                {match.score![0]}
              </span>
            )}
            {isScheduled && hasLambda && (
              <span className="ml-auto font-mono tabular-nums text-xs font-medium text-muted-foreground">
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
              <span className="ml-auto font-mono tabular-nums text-base font-bold text-foreground">
                {match.score![1]}
              </span>
            )}
            {isScheduled && hasLambda && (
              <span className="ml-auto font-mono tabular-nums text-xs font-medium text-muted-foreground">
                {(model.away * 100).toFixed(1)}%
              </span>
            )}
          </div>

          {/* Model sub-strip */}
          {isFinished && showScore && hasLambda ? (
            <div className="flex items-center gap-2 opacity-50">
              <PoissonMiniChart lambdaHome={match.lambdaHome} lambdaAway={match.lambdaAway} />
              <span className="font-mono tabular-nums text-xs text-muted-foreground">
                {`xG ${match.lambdaHome.toFixed(2)} - ${match.lambdaAway.toFixed(2)}`}
              </span>
            </div>
          ) : isFinished && !showScore ? (
            <span className="font-mono text-xs italic text-muted-foreground">Resultado pendiente</span>
          ) : isScheduled && hasLambda ? (
            <div className="flex items-center gap-2">
              <PoissonMiniChart lambdaHome={match.lambdaHome} lambdaAway={match.lambdaAway} />
              <span className="font-mono tabular-nums text-xs text-muted-foreground">
                {`xG ${match.lambdaHome.toFixed(2)} - ${match.lambdaAway.toFixed(2)} · Marcador est. ${model.mostLikely.score} (${(model.mostLikely.probability * 100).toFixed(1)}%)`}
              </span>
            </div>
          ) : isScheduled && !hasLambda ? (
            <div className="flex items-center gap-2">
              <div className="h-3 w-16 animate-pulse rounded-sm bg-muted" aria-hidden />
              <span className="font-mono text-xs text-muted-foreground">Calculando métricas…</span>
            </div>
          ) : null}
        </div>

        {/* COLUMN 3 — Probabilidades 1X2 y Acción (180px) */}
        <div className="flex w-[180px] shrink-0 flex-col items-end justify-center gap-2">
          {/* 1X2 probabilities — only for upcoming */}
          {isScheduled && (
            <div className="flex gap-1.5 mb-1">
              {(
                [
                  ['1', model.home],
                  ['X', model.draw],
                  ['2', model.away],
                ] as const
              ).map(([label, value]) => (
                <span
                  key={label}
                  className="rounded border border-border/60 bg-surface/40 px-1.5 py-0.5 font-mono tabular-nums text-xs text-muted-foreground"
                >
                  {`${label} ${(value * 100).toFixed(1)}%`}
                </span>
              ))}
            </div>
          )}

          <div className="inline-flex items-center gap-1 text-xs font-medium text-primary transition-opacity group-hover:opacity-80">
            {isFinished ? 'Ver Detalle' : 'Ver Análisis'}
            <ArrowRightIcon className="size-3 transition-transform group-hover:translate-x-0.5" aria-hidden />
          </div>
        </div>
      </div>
    </Card>
    </Link>
  )
}
