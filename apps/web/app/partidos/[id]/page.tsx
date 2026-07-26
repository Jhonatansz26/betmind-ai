'use client'

import * as React from 'react'
import Link from 'next/link'
import { useParams } from 'next/navigation'
import { ArrowLeftIcon, SparklesIcon } from 'lucide-react'
import { toast } from 'sonner'
import { CheckIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Separator } from '@/components/ui/separator'
import {
  bestOpportunity,
  buildModel,
  marketRows,
  type Match,
  type Mode,
} from '@/lib/betmind'
import { fetchMatches } from '@/lib/api'
import { cn } from '@/lib/utils'
import { MarketTable } from '@/components/betmind/market-table'
import { ModeSelector } from '@/components/betmind/mode-selector'
import { PoissonModalChart } from '@/components/betmind/poisson-modal-chart'
import { RefereeWidget } from '@/components/betmind/referee-widget'
import { TacticalPanel } from '@/components/betmind/tactical-panel'

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
      <h2 className="text-base font-semibold text-foreground">{children}</h2>
      {badge}
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Skeleton                                                            */
/* ------------------------------------------------------------------ */

function PageSkeleton() {
  return (
    <div className="flex flex-col gap-6">
      <div className="h-32 animate-pulse rounded-xl bg-card" />
      <div className="h-48 animate-pulse rounded-xl bg-card" />
      <div className="h-64 animate-pulse rounded-xl bg-card" />
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Match detail content                                                */
/* ------------------------------------------------------------------ */

function MatchDetailContent({ match }: { match: Match }) {
  const [selectedMarket, setSelectedMarket] = React.useState<string | null>(null)
  const [mode, setMode] = React.useState<Mode>('EDGE')

  const model = React.useMemo(() => buildModel(match.lambdaHome, match.lambdaAway), [match])
  const rows = React.useMemo(() => marketRows(match, model), [match, model])
  const best = React.useMemo(() => bestOpportunity(rows), [rows])
  const selectable = rows.filter((row) => row.edge > 0)

  return (
    <div className="flex flex-col gap-6">
      {/* ── HEADER ── */}
      <div className="rounded-xl border border-border bg-card p-5">
        {/* Meta row */}
        <p className="flex flex-wrap items-center gap-2 text-xs text-subtle">
          <span aria-hidden>{match.flag}</span>
          {match.league}
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

        {/* Teams */}
        <div className="mt-4 flex items-center gap-4">
          <div className="flex flex-1 items-center gap-3">
            <span
              className="flex size-10 shrink-0 items-center justify-center rounded-full border border-primary/30 bg-primary/10 text-sm font-semibold text-primary"
              aria-hidden
            >
              {match.home.charAt(0)}
            </span>
            <h1 className="font-serif text-xl leading-tight text-foreground">{match.home}</h1>
          </div>
          <span className="num shrink-0 text-sm text-subtle">vs</span>
          <div className="flex flex-1 items-center justify-end gap-3 text-right">
            <span className="font-serif text-xl leading-tight text-foreground">{match.away}</span>
            <span
              className="flex size-10 shrink-0 items-center justify-center rounded-full border border-warning/30 bg-warning/10 text-sm font-semibold text-warning"
              aria-hidden
            >
              {match.away.charAt(0)}
            </span>
          </div>
        </div>

        {/* 1X2 model probabilities */}
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

        {/* Best opportunity banner */}
        {best && (
          <div className="mt-3 flex items-center gap-2 rounded-md border border-positive/30 bg-positive/10 px-3 py-2">
            <span className="num text-sm font-semibold text-positive">EV+</span>
            <span className="text-xs text-positive">
              Mejor oportunidad: {best.label} · +{(best.edge * 100).toFixed(1)}% edge
            </span>
          </div>
        )}
      </div>

      {/* ── SECTION 1 — Poisson ── */}
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex flex-col gap-4">
          <SectionTitle>Modelo de Probabilidad de Goles (Poisson)</SectionTitle>
          <PoissonModalChart
            lambdaHome={match.lambdaHome}
            lambdaAway={match.lambdaAway}
            homeLabel={match.home}
            awayLabel={match.away}
          />
          <div className="flex flex-col gap-2 rounded-lg border border-border bg-surface-inset p-3">
            <p className="text-xs font-medium tracking-wide text-subtle uppercase">
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
        </div>
      </div>

      <Separator />

      {/* ── SECTION 2 — EV ── */}
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex flex-col gap-4">
          <SectionTitle>Análisis de Valor Esperado (+EV)</SectionTitle>
          <MarketTable rows={rows} />
          <p className="text-sm text-muted-foreground">
            {best ? (
              <>
                <span className="font-medium text-foreground">Mejor oportunidad: </span>
                {`${best.label} · +${(best.edge * 100).toFixed(1)}% edge sobre probabilidad implícita del mercado`}
              </>
            ) : (
              'Ningún mercado supera el umbral de 3% de edge en este partido.'
            )}
          </p>
        </div>
      </div>

      <Separator />

      {/* ── SECTION 3 — Tactical ── */}
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex flex-col gap-4">
          <SectionTitle
            badge={
              <span className="inline-flex items-center gap-1.5 rounded-sm border border-border bg-muted/60 px-1.5 py-0.5 text-[10px] text-muted-foreground">
                <SparklesIcon className="size-3" aria-hidden />
                Potenciado por Groq · Llama 3.3
              </span>
            }
          >
            Análisis Táctico
          </SectionTitle>
          <TacticalPanel match={match} />
        </div>
      </div>

      <Separator />

      {/* ── SECTION 4 — Referee ── */}
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex flex-col gap-4">
          <SectionTitle badge={<span className="text-xs text-muted-foreground">{match.referee.name}</span>}>
            Perfil del Árbitro
          </SectionTitle>
          <RefereeWidget referee={match.referee} />
        </div>
      </div>

      <Separator />

      {/* ── SECTION 5 — Select market ── */}
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="flex flex-col gap-4">
          <SectionTitle>Seleccionar Mercado</SectionTitle>
          {selectable.length > 0 ? (
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
          ) : (
            <p className="rounded-md border border-border bg-surface-inset p-3 text-sm text-muted-foreground">
              No hay mercados con edge positivo disponibles para este partido.
            </p>
          )}

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
        </div>
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
  const [loading, setLoading] = React.useState(true)
  const [error, setError] = React.useState(false)

  React.useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const todayCot = new Date()
        const dateStr = todayCot.toLocaleDateString('en-CA', { timeZone: 'America/Bogota' })
        const all = await fetchMatches(dateStr)
        const found = all.find((m) => m.id === params.id) ?? null
        if (!cancelled) setMatch(found)
        if (!cancelled && !found) setError(true)
      } catch {
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
        <div className="mx-auto flex h-14 w-full max-w-3xl items-center gap-3 px-4">
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

      <div className="mx-auto w-full max-w-3xl px-4 py-6">
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
        {match && !loading && <MatchDetailContent match={match} />}
      </div>
    </div>
  )
}
