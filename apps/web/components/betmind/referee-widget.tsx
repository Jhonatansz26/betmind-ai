import type { Referee } from '@/lib/betmind'

export function RefereeWidget({ referee }: { referee: Referee }) {
  const stats = [
    { label: 'Prom. Tarjetas Amarillas', value: referee.yellows.toFixed(1) },
    { label: 'Prom. Tarjetas Rojas', value: referee.reds.toFixed(2) },
    { label: 'Prom. Faltas Cobradas', value: referee.fouls.toFixed(1) },
    { label: 'Índice de Estrictez', value: `${referee.strictness}/100` },
    { label: 'Prom. Partidos Clave', value: referee.highStakes.toFixed(1) },
    { label: 'Tendencia Reciente', value: referee.trend },
  ]

  return (
    <div className="flex flex-col gap-3">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
        {stats.map((stat) => (
          <div
            key={stat.label}
            className="flex flex-col gap-1 rounded-md border border-border bg-background/40 p-3"
          >
            <span className="text-[10px] tracking-wide text-subtle uppercase">{stat.label}</span>
            <span className="num text-sm font-medium text-foreground">{stat.value}</span>
          </div>
        ))}
      </div>

      <div className="flex flex-col gap-1.5">
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Medidor de estrictez</span>
          <span className="num">{referee.strictness}</span>
        </div>
        <div
          className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
          role="meter"
          aria-valuenow={referee.strictness}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Índice de estrictez de ${referee.name}`}
        >
          <div
            className="h-full rounded-full bg-gradient-to-r from-primary to-warning"
            style={{ width: `${referee.strictness}%` }}
          />
        </div>
      </div>
    </div>
  )
}
