'use client'

import * as React from 'react'
import { toast } from 'sonner'
import { CheckIcon, SparklesIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogTitle } from '@/components/ui/dialog'
import { Separator } from '@/components/ui/separator'
import {
  bestOpportunity,
  buildModel,
  marketRows,
  type Match,
  type Mode,
} from '@/lib/betmind'
import { fetchMatchPrediction, type EnrichedMatch } from '@/lib/api'
import { cn } from '@/lib/utils'
import { MarketTable } from './market-table'
import { ModeSelector } from './mode-selector'
import { PoissonModalChart } from './poisson-modal-chart'
import { RefereeWidget } from './referee-widget'
import { TacticalPanel } from './tactical-panel'

function SectionTitle({
  children,
  badge,
}: {
  children: React.ReactNode
  badge?: React.ReactNode
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-2">
      <h3 className="font-serif text-lg text-foreground">{children}</h3>
      {badge}
    </div>
  )
}

interface MatchModalProps {
  match: Match | null
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function MatchModal({ match, open, onOpenChange }: MatchModalProps) {
  const [selectedMarket, setSelectedMarket] = React.useState<string | null>(null)
  const [mode, setMode] = React.useState<Mode>('EDGE')
  const [enriched, setEnriched] = React.useState<EnrichedMatch | null>(null)

  React.useEffect(() => {
    if (open && match) {
      setSelectedMarket(null)
      setMode('EDGE')
      setEnriched(null)
      fetchMatchPrediction(match.id).then(setEnriched).catch(() => setEnriched(null))
    }
  }, [open, match?.id])

  const model = React.useMemo(
    () => (match ? buildModel(match.lambdaHome, match.lambdaAway) : null),
    [match],
  )
  const rows = React.useMemo(
    () => (match && model ? marketRows(match, model) : []),
    [match, model],
  )
  const best = React.useMemo(() => bestOpportunity(rows), [rows])
  const selectable = rows.filter((row) => row.edge > 0)

  if (!match || !model) return null

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] w-full overflow-y-auto border border-border bg-card p-0 sm:max-w-[680px]">
        {/* HEADER */}
        <div className="sticky top-0 z-10 flex flex-col gap-4 border-b border-border bg-card p-5 pr-12">
          <p className="flex flex-wrap items-center gap-2 text-xs text-subtle">
            <span aria-hidden>{match.flag}</span>
            {match.league}
            <span aria-hidden>·</span>
            {match.time}
            {match.status === 'LIVE' ? (
              <span className="num inline-flex items-center gap-1.5 rounded-sm border border-positive/30 bg-positive/10 px-1.5 py-0.5 text-[11px] font-medium text-positive">
                <span className="live-dot size-1.5 rounded-full bg-positive" aria-hidden />
                {`EN VIVO ${match.minute}'`}
              </span>
            ) : (
              <span className="rounded-sm border border-border bg-muted/60 px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">
                {match.status === 'UPCOMING' ? 'POR JUGAR' : match.status}
              </span>
            )}
          </p>

          <div className="flex items-center gap-4">
            <div className="flex flex-1 items-center gap-3">
              <span
                className="flex size-10 shrink-0 items-center justify-center rounded-full border border-primary/30 bg-primary/10 text-sm font-semibold text-primary"
                aria-hidden
              >
                {match.home.charAt(0)}
              </span>
              <DialogTitle className="font-serif text-xl leading-tight text-foreground">
                {match.home}
              </DialogTitle>
            </div>
            <span className="num text-sm text-subtle">vs</span>
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

          <div className="grid grid-cols-3 gap-2">
            {(
              [
                ['Home', model.home, 'text-primary'],
                ['Draw', model.draw, 'text-muted-foreground'],
                ['Away', model.away, 'text-warning'],
              ] as const
            ).map(([label, value, tone]) => (
              <div
                key={label}
                className="flex flex-col items-center gap-0.5 rounded-md border border-border bg-background/40 py-2"
              >
                <span className="text-[10px] tracking-wide text-subtle uppercase">{label}</span>
                <span className={cn('num text-base font-semibold', tone)}>
                  {`${(value * 100).toFixed(1)}%`}
                </span>
              </div>
            ))}
          </div>
        </div>

        <div className="flex flex-col gap-6 p-5">
          {/* SECTION 1 — Poisson */}
          <section className="flex flex-col gap-3">
            <SectionTitle>Modelo de Probabilidad de Goles (Poisson)</SectionTitle>
            <PoissonModalChart
              lambdaHome={match.lambdaHome}
              lambdaAway={match.lambdaAway}
              homeLabel={match.home}
              awayLabel={match.away}
            />
            <div className="flex flex-col gap-2 rounded-lg border border-border bg-background/40 p-3">
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
          </section>

          <Separator />

          {/* SECTION 2 — EV */}
          <section className="flex flex-col gap-3">
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
          </section>

          <Separator />

          {/* SECTION 3 — Tactical */}
          <section className="flex flex-col gap-3">
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
          </section>

          <Separator />

          {/* SECTION 4 — Referee */}
          <section className="flex flex-col gap-3">
            <SectionTitle
              badge={
                <span className="text-xs text-muted-foreground">{match.referee.name}</span>
              }
            >
              Perfil del Árbitro
            </SectionTitle>
            <RefereeWidget referee={match.referee} />
          </section>

          <Separator />

          {/* SECTION 5 — Add to ticket */}
          <section className="flex flex-col gap-3">
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
                            : 'border-border bg-background/40 hover:border-primary/30',
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
              <p className="rounded-md border border-border bg-background/40 p-3 text-sm text-muted-foreground">
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
                onOpenChange(false)
              }}
            >
              Añadir al Boleto
            </Button>
          </section>

          {/* Bet Builder desde predicción enriquecida */}
          {enriched?.betBuilder && enriched.betBuilder.length > 0 && (
            <section className="flex flex-col gap-3 rounded-xl border border-border bg-card p-4">
              <SectionTitle>Bet Builder Sugerido</SectionTitle>
              <div className="flex flex-col gap-3">
                {enriched.betBuilder.map((profile) => (
                  <div
                    key={profile.profile}
                    className="rounded-lg border border-border bg-surface-inset p-3"
                  >
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-semibold text-foreground">
                        {profile.label}
                      </span>
                      <span className="num text-xs text-muted-foreground">
                        Cuota comb: {profile.combined_odds.toFixed(2)}
                      </span>
                    </div>
                    <ul className="mt-2 flex flex-col gap-1">
                      {profile.selections.map((sel) => (
                        <li key={sel.market_name} className="flex items-center justify-between text-xs">
                          <span className="text-subtle">{sel.label}</span>
                          <span className="num text-muted-foreground">
                            {sel.odds_estimate.toFixed(2)}
                          </span>
                        </li>
                      ))}
                    </ul>
                    <Button
                      size="sm"
                      variant="outline"
                      className="mt-2 w-full text-xs"
                      onClick={() => {
                        toast.success('Añadido al boleto', {
                          description: `${profile.label} · ${match.home} vs ${match.away}`,
                        })
                      }}
                    >
                      Copiar al Boleto
                    </Button>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>
      </DialogContent>
    </Dialog>
  )
}
