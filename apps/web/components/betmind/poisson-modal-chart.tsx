'use client'

import * as React from 'react'
import { goalDistribution } from '@/lib/betmind'

const BUCKETS = ['0', '1', '2', '3', '4', '5+']

const round = (n: number) => Math.round(n * 100) / 100

const W = 620
const H = 210
const PAD_L = 34
const PAD_R = 8
const PAD_T = 12
const PAD_B = 26

interface PoissonModalChartProps {
  lambdaHome: number
  lambdaAway: number
  homeLabel: string
  awayLabel: string
}

interface TooltipState {
  visible: boolean
  x: number
  y: number
  text: string
}

export function PoissonModalChart({
  lambdaHome,
  lambdaAway,
  homeLabel,
  awayLabel,
}: PoissonModalChartProps) {
  const home = goalDistribution(lambdaHome, 6)
  const away = goalDistribution(lambdaAway, 6)
  const rawMax = Math.max(...home, ...away)
  const max = Math.ceil((rawMax * 100) / 10) * 10

  const plotW = W - PAD_L - PAD_R
  const plotH = H - PAD_T - PAD_B
  const groupW = plotW / BUCKETS.length
  const barW = (groupW - 18) / 2

  const ticks = [0, max / 2, max]

  const containerRef = React.useRef<HTMLDivElement>(null)
  const [tooltip, setTooltip] = React.useState<TooltipState>({
    visible: false,
    x: 0,
    y: 0,
    text: '',
  })

  function handleBarHover(
    e: React.MouseEvent<SVGRectElement>,
    team: string,
    prob: number,
    goals: string,
  ) {
    const container = containerRef.current
    if (!container) return
    const rect = container.getBoundingClientRect()
    const svgEl = container.querySelector('svg')
    if (!svgEl) return
    const svgRect = svgEl.getBoundingClientRect()
    const scaleX = svgRect.width / W
    const scaleY = svgRect.height / H
    const svgX = e.clientX - svgRect.left
    const svgY = e.clientY - svgRect.top
    setTooltip({
      visible: true,
      x: svgX / scaleX,
      y: svgY / scaleY - 12,
      text: `${team}: ${(prob * 100).toFixed(1)}% prob. exactly ${goals} goals`,
    })
  }

  function handleBarLeave() {
    setTooltip((prev) => ({ ...prev, visible: false }))
  }

  return (
    <div ref={containerRef} className="relative flex flex-col gap-3">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-auto w-full"
        role="img"
        aria-label="Grouped bar chart of goal probability by team"
      >
        {ticks.map((t) => {
          const y = PAD_T + plotH - (t / max) * plotH
          return (
            <g key={t}>
              <line
                x1={PAD_L}
                y1={y}
                x2={W - PAD_R}
                y2={y}
                stroke="var(--border)"
                strokeWidth={1}
                strokeDasharray={t === 0 ? undefined : '3 4'}
              />
              <text x={PAD_L - 8} y={y + 3} textAnchor="end" fontSize={9} fill="var(--subtle)">
                {`${t.toFixed(0)}%`}
              </text>
            </g>
          )
        })}

        {BUCKETS.map((bucket, i) => {
          const gx = PAD_L + i * groupW + (groupW - (barW * 2 + 4)) / 2
          const hh = round(((home[i] * 100) / max) * plotH)
          const ha = round(((away[i] * 100) / max) * plotH)
          return (
            <g key={bucket}>
              <rect
                x={gx}
                y={PAD_T + plotH - hh}
                width={barW}
                height={Math.max(1, hh)}
                rx={2}
                fill="var(--primary)"
                className="cursor-pointer transition-opacity hover:opacity-80"
                onMouseMove={(e) => handleBarHover(e, homeLabel, home[i], bucket)}
                onMouseLeave={handleBarLeave}
              />
              <text
                x={gx + barW / 2}
                y={PAD_T + plotH - hh - 4}
                textAnchor="middle"
                fontSize={9}
                fill="var(--muted-foreground)"
                className="pointer-events-none"
              >
                {(home[i] * 100).toFixed(0)}
              </text>
              <rect
                x={gx + barW + 4}
                y={PAD_T + plotH - ha}
                width={barW}
                height={Math.max(1, ha)}
                rx={2}
                fill="var(--warning)"
                className="cursor-pointer transition-opacity hover:opacity-80"
                onMouseMove={(e) => handleBarHover(e, awayLabel, away[i], bucket)}
                onMouseLeave={handleBarLeave}
              />
              <text
                x={gx + barW + 4 + barW / 2}
                y={PAD_T + plotH - ha - 4}
                textAnchor="middle"
                fontSize={9}
                fill="var(--muted-foreground)"
                className="pointer-events-none"
              >
                {(away[i] * 100).toFixed(0)}
              </text>
              <text
                x={PAD_L + i * groupW + groupW / 2}
                y={H - 8}
                textAnchor="middle"
                fontSize={10}
                fill="var(--subtle)"
              >
                {bucket}
              </text>
            </g>
          )
        })}

        {tooltip.visible && (
          <g className="pointer-events-none">
            <rect
              x={tooltip.x - tooltip.text.length * 3}
              y={tooltip.y - 14}
              width={tooltip.text.length * 6}
              height={20}
              rx={4}
              fill="var(--foreground)"
              opacity={0.95}
            />
            <text
              x={tooltip.x}
              y={tooltip.y}
              textAnchor="middle"
              fontSize={9}
              fontWeight={500}
              fill="var(--background)"
            >
              {tooltip.text}
            </text>
          </g>
        )}
      </svg>

      <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-2">
          <span className="size-2.5 rounded-sm bg-primary" aria-hidden />
          {homeLabel}
        </span>
        <span className="flex items-center gap-2">
          <span className="size-2.5 rounded-sm bg-warning" aria-hidden />
          {awayLabel}
        </span>
        <span className="text-subtle">goals scored</span>
        <span className="num ml-auto text-subtle">
          {`Expected Goals — Home: λ ${lambdaHome.toFixed(2)} · Away: λ ${lambdaAway.toFixed(2)}`}
        </span>
      </div>
    </div>
  )
}
