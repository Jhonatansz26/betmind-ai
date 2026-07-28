'use client'

import * as React from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { ArrowLeftIcon, CheckIcon, SparklesIcon } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  bestOpportunity,
  buildModel,
  marketRows,
  type Match,
  type MatchModel,
  type MarketRow,
  type Mode,
} from '@/lib/betmind'
import { fetchMatchPrediction, type EnrichedMatch } from '@/lib/api'
import { resolveLeague } from '@/lib/league-metadata'
import { cn } from '@/lib/utils'
import { MarketTable } from '@/components/betmind/market-table'
import { ModeSelector } from '@/components/betmind/mode-selector'
import { PoissonModalChart } from '@/components/betmind/poisson-modal-chart'
import { RefereeWidget } from '@/components/betmind/referee-widget'
import { TacticalPanel } from '@/components/betmind/tactical-panel'
import { MatchTabBar, type MatchTab } from '@/components/betmind/match-tab-bar'
import { MatchComparisonBars, type ComparisonStat } from '@/components/betmind/match-comparison-bars'
import { TrendPills, buildTrendPills } from '@/components/betmind/trend-pills'
import { InsufficientDataCard } from '@/components/betmind/insufficient-data-card'

/* ------------------------------------------------------------------ */
/* Helpers                                                             */
/* ------------------------------------------------------------------ */

function hasLambda(match: Match): boolean {
  return match.lambdaHome > 0 || match.lambdaAway > 0
}

function hasRefereeData(match: Match): boolean {
  const r = match.referee
  return r.strictness > 0 || r.yellows > 0 || r.fouls > 0
}

function hasTacticalData(match: Match): boolean {
  return match.pros.length > 0 || match.cons.length > 0
}

/** Genera el array de métricas autorizadas para MatchComparisonBars */
function buildComparisonStats(model: MatchModel): ComparisonStat[] {
  return [
    { label: 'Victoria',     home: model.home,   away: model.away,   format: 'percent' },
    { label: 'Empate',       home: model.draw,   away: model.draw,   format: 'percent' },
    { label: 'Over 2.5',     home: model.over25, away: model.over25, format: 'percent' },
    { label: 'Ambos Anotan', home: model.btts,   away: model.btts,   format: 'percent' },
  ]
}

/* ------------------------------------------------------------------ */
/* Skeleton                                                            */
/* ------------------------------------------------------------------ */

function PageSkeleton() {
  return (
    <div className="flex flex-col gap-4">
      <div className="h-32 animate-pulse rounded-xl bg-card" />
      <div className="h-10 animate-pulse rounded-lg bg-card" />
      <div className="h-48 animate-pulse rounded-xl bg-card" />
      <div className="h-24 animate-pulse rounded-xl bg-card" />
      <div className="h-64 animate-pulse rounded-xl bg-card" />
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Section header                                                      */
/* ------------------------------------------------------------------ */

function SectionTitle({
  children,
  badge,
}: {
  children: React.ReactNode
  badge?: React.ReactNode
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h2 className="text-[11px] font-semibold tracking-[0.10em] text-subtle uppercase">
        {children}
      </h2>
      {badge}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Tab: Previa & Pronóstico                                            */
/* ------------------------------------------------------------------ */

function PreviewTab({
  match,
  model,
  rows,
  best,
}: {
  match: Match
  model: MatchModel
  rows: MarketRow[]
  best: MarketRow | null
}) {
  const [selectedMarket, setSelectedMarket] = React.useState<string | null>(null)
  const [mode, setMode] = React.useState<Mode>('EDGE')
  const selectable = rows.filter((row) => row.edge > 0)
  const comparisonStats = buildComparisonStats(model)
  const trendPills = buildTrendPills(model, best)
  const lambdaAvailable = hasLambda(match)

  return (
    <div
      id="match-panel-preview"
      role="tabpanel"
      aria-labelledby="match-tab-preview"
      className="grid grid-cols-1 gap-6 lg:grid-cols-[3fr_2fr]"
    >
      {/* ── COLUMNA IZQUIERDA (60%) ── */}
      <div className="flex flex-col gap-5">
        {/* Veredicto +EV destacado con botón Guardar en mi Boleto */}
        {best ? (
          <div className="flex flex-wrap items-center justify-between gap-4 rounded-xl border border-positive/40 bg-gradient-to-r from-positive/15 to-positive/5 p-4 shadow-sm">
            <div className="flex items-center gap-3">
              <span className="num rounded-md bg-positive px-2.5 py-1 text-sm font-bold text-white shadow-sm">
                EV+
              </span>
              <div className="flex flex-col gap-0.5">
                <span className="text-sm font-bold text-foreground">{best.label}</span>
                <span className="num text-xs font-semibold text-positive">
                  {`+${(best.edge * 100).toFixed(1)}% edge · Cuota ${best.odds.toFixed(2)}`}
                </span>
              </div>
            </div>
            <Button
              size="sm"
              className="bg-positive font-semibold text-white shadow-sm transition-opacity hover:bg-positive/90"
              onClick={() => {
                toast.success('Añadido al boleto', {
                  description: `${best.label} · ${match.home} vs ${match.away}`,
                })
              }}
            >
              ⭐ Guardar en mi Boleto
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-3 rounded-xl border border-border bg-surface-inset px-4 py-3">
            <span className="text-xs text-muted-foreground">
              Ningún mercado supera el umbral de 3% de edge en este partido.
            </span>
          </div>
        )}

        {/* Tendencias */}
        <TrendPills pills={trendPills} />

        {/* Tabla de Mercados + Selector */}
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex flex-col gap-4">
            <SectionTitle>Análisis de Valor Esperado (+EV)</SectionTitle>
            <MarketTable rows={rows} />

            {selectable.length > 0 && (
              <>
                <SectionTitle>Seleccionar Mercado para Boleto Manual</SectionTitle>
                <ul className="flex flex-col gap-2">
                  {selectable.map((row) => {
                    const active = selectedMarket === row.key
                    return (
                      <li key={row.key}>
                        <button
                          type="button"
                          onClick={() => setSelectedMarket(active ? null : row.key)}
                          aria-pressed={active}
                          className={cn(
                            'flex w-full items-center justify-between gap-3 rounded-md border px-3 py-2.5 text-left transition-colors',
                            active
                              ? 'border-primary/50 bg-primary/10'
                              : 'border-border bg-surface-inset hover:border-primary/30',
                          )}
                        >
                          <span className="flex items-center gap-2">
                            {active ? (
                              <CheckIcon className="size-4 text-primary" aria-hidden />
                            ) : (
                              <span className="size-4 rounded-full border border-border" aria-hidden />
                            )}
                            <span className="text-sm font-medium text-foreground">{row.label}</span>
                          </span>
                          <span className="num flex items-center gap-3 text-xs">
                            <span className="text-muted-foreground">{row.odds.toFixed(2)}</span>
                            <span className="text-positive">{`+${(row.edge * 100).toFixed(1)}%`}</span>
                          </span>
                        </button>
                      </li>
                    )
                  })}
                </ul>

                <ModeSelector value={mode} onChange={setMode} />

                <Button
                  className="w-full bg-gradient-to-b from-primary to-primary/80"
                  disabled={!selectedMarket}
                  onClick={() => {
                    const row = rows.find((r) => r.key === selectedMarket)
                    toast.success('Añadido al boleto', {
                      description: `${row?.label} · ${match.home} vs ${match.away} · modo ${mode}`,
                    })
                    setSelectedMarket(null)
                  }}
                >
                  Añadir al Boleto
                </Button>
              </>
            )}
          </div>
        </div>
      </div>

      {/* ── COLUMNA DERECHA (40%) ── */}
      <div className="flex flex-col gap-5">
        {/* Barras Comparativas (solo datos reales del modelo) */}
        <div className="rounded-xl border border-border bg-card p-4">
          <SectionTitle>Probabilidades del Modelo</SectionTitle>
          <div className="mt-3">
            {lambdaAvailable ? (
              <MatchComparisonBars
                homeLabel={match.home}
                awayLabel={match.away}
                stats={comparisonStats}
              />
            ) : (
              <InsufficientDataCard
                title="Modelo Cuantitativo"
                message="Se requieren datos históricos para calibrar las probabilidades de este partido."
              />
            )}
          </div>
        </div>

        {/* Gráfico Poisson (con guard de lambda) */}
        <div className="rounded-xl border border-border bg-card p-4">
          <div className="flex flex-col gap-4">
            <SectionTitle>Distribución de Goles (Poisson)</SectionTitle>
            {lambdaAvailable ? (
              <>
                <PoissonModalChart
                  lambdaHome={match.lambdaHome}
                  lambdaAway={match.lambdaAway}
                  homeLabel={match.home}
                  awayLabel={match.away}
                />
                <div className="flex flex-col gap-2 rounded-lg border border-border bg-surface-inset p-3">
                  <p className="text-[10px] font-medium tracking-wide text-subtle uppercase">
                    Marcadores Más Probables
                  </p>
                  <ul className="flex flex-col gap-1">
                    {model.topScores.map((line) => (
                      <li
                        key={line.score}
                        className="num flex items-center justify-between text-sm text-muted-foreground"
                      >
                        <span className="font-medium text-foreground">{line.score}</span>
                        <span>{`${(line.probability * 100).toFixed(1)}%`}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </>
            ) : (
              <InsufficientDataCard
                title="Modelo de Goles por Poisson"
                message="El cálculo de distribución de goles requiere al menos 5 partidos históricos registrados."
              />
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Tab: H2H & Táctico                                                  */
/* ------------------------------------------------------------------ */

function H2HTab({ match }: { match: Match }) {
  return (
    <div
      id="match-panel-h2h"
      role="tabpanel"
      aria-labelledby="match-tab-h2h"
      className="flex flex-col gap-5"
    >
      <div className="rounded-xl border border-border bg-card p-4">
        <div className="flex flex-col gap-4">
          <SectionTitle
            badge={
              <span className="inline-flex items-center gap-1.5 rounded-sm border border-border bg-muted/60 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                <SparklesIcon className="size-3" aria-hidden />
                Potenciado por Groq · Llama 3.3
              </span>
            }
          >
            Análisis Táctico & H2H
          </SectionTitle>
          {hasTacticalData(match) ? (
            <TacticalPanel match={match} />
          ) : (
            <InsufficientDataCard
              title="Análisis Táctico"
              message="El análisis de pros, contras y señal táctica se generará antes del inicio del partido."
            />
          )}
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Tab: Árbitro                                                        */
/* ------------------------------------------------------------------ */

function RefereeTab({ match }: { match: Match }) {
  const showWidget = hasRefereeData(match)

  return (
    <div
      id="match-panel-referee"
      role="tabpanel"
      aria-labelledby="match-tab-referee"
      className="flex flex-col gap-5"
    >
      <div className="rounded-xl border border-border bg-card p-4">
        <div className="flex flex-col gap-4">
          <SectionTitle badge={<span className="text-xs text-muted-foreground">{match.referee.name}</span>}>
            Perfil del Árbitro
          </SectionTitle>
          {showWidget ? (
            <RefereeWidget referee={match.referee} />
          ) : (
            <InsufficientDataCard
              title="Árbitro sin estadísticas"
              message={
                match.referee.name === 'Por confirmar'
                  ? 'El árbitro aún no ha sido designado para este partido.'
                  : `No hay estadísticas históricas registradas para ${match.referee.name}.`
              }
            />
          )}
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Match detail content                                                */
/* ------------------------------------------------------------------ */

function MatchDetailContent({ match, enriched }: { match: Match; enriched?: EnrichedMatch | null }) {
  const [activeTab, setActiveTab] = React.useState<MatchTab>('preview')
  const model = React.useMemo(() => buildModel(match.lambdaHome, match.lambdaAway), [match])
  const rows = React.useMemo(() => marketRows(match, model), [match, model])
  const best = React.useMemo(() => bestOpportunity(rows), [rows])
  const leagueMeta = resolveLeague(match.leagueExternalId, match.league)
  const hasPrediction = enriched != null && (enriched.confidenceScore > 0 || enriched.evAnalysis.length > 0)

  return (
    <div className="flex flex-col gap-0">
      {/* ── HEADER (permanente, fuera de tabs) ── */}
      <div className="rounded-xl border border-border bg-card p-5">
        {/* Meta row */}
        <p className="flex flex-wrap items-center gap-2 text-xs text-subtle">
          <span aria-hidden>{leagueMeta.flag}</span>
          {leagueMeta.name}
          <span aria-hidden>·</span>
          {match.time}
          {match.status === 'LIVE' ? (
            <span className="num inline-flex items-center gap-1.5 rounded-sm border border-positive/30 bg-positive/10 px-1.5 py-0.5 text-[11px] font-medium text-positive">
              <span className="live-dot size-1.5 rounded-full bg-positive" aria-hidden />
              {`EN VIVO ${match.minute ?? 0}'`}
            </span>
          ) : (
            <span className="rounded-sm border border-border bg-muted/60 px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">
              {match.status === 'UPCOMING' ? 'POR JUGAR' : match.status}
            </span>
          )}
        </p>

        {/* Equipos */}
        <div className="mt-4 flex items-center gap-4">
          <div className="flex flex-1 items-center gap-3">
            <span
              className="flex size-10 shrink-0 items-center justify-center rounded-full border border-primary/30 bg-primary/10 text-sm font-semibold text-primary"
              aria-hidden
            >
              {match?.home?.charAt(0) || '?'}
            </span>
            <h1 className="font-serif text-xl leading-tight text-foreground">{match.home || 'Local'}</h1>
          </div>
          <span className="num shrink-0 text-sm text-subtle">vs</span>
          <div className="flex flex-1 items-center justify-end gap-3 text-right">
            <span className="font-serif text-xl leading-tight text-foreground">{match.away || 'Visitante'}</span>
            <span
              className="flex size-10 shrink-0 items-center justify-center rounded-full border border-warning/30 bg-warning/10 text-sm font-semibold text-warning"
              aria-hidden
            >
              {match?.away?.charAt(0) || '?'}
            </span>
          </div>
        </div>

        {/* Probabilidades 1X2 compactas */}
        <div className="mt-4 grid grid-cols-3 gap-2">
          {(
            [
              ['Local', model.home, 'text-primary'],
              ['Empate', model.draw, 'text-muted-foreground'],
              ['Visitante', model.away, 'text-warning'],
            ] as const
          ).map(([label, value, tone]) => (
            <div
              key={label}
              className="flex flex-col items-center gap-0.5 rounded-md border border-border bg-surface-inset py-2"
            >
              <span className="text-[10px] tracking-wide text-subtle uppercase">{label}</span>
              <span className={cn('num text-base font-semibold', tone)}>
                {`${(value * 100).toFixed(1)}%`}
              </span>
            </div>
          ))}
        </div>

        {/* Prediction confidence badge + tactical headline */}
        {hasPrediction && enriched && (
          <div className="mt-4 flex flex-col gap-2 rounded-lg border border-border bg-surface/50 p-3">
            <div className="flex items-center gap-2">
              <span className="num inline-flex items-center gap-1 rounded-md bg-primary/15 px-2 py-0.5 text-[10px] font-bold text-primary">
                {enriched.llmModelUsed}
              </span>
              <span className="num text-xs text-muted-foreground">
                Confianza: {enriched.confidenceScore}/100
              </span>
            </div>
            {enriched.tacticalHeadline && (
              <p className="text-xs leading-relaxed text-foreground">
                {enriched.tacticalHeadline}
              </p>
            )}
            {enriched.tacticalNarrative && (
              <p className="text-[11px] leading-relaxed text-subtle line-clamp-3">
                {enriched.tacticalNarrative}
              </p>
            )}
          </div>
        )}
      </div>

      {/* ── TAB BAR (sticky bajo el header de página) ── */}
      <MatchTabBar active={activeTab} onChange={setActiveTab} className="mt-0" />

      {/* ── CONTENIDO DE PESTAÑAS ── */}
      <div className="mt-5">
        {activeTab === 'preview' && (
          <PreviewTab match={match} model={model} rows={rows} best={best} />
        )}
        {activeTab === 'h2h' && <H2HTab match={match} />}
        {activeTab === 'referee' && <RefereeTab match={match} />}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function PartidoDetailPage() {
  const params = useParams<{ id: string }>()
  const [match, setMatch] = React.useState<Match | null>(null)
  const [enriched, setEnriched] = React.useState<EnrichedMatch | null>(null)
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState(false)

  React.useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        console.log(`[PartidoDetailPage] Fetching match ${params.id}...`)
        const result = await fetchMatchPrediction(params.id)
        if (!cancelled) {
          if (result) {
            console.log(
              `[PartidoDetailPage] Loaded: ${result.home} vs ${result.away} | ` +
              `λ ${result.lambdaHome}/${result.lambdaAway} | ` +
              `confidence: ${result.confidenceScore}`
            )
            setMatch(result)
            setEnriched(result)
          } else {
            console.warn(`[PartidoDetailPage] Match ${params.id} not found in API`)
            setError(true)
          }
        }
      } catch (e) {
        console.error(`[PartidoDetailPage] Error loading match ${params.id}:`, e)
        if (!cancelled) setError(true)
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [params.id])

  return (
    <div className="min-h-svh bg-background">
      {/* Sticky back bar */}
      <header className="sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur-md">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center gap-3 px-4">
          <Link
            href="/"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            <ArrowLeftIcon className="size-4" aria-hidden />
            Volver a Partidos
          </Link>

          {match && (
            <p className="ml-auto truncate text-sm font-medium text-foreground">
              {match.home} vs {match.away}
            </p>
          )}
        </div>
      </header>

      <div className="mx-auto w-full max-w-6xl px-4 py-6">
        {loading && <PageSkeleton />}
        {error && !loading && (
          <div className="rounded-xl border border-border bg-card p-10 text-center">
            <p className="text-sm font-medium text-foreground">Partido no encontrado</p>
            <p className="mt-1 text-xs text-subtle">
              Es posible que el partido ya no esté disponible para hoy.
            </p>
            <Link
              href="/"
              className="mt-4 inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline"
            >
              <ArrowLeftIcon className="size-4" aria-hidden />
              Volver al inicio
            </Link>
          </div>
        )}
        {match && !loading && <MatchDetailContent match={match} enriched={enriched} />}
      </div>
    </div>
  )
}
