import { goalDistribution } from '@/lib/betmind'
import { cn } from '@/lib/utils'

const BUCKETS = ['0', '1', '2', '3', '4+']

/** Keeps SVG geometry deterministic between server and client renders. */
const round = (n: number) => Math.round(n * 100) / 100

interface PoissonMiniChartProps {
  lambdaHome: number
  lambdaAway: number
  width?: number
  height?: number
  className?: string
}

/**
 * The signature visual: a mini Poisson goal-probability histogram.
 * Home bars render in indigo, away bars in amber.
 */
export function PoissonMiniChart({
  lambdaHome,
  lambdaAway,
  width = 120,
  height = 48,
  className,
}: PoissonMiniChartProps) {
  const home = goalDistribution(lambdaHome, 5)
  const away = goalDistribution(lambdaAway, 5)
  const max = Math.max(...home, ...away, 0.01)

  const labelBand = 8
  const plot = height - labelBand
  const groupWidth = width / BUCKETS.length
  const barWidth = (groupWidth - 6) / 2

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={cn('overflow-visible', className)}
      role="img"
      aria-label={`Goal probability distribution. Home expected goals ${lambdaHome.toFixed(2)}, away ${lambdaAway.toFixed(2)}.`}
    >
      <line
        x1={0}
        y1={plot + 0.5}
        x2={width}
        y2={plot + 0.5}
        stroke="var(--border)"
        strokeWidth={1}
      />
      {BUCKETS.map((bucket, i) => {
        const x = i * groupWidth + 1
        // Round to fixed precision so server and client serialise identically.
        const hHome = round(Math.max(1, (home[i] / max) * (plot - 2)))
        const hAway = round(Math.max(1, (away[i] / max) * (plot - 2)))
        return (
          <g key={bucket}>
            <rect
              x={x}
              y={plot - hHome}
              width={barWidth}
              height={hHome}
              rx={1}
              fill="var(--primary)"
              opacity={0.9}
            />
            <rect
              x={x + barWidth + 4}
              y={plot - hAway}
              width={barWidth}
              height={hAway}
              rx={1}
              fill="var(--warning)"
              opacity={0.75}
            />
            <text
              x={x + barWidth + 1}
              y={height - 0.5}
              textAnchor="middle"
              fontSize={6}
              fill="var(--subtle)"
            >
              {bucket}
            </text>
          </g>
        )
      })}
    </svg>
  )
}
