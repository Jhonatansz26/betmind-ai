import { cn } from '@/lib/utils'
import type { MatchModel, MarketRow } from '@/lib/betmind'
import { pct } from '@/lib/betmind'

export interface TrendPill {
  label: string
  type: 'positive' | 'warning' | 'neutral'
}

interface TrendPillsProps {
  pills: TrendPill[]
  /** Título de la sección. Default: "Tendencias del Partido" */
  title?: string
  className?: string
}

const PILL_STYLES: Record<TrendPill['type'], string> = {
  positive:
    'border-positive/25 bg-positive/10 text-positive',
  warning:
    'border-warning/25 bg-warning/10 text-warning',
  neutral:
    'border-border bg-muted/60 text-muted-foreground',
}

/**
 * TrendPills
 *
 * Renderiza un conjunto de badges compactos tipo píldora que destacan
 * tendencias del partido derivadas de los umbrales del modelo.
 *
 * La lógica de qué píldoras mostrar se calcula fuera del componente
 * (en page.tsx) mediante `buildTrendPills()`, manteniendo este componente
 * completamente agnóstico a la lógica de negocio.
 */
export function TrendPills({ pills, title = 'Tendencias del Partido', className }: TrendPillsProps) {
  if (pills.length === 0) return null

  return (
    <div className={cn('flex flex-col gap-2', className)}>
      <p className="text-[10px] font-semibold tracking-[0.10em] text-subtle uppercase">
        {title}
      </p>
      <div className="flex flex-wrap gap-1.5" role="list" aria-label={title}>
        {pills.map((pill, i) => (
          <span
            // eslint-disable-next-line react/no-array-index-key
            key={`${pill.label}-${i}`}
            role="listitem"
            className={cn(
              'inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-medium leading-none',
              PILL_STYLES[pill.type],
            )}
          >
            {pill.label}
          </span>
        ))}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Builder helper (usado en page.tsx)                                  */
/* ------------------------------------------------------------------ */

/**
 * Genera las píldoras de tendencia a partir del modelo Poisson calculado.
 * Todas las métricas provienen del modelo real — no se inventan valores.
 */
export function buildTrendPills(model: MatchModel, best: MarketRow | null): TrendPill[] {
  const pills: TrendPill[] = []

  if (model.over25 > 0.60)
    pills.push({ label: `Over 2.5 probable · ${pct(model.over25)}`, type: 'positive' })

  if (model.over25 < 0.35)
    pills.push({ label: `Under 2.5 probable · ${pct(1 - model.over25)}`, type: 'warning' })

  if (model.btts > 0.55)
    pills.push({ label: `Ambos anotan · ${pct(model.btts)}`, type: 'positive' })

  if (model.home > 0.55)
    pills.push({ label: `Local favorito · ${pct(model.home)}`, type: 'positive' })

  if (model.away > 0.45 && model.away > model.home)
    pills.push({ label: `Visitante favorito · ${pct(model.away)}`, type: 'warning' })
  else if (model.away > 0.35 && model.away > model.draw)
    pills.push({ label: `Visitante competitivo · ${pct(model.away)}`, type: 'warning' })

  if (best && best.edge > 0.05)
    pills.push({ label: `Edge alto detectado · +${(best.edge * 100).toFixed(1)}%`, type: 'positive' })

  if (pills.length === 0)
    pills.push({ label: 'Sin tendencias marcadas para este partido', type: 'neutral' })

  return pills
}
