import { Activity, AlertTriangle, Check, Database, Gauge, Sparkles } from 'lucide-react'
import type { Match, TacticalFactor } from '@/lib/betmind'
import { cn } from '@/lib/utils'
import { formatPercent, formatxG } from '@/lib/formatters'

function StatBar({ label, home, away }: { label: string; home: number; away: number }) {
  const total = home + away
  const homeWidth = total > 0 ? (home / total) * 100 : 50
  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="font-mono font-semibold tabular-nums text-foreground">{formatxG(home)}</span>
        <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</span>
        <span className="font-mono font-semibold tabular-nums text-foreground">{formatxG(away)}</span>
      </div>
      <div className="flex h-1.5 overflow-hidden rounded-full bg-surface-inset"><div className="bg-primary transition-[width] duration-300 ease-out" style={{ width: `${homeWidth}%` }} /><div className="bg-warning transition-[width] duration-300 ease-out" style={{ width: `${100 - homeWidth}%` }} /></div>
    </div>
  )
}

function FactorList({ title, factors }: { title: string; factors: TacticalFactor[] }) {
  if (!factors.length) return null
  return (
    <section className="border-t border-border/50 pt-4">
      <h3 className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.14em] text-muted-foreground">{title === 'A favor' ? <Check className="size-3 text-positive" /> : <AlertTriangle className="size-3 text-warning" />}{title}</h3>
      <ul className="mt-2 flex flex-col divide-y divide-border/40">
        {factors.map((factor) => (
          <li key={`${factor.category}-${factor.factor}`} className="group/insight flex items-start justify-between gap-3 rounded-md py-2 first:pt-0 last:pb-0 hover:bg-primary/[0.04]">
            <div className="min-w-0"><span className="font-mono text-[9px] uppercase text-muted-foreground">{factor.category}</span><p className="mt-0.5 text-xs leading-relaxed text-foreground/90">{factor.factor}</p></div>
            <span className={cn('shrink-0 rounded border px-1.5 py-0.5 text-[9px] font-mono font-semibold uppercase transition-colors', factor.impact === 'HIGH' ? 'border-positive/30 bg-positive/10 text-positive' : factor.impact === 'MEDIUM' ? 'border-warning/30 bg-warning/10 text-warning' : 'border-border/60 bg-surface text-muted-foreground')}>{factor.impact === 'HIGH' ? 'ALTA' : factor.impact === 'MEDIUM' ? 'MEDIA' : 'BAJA'}</span>
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
  confidence_score?: number | null
  risk_level?: string | null
}

export function TacticalPanel({ match, analysis }: { match: Match; analysis?: TacticalMetadata | null }) {
  const totalGoals = match.lambdaHome + match.lambdaAway
  const rhythm = totalGoals < 2 ? 'Ritmo contenido' : totalGoals < 3 ? 'Ritmo moderado' : 'Ritmo abierto'
  const confidence = Math.max(0, Math.min(100, analysis?.confidence_score ?? 0))
  const risk = (analysis?.risk_level ?? 'MEDIUM').toUpperCase()
  const narratives = [['Goles', analysis?.goals_narrative], ['Tarjetas', analysis?.cards_narrative], ['Córneres', analysis?.corners_narrative], ['Proposiciones de jugador', analysis?.player_props_narrative]].filter((item): item is [string, string] => typeof item[1] === 'string' && item[1].length > 0)
  return (
    <div className="relative flex flex-col gap-5 overflow-hidden rounded-2xl border border-border bg-card p-5 shadow-[inset_0_1px_0_rgba(255,255,255,0.03)]">
      <div className="pointer-events-none absolute right-0 top-0 h-32 w-32 rounded-full bg-primary/10 blur-3xl" aria-hidden="true" />
      <div className="relative flex flex-wrap items-center justify-between gap-2 border-b border-border/50 pb-3 text-[10px] font-mono text-muted-foreground"><span className="flex items-center gap-1.5"><Database className="size-3 text-primary" /> MODELO: {analysis?.llm_model_used || 'QUANT ENGINE'}</span><span>COMPLETITUD: {analysis?.data_completeness_score != null ? formatPercent(analysis.data_completeness_score, 0) : 'N/D'}</span><span>{analysis?.generation_tokens_used ? `${analysis.generation_tokens_used} TOKENS` : 'SEÑAL EN VIVO'}</span></div>
      <div className="relative grid gap-5 lg:grid-cols-[minmax(0,1fr)_220px] lg:items-center">
        <div><p className="mb-2 flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.14em] text-primary"><Sparkles className="size-3" /> Memorándum cuantitativo</p><h2 className="text-xl font-bold tracking-tight text-foreground">{analysis?.match_preview_headline || `Lectura táctica de ${match.home} vs ${match.away}`}</h2><p className="mt-1 text-xs text-muted-foreground">{match.league} · Señal {match.signal.toLowerCase()}</p></div>
        <div className="rounded-xl border border-primary/20 bg-primary/[0.06] p-3"><div className="flex items-center justify-between gap-2"><span className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-wider text-muted-foreground"><Gauge className="size-3 text-primary" /> Confianza IA</span><span className="font-mono text-sm font-bold tabular-nums text-primary">{confidence || '—'}<span className="text-[10px] text-muted-foreground">/100</span></span></div><div className="mt-3 h-1.5 overflow-hidden rounded-full bg-surface-inset"><div className="h-full rounded-full bg-primary transition-[width] duration-500 ease-out" style={{ width: `${confidence}%` }} /></div><p className="mt-2 text-[10px] text-muted-foreground">Riesgo <span className={risk === 'LOW' ? 'text-positive' : risk === 'HIGH' ? 'text-negative' : 'text-warning'}>{risk === 'LOW' ? 'bajo' : risk === 'HIGH' ? 'alto' : 'medio'}</span></p></div>
      </div>
      <section className="flex flex-col gap-3"><h3 className="flex items-center gap-2 text-[10px] font-mono uppercase tracking-[0.14em] text-muted-foreground"><Activity className="size-3 text-primary" /> Lectura rápida del modelo</h3><StatBar label="Goles esperados" home={match.lambdaHome} away={match.lambdaAway} /><StatBar label="Total de goles" home={totalGoals} away={totalGoals} /><p className="border-t border-border/40 pt-3 text-xs leading-relaxed text-foreground/90">{rhythm}. {match.summary || 'Sin narrativa adicional disponible.'}</p></section>
      {narratives.map(([title, narrative]) => <section key={title} className="border-t border-border/50 pt-3"><h3 className="text-[10px] font-mono uppercase tracking-[0.14em] text-muted-foreground">{title}</h3><p className="mt-2 text-xs leading-relaxed text-foreground/90">{narrative}</p></section>)}
      {(match.pros.length > 0 || match.cons.length > 0) && <div className="grid gap-4 sm:grid-cols-2"><FactorList title="A favor" factors={match.pros} /><FactorList title="En contra" factors={match.cons} /></div>}
      {match.keyRisk && <p className="border-t border-border/50 pt-3 text-xs leading-relaxed text-foreground/90"><span className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">Riesgo clave · </span>{match.keyRisk}</p>}
    </div>
  )
}
