import type { Impact, Match, TacticalFactor } from '@/lib/betmind'
import { cn } from '@/lib/utils'

const IMPACT_STYLES: Record<Impact, string> = {
  HIGH: 'border-positive/30 bg-positive/10 text-positive',
  MEDIUM: 'border-warning/30 bg-warning/10 text-warning',
  LOW: 'border-border bg-muted/60 text-muted-foreground',
}

const IMPACT_LABEL: Record<Impact, string> = {
  HIGH: 'ALTO',
  MEDIUM: 'MEDIO',
  LOW: 'BAJO',
}

const CATEGORY_LABEL: Record<string, string> = {
  FORMA: 'FORMA',
  FORM: 'FORMA',
  ESTADÍSTICA: 'ESTADÍSTICA',
  STATISTICS: 'ESTADÍSTICA',
  H2H: 'H2H',
  CONTEXTO: 'CONTEXTO',
  CONTEXT: 'CONTEXTO',
  ÁRBITRO: 'ÁRBITRO',
  REFEREE: 'ÁRBITRO',
}

function FactorRow({ item, tone }: { item: TacticalFactor; tone: 'pro' | 'con' }) {
  const categoryLabel = CATEGORY_LABEL[item.category] ?? item.category
  return (
    <li className="flex flex-col gap-1.5 rounded-md border border-border bg-background/40 p-3">
      <div className="flex items-center justify-between gap-2">
        <span
          className={cn(
            'rounded-sm border px-1.5 py-0.5 text-[10px] font-medium tracking-wide',
            tone === 'pro'
              ? 'border-positive/25 bg-positive/5 text-positive'
              : 'border-warning/25 bg-warning/5 text-warning',
          )}
        >
          {categoryLabel}
        </span>
        <span
          className={cn(
            'rounded-sm border px-1.5 py-0.5 text-[10px] font-medium',
            IMPACT_STYLES[item.impact],
          )}
        >
          {IMPACT_LABEL[item.impact]}
        </span>
      </div>
      <p className="text-pretty text-sm leading-relaxed text-foreground">{item.factor}</p>
    </li>
  )
}

const SIGNAL_DOTS: Record<Match['signal'], number> = { STRONG: 3, MODERATE: 2, WEAK: 1 }

const SIGNAL_LABEL: Record<Match['signal'], string> = {
  STRONG: 'FUERTE',
  MODERATE: 'MODERADA',
  WEAK: 'DÉBIL',
}

export function TacticalPanel({ match }: { match: Match }) {
  const filled = SIGNAL_DOTS[match.signal]

  return (
    <div className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-2">
          <h4 className="text-xs font-semibold tracking-wide text-positive">PROS</h4>
          <ul className="flex flex-col gap-2">
            {match.pros.map((item) => (
              <FactorRow key={item.factor} item={item} tone="pro" />
            ))}
          </ul>
        </div>
        <div className="flex flex-col gap-2">
          <h4 className="text-xs font-semibold tracking-wide text-warning">CONTRAS</h4>
          <ul className="flex flex-col gap-2">
            {match.cons.map((item) => (
              <FactorRow key={item.factor} item={item} tone="con" />
            ))}
          </ul>
        </div>
      </div>

      <div className="flex flex-col gap-2 rounded-lg border border-border bg-background/40 p-3">
        <p className="flex items-center gap-2 text-xs font-medium tracking-wide text-foreground">
          {`Señal: ${SIGNAL_LABEL[match.signal]}`}
          <span className="flex items-center gap-1" aria-hidden>
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className={cn(
                  'size-1.5 rounded-full',
                  i < filled ? 'bg-primary' : 'bg-border',
                )}
              />
            ))}
          </span>
        </p>
        <p className="text-sm leading-relaxed text-muted-foreground">
          <span className="font-medium text-foreground">Riesgo Clave: </span>
          {match.keyRisk}
        </p>
        <p className="text-sm leading-relaxed text-muted-foreground">
          <span className="font-medium text-foreground">Resumen Táctico: </span>
          {match.summary}
        </p>
      </div>
    </div>
  )
}
