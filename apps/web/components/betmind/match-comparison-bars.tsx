import { cn } from '@/lib/utils'

export interface ComparisonStat {
  /** Nombre de la métrica — "Victoria Local" */
  label: string
  /** Valor entre 0 y 1 para el equipo local */
  home: number
  /** Valor entre 0 y 1 para el equipo visitante */
  away: number
  /** Siempre 'percent' — datos reales del modelo son probabilidades */
  format: 'percent'
}

interface MatchComparisonBarsProps {
  homeLabel: string
  awayLabel: string
  /** Array de métricas a comparar. Solo probabilidades reales del backend. */
  stats: ComparisonStat[]
  className?: string
}

function formatValue(value: number, format: ComparisonStat['format']): string {
  if (format === 'percent') return `${(value * 100).toFixed(1)}%`
  return value.toFixed(2)
}

/**
 * MatchComparisonBars
 *
 * Barras comparativas horizontales centradas, estilo SofaScore/ValueStats.
 * Layout: [ Valor Local | ████░░ | Métrica | ░░████ | Valor Visitante ]
 *
 * Las barras crecen desde el centro hacia los extremos.
 * El ancho es proporcional al ratio: home/(home+away) y away/(home+away),
 * lo que garantiza que siempre sumen el 100% disponible.
 *
 * IMPORTANTE: Solo acepta probabilidades reales del modelo (0–1).
 * No se renderizan valores inventados o derivados de forma heurística.
 */
export function MatchComparisonBars({
  homeLabel,
  awayLabel,
  stats,
  className,
}: MatchComparisonBarsProps) {
  if (stats.length === 0) return null

  return (
    <div className={cn('flex flex-col gap-0', className)}>
      {/* Header de equipos */}
      <div className="mb-3 grid grid-cols-[1fr_auto_1fr] items-center gap-x-3">
        <span className="truncate text-left text-[11px] font-semibold text-primary">
          {homeLabel}
        </span>
        <span className="w-[110px] text-center text-[10px] font-semibold tracking-[0.10em] text-subtle uppercase">
          Probabilidades
        </span>
        <span className="truncate text-right text-[11px] font-semibold text-warning">
          {awayLabel}
        </span>
      </div>

      {/* Filas de métricas */}
      <div className="flex flex-col divide-y divide-border/50">
        {stats.map((stat) => {
          const total = stat.home + stat.away
          // Evitar división por cero — si ambos son 0, mostrar barras vacías iguales
          const homeRatio = total > 0 ? stat.home / total : 0.5
          const awayRatio = total > 0 ? stat.away / total : 0.5

          // Porcentaje visual de barra (min 4% para que siempre sea visible)
          const homeBarPct = Math.max(homeRatio * 100, 4)
          const awayBarPct = Math.max(awayRatio * 100, 4)

          return (
            <div
              key={stat.label}
              className="grid grid-cols-[1fr_110px_1fr] items-center gap-x-3 py-2.5"
            >
              {/* Local: valor + barra (barra crece hacia la derecha del extremo izquierdo) */}
              <div className="flex items-center justify-end gap-2">
                <span className="num shrink-0 text-xs font-semibold tabular-nums text-foreground">
                  {formatValue(stat.home, stat.format)}
                </span>
                <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-muted/50">
                  <div
                    className="absolute right-0 h-full rounded-full bg-primary transition-all duration-500"
                    style={{ width: `${homeBarPct}%` }}
                    aria-hidden
                  />
                </div>
              </div>

              {/* Label de métrica centrado */}
              <span className="text-center text-[10px] tracking-wide text-subtle uppercase">
                {stat.label}
              </span>

              {/* Visitante: barra + valor (barra crece hacia la derecha) */}
              <div className="flex items-center gap-2">
                <div className="relative h-1.5 w-full overflow-hidden rounded-full bg-muted/50">
                  <div
                    className="absolute left-0 h-full rounded-full bg-warning transition-all duration-500"
                    style={{ width: `${awayBarPct}%` }}
                    aria-hidden
                  />
                </div>
                <span className="num shrink-0 text-xs font-semibold tabular-nums text-foreground">
                  {formatValue(stat.away, stat.format)}
                </span>
              </div>
            </div>
          )
        })}
      </div>

      {/* Nota al pie */}
      <p className="mt-2 text-[10px] text-subtle/70">
        Basado en el modelo cuantitativo Poisson calibrado con datos reales.
      </p>
    </div>
  )
}
