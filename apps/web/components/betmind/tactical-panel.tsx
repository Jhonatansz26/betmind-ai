import type { Match, TacticalFactor } from '@/lib/betmind'
import { cn } from '@/lib/utils'

function StatBar({ label, home, away }: { label: string; home: number; away: number }) {
  const total = home + away
  const homeWidth = total > 0 ? (home / total) * 100 : 50
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="font-mono font-semibold tabular-nums text-foreground">{home.toFixed(2)}</span>
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</span>
        <span className="font-mono font-semibold tabular-nums text-foreground">{away.toFixed(2)}</span>
      </div>
      <div className="flex h-1.5 overflow-hidden rounded-full bg-surface-inset">
        <div className="bg-primary" style={{ width: `${homeWidth}%` }} />
        <div className="bg-warning" style={{ width: `${100 - homeWidth}%` }} />
      </div>
    </div>
  )
}

function FactorList({ title, factors }: { title: string; factors: TacticalFactor[] }) {
  if (!factors.length) return null
  return (
    <section className="border-t border-border/50 pt-3">
      <h3 className="text-xs font-mono uppercase tracking-wider text-muted-foreground">{title}</h3>
      <ul className="mt-2 flex flex-col divide-y divide-border/40">
        {factors.map((factor) => (
          <li key={`${factor.category}-${factor.factor}`} className="flex items-start justify-between gap-3 py-2 first:pt-0 last:pb-0">
            <div className="min-w-0"><span className="font-mono text-[9px] uppercase text-muted-foreground">{factor.category}</span><p className="mt-0.5 text-xs leading-relaxed text-foreground/90">{factor.factor}</p></div>
            <span className="shrink-0 rounded border border-border/60 bg-surface px-1.5 py-0.5 text-[9px] font-mono font-semibold uppercase text-muted-foreground">{factor.impact}</span>
          </li>
        ))}
      </ul>
    </section>
  )
}

interface TacticalMetadata {
  llm_model_used?: string | null
  data_completeness_score?: number | null
  generation_tokens_used?: number | null
  match_preview_headline?: string | null
  goals_narrative?: string | null
  cards_narrative?: string | null
  corners_narrative?: string | null
  player_props_narrative?: string | null
}

export function TacticalPanel({ match, analysis }: { match: Match; analysis?: TacticalMetadata | null }) {
  const totalGoals = match.lambdaHome + match.lambdaAway
  const rhythm = totalGoals < 2 ? 'Ritmo contenido' : totalGoals < 3 ? 'Ritmo moderado' : 'Ritmo abierto'
  const narratives = [
    ['Goles', analysis?.goals_narrative],
    ['Tarjetas', analysis?.cards_narrative],
    ['Córneres', analysis?.corners_narrative],
    ['Proposiciones de jugador', analysis?.player_props_narrative],
  ].filter((item): item is [string, string] => typeof item[1] === 'string' && item[1].length > 0)
  return (
    <div className="flex flex-col gap-4 rounded-xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border/50 pb-3 text-[10px] font-mono text-muted-foreground">
        <span>MODELO: {analysis?.llm_model_used || 'QUANT ENGINE'}</span><span>COMPLETITUD DE DATOS: {analysis?.data_completeness_score != null ? `${(analysis.data_completeness_score * 100).toFixed(0)}%` : 'N/A'}</span><span>TOKENS: {analysis?.generation_tokens_used || 0}</span>
      </div>
      <div>
        <h2 className="text-base font-bold tracking-tight text-foreground">{analysis?.match_preview_headline || `Lectura táctica de ${match.home} vs ${match.away}`}</h2>
        <p className="mt-1 text-xs text-muted-foreground">{match.league} · Señal {match.signal.toLowerCase()}</p>
      </div>
      <section className="flex flex-col gap-3">
        <h3 className="text-xs font-mono uppercase tracking-wider text-muted-foreground">Modelo cuantitativo</h3>
        <StatBar label="Goles esperados" home={match.lambdaHome} away={match.lambdaAway} />
        <StatBar label="Total de goles" home={totalGoals} away={totalGoals} />
        <p className="border-t border-border/40 pt-2 text-xs leading-relaxed text-foreground/90">{rhythm}. {match.summary || 'Sin narrativa adicional disponible.'}</p>
      </section>
      {narratives.map(([title, narrative]) => (
        <section key={title} className="border-t border-border/50 pt-3">
          <h3 className="text-xs font-mono uppercase tracking-wider text-muted-foreground">{title}</h3>
          <p className="mt-2 text-xs leading-relaxed text-foreground/90">{narrative}</p>
        </section>
      ))}
      {(match.pros.length > 0 || match.cons.length > 0) && (
        <div className="grid gap-4 sm:grid-cols-2">
          <FactorList title="A favor" factors={match.pros} />
          <FactorList title="En contra" factors={match.cons} />
        </div>
      )}
      {match.keyRisk && <p className={cn('border-t border-border/50 pt-3 text-xs leading-relaxed text-foreground/90')}><span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Riesgo clave · </span>{match.keyRisk}</p>}
    </div>
  )
}
