'use client'

import * as React from 'react'
import { poissonPmf } from '@/lib/betmind'
import { cn } from '@/lib/utils'

interface ScoreHeatmapProps {
  lambdaHome: number
  lambdaAway: number
  homeLabel: string
  awayLabel: string
  topScores?: { score: string; probability: number }[]
}

const MAX_GOALS = 4 // 0-4 goals per axis → 5x5 grid

function cellProb(lambdaH: number, lambdaA: number, h: number, a: number): number {
  return poissonPmf(lambdaH, h) * poissonPmf(lambdaA, a)
}

function interpolateColor(prob: number, maxProb: number): string {
  const t = Math.min(prob / (maxProb * 0.9), 1) // normalize
  // From cool indigo/dark → vivid indigo
  const r = Math.round(30 + t * (99 - 30))
  const g = Math.round(30 + t * (102 - 30))
  const b = Math.round(60 + t * (241 - 60))
  const a = 0.12 + t * 0.78
  return `rgba(${r},${g},${b},${a})`
}

export function ScoreHeatmap({
  lambdaHome,
  lambdaAway,
  homeLabel,
  awayLabel,
  topScores,
}: ScoreHeatmapProps) {
  const [hovered, setHovered] = React.useState<{ h: number; a: number } | null>(null)

  const grid: { h: number; a: number; prob: number }[][] = []
  let maxProb = 0

  for (let h = 0; h <= MAX_GOALS; h++) {
    grid[h] = []
    for (let a = 0; a <= MAX_GOALS; a++) {
      const prob = cellProb(lambdaHome, lambdaAway, h, a)
      if (prob > maxProb) maxProb = prob
      grid[h][a] = { h, a, prob }
    }
  }

  const top3 = topScores?.slice(0, 3) ?? []

  return (
    <div className="flex flex-col gap-4">
      {/* Heat map grid */}
      <div className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-[11px] font-semibold tracking-widest text-[#6366f1]/80 uppercase">
            Mapa de Marcadores
          </p>
          <p className="text-[10px] text-zinc-500">Hover para probabilidad exacta</p>
        </div>

        {/* Column headers (Away goals) */}
        <div className="flex flex-col gap-0.5">
          <div className="flex gap-0.5">
            {/* corner spacer */}
            <div className="flex w-8 shrink-0 items-center justify-center" />
            {/* away goal labels */}
            {Array.from({ length: MAX_GOALS + 1 }, (_, a) => (
              <div
                key={a}
                className="flex h-6 flex-1 items-center justify-center rounded-sm bg-warning/10"
              >
                <span className="text-[10px] font-semibold text-warning">{a}</span>
              </div>
            ))}
          </div>

          {/* Rows: home goals (row header) + cells */}
          {Array.from({ length: MAX_GOALS + 1 }, (_, h) => (
            <div key={h} className="flex gap-0.5">
              {/* Row header: home goals */}
              <div className="flex w-8 shrink-0 items-center justify-center rounded-sm bg-primary/10">
                <span className="text-[10px] font-semibold text-primary">{h}</span>
              </div>
              {Array.from({ length: MAX_GOALS + 1 }, (_, a) => {
                const cell = grid[h][a]
                const isHovered = hovered?.h === h && hovered?.a === a
                const isTop = top3.some((s) => s.score === `${h}-${a}`)
                const pct = (cell.prob * 100).toFixed(1)
                return (
                  <div
                    key={a}
                    className={cn(
                      'flex flex-1 aspect-square items-center justify-center rounded-sm cursor-default transition-all duration-150',
                      isTop && 'ring-1 ring-inset ring-[#6366f1]/60',
                      isHovered && 'scale-110 z-10 ring-1 ring-inset ring-white/30',
                    )}
                    style={{ background: interpolateColor(cell.prob, maxProb) }}
                    onMouseEnter={() => setHovered({ h, a })}
                    onMouseLeave={() => setHovered(null)}
                  >
                    {isHovered ? (
                      <span className="text-[10px] font-bold text-white drop-shadow">{pct}%</span>
                    ) : isTop ? (
                      <span className="text-[10px] font-semibold text-[#a5b4fc]">{pct}%</span>
                    ) : (
                      <span className="text-[9px] text-zinc-600">{pct}%</span>
                    )}
                  </div>
                )
              })}
            </div>
          ))}

          {/* Axis labels */}
          <div className="mt-1 flex gap-0.5">
            <div className="w-8 shrink-0" />
            <div className="flex flex-1 justify-center">
              <span className="text-[10px] font-medium text-warning/70">
                Goles {awayLabel} (Visitante) →
              </span>
            </div>
          </div>
        </div>

        {/* Side legend */}
        <div className="mt-0.5 flex items-center gap-2 justify-end">
          <span className="text-[10px] font-medium text-primary/70">
            ↑ Goles {homeLabel} (Local)
          </span>
        </div>
      </div>

      {/* Top scores */}
      {top3.length > 0 && (
        <div className="grid grid-cols-3 gap-2">
          {top3.map((s, idx) => (
            <div
              key={s.score}
              className={cn(
                'flex flex-col items-center gap-1 rounded-lg border py-3 transition-colors',
                idx === 0
                  ? 'border-[#6366f1]/40 bg-[#6366f1]/10'
                  : 'border-white/[0.06] bg-white/[0.02]',
              )}
            >
              {idx === 0 && (
                <span className="text-[9px] font-semibold tracking-widest text-[#6366f1] uppercase">
                  + Probable
                </span>
              )}
              <span className="num text-lg font-bold text-zinc-100">{s.score}</span>
              <span className="num text-xs text-zinc-400">
                {(s.probability * 100).toFixed(1)}%
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Legend: team colors */}
      <div className="flex items-center gap-6 text-[11px] text-zinc-500">
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm bg-primary" />
          {homeLabel} (filas)
        </span>
        <span className="flex items-center gap-1.5">
          <span className="h-2.5 w-2.5 rounded-sm bg-warning" />
          {awayLabel} (columnas)
        </span>
        <span className="ml-auto">Intensidad = probabilidad</span>
      </div>
    </div>
  )
}
