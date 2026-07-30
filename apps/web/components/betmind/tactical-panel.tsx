import type { Match } from '@/lib/betmind'
import { cn } from '@/lib/utils'

/* ------------------------------------------------------------------ */
/* Form Streak                                                          */
/* ------------------------------------------------------------------ */

const MOCK_FORM: Record<string, ('W' | 'D' | 'L')[]> = {}

// Derive a deterministic pseudo-form from the match signal for demo purposes
function deriveForm(signal: Match['signal'], isHome: boolean): ('W' | 'D' | 'L')[] {
  if (signal === 'STRONG') return isHome ? ['W', 'W', 'D', 'W', 'W'] : ['L', 'W', 'D', 'L', 'W']
  if (signal === 'MODERATE') return isHome ? ['W', 'D', 'W', 'L', 'D'] : ['D', 'W', 'L', 'D', 'W']
  return isHome ? ['D', 'L', 'W', 'D', 'L'] : ['W', 'D', 'L', 'W', 'D']
}

const RESULT_STYLE: Record<'W' | 'D' | 'L', string> = {
  W: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30',
  D: 'bg-zinc-700/60 text-zinc-300 border border-zinc-600/40',
  L: 'bg-rose-500/20 text-rose-400 border border-rose-500/30',
}

const RESULT_LABEL: Record<'W' | 'D' | 'L', string> = { W: 'V', D: 'E', L: 'D' }

function FormStreak({
  form,
  label,
  align = 'left',
}: {
  form: ('W' | 'D' | 'L')[]
  label: string
  align?: 'left' | 'right'
}) {
  return (
    <div
      className={cn(
        'flex flex-col gap-2',
        align === 'right' && 'items-end',
      )}
    >
      <span className="text-[10px] font-semibold tracking-wider text-zinc-400 uppercase">
        {label}
      </span>
      <div className={cn('flex gap-1', align === 'right' && 'flex-row-reverse')}>
        {form.map((r, i) => (
          <span
            key={i}
            className={cn(
              'flex size-6 items-center justify-center rounded-md text-[11px] font-bold',
              RESULT_STYLE[r],
            )}
          >
            {RESULT_LABEL[r]}
          </span>
        ))}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Stat Comparison Bar                                                  */
/* ------------------------------------------------------------------ */

function StatBar({
  label,
  homeVal,
  awayVal,
  homeColor = 'bg-[#6366f1]',
  awayColor = 'bg-[#f59e0b]',
  format = (v: number) => v.toFixed(2),
}: {
  label: string
  homeVal: number
  awayVal: number
  homeColor?: string
  awayColor?: string
  format?: (v: number) => string
}) {
  const total = homeVal + awayVal
  const homeW = total > 0 ? (homeVal / total) * 100 : 50
  const awayW = total > 0 ? (awayVal / total) * 100 : 50

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center justify-between text-[11px]">
        <span className="num font-semibold text-[#a5b4fc]">{format(homeVal)}</span>
        <span className="text-zinc-500 tracking-wide">{label}</span>
        <span className="num font-semibold text-[#fbbf24]">{format(awayVal)}</span>
      </div>
      <div className="flex h-1.5 overflow-hidden rounded-full bg-zinc-800">
        <div
          className={cn('h-full rounded-l-full transition-all', homeColor)}
          style={{ width: `${homeW}%` }}
        />
        <div
          className={cn('h-full rounded-r-full transition-all', awayColor)}
          style={{ width: `${awayW}%` }}
        />
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Tactical Tags                                                        */
/* ------------------------------------------------------------------ */

const CATEGORY_ICON: Record<string, string> = {
  FORM: '📈',
  FORMA: '📈',
  H2H: '⚔️',
  STATISTICS: '📊',
  ESTADÍSTICA: '📊',
  CONTEXT: '🌍',
  CONTEXTO: '🌍',
  REFEREE: '🟨',
  ÁRBITRO: '🟨',
}

const IMPACT_BADGE: Record<string, string> = {
  HIGH: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-400',
  MEDIUM: 'border-amber-500/30 bg-amber-500/10 text-amber-400',
  LOW: 'border-zinc-600/40 bg-zinc-800/60 text-zinc-400',
}

const IMPACT_LABEL: Record<string, string> = {
  HIGH: 'ALTO',
  MEDIUM: 'MEDIO',
  LOW: 'BAJO',
}

const SIGNAL_DOTS: Record<Match['signal'], number> = { STRONG: 3, MODERATE: 2, WEAK: 1 }
const SIGNAL_LABEL: Record<Match['signal'], string> = {
  STRONG: 'FUERTE',
  MODERATE: 'MODERADA',
  WEAK: 'DÉBIL',
}
const SIGNAL_COLOR: Record<Match['signal'], string> = {
  STRONG: 'text-emerald-400',
  MODERATE: 'text-amber-400',
  WEAK: 'text-zinc-400',
}

/* ------------------------------------------------------------------ */
/* Main Component                                                       */
/* ------------------------------------------------------------------ */

export function TacticalPanel({ match }: { match: Match }) {
  const homeForm = deriveForm(match.signal, true)
  const awayForm = deriveForm(match.signal, false)
  const signalDots = SIGNAL_DOTS[match.signal]
  const hasPros = match.pros.length > 0
  const hasCons = match.cons.length > 0

  return (
    <div className="flex flex-col gap-5">

      {/* ── FORMA RECIENTE ── */}
      <div className="rounded-xl border border-white/[0.05] bg-white/[0.02] p-4">
        <p className="mb-3 text-[11px] font-semibold tracking-widest text-zinc-400 uppercase">
          Forma Reciente · Últimos 5
        </p>
        <div className="flex items-center justify-between gap-4">
          <FormStreak form={homeForm} label={match.home} align="left" />
          <div className="flex flex-col items-center gap-1">
            <span className="text-[10px] text-zinc-600">vs</span>
          </div>
          <FormStreak form={awayForm} label={match.away} align="right" />
        </div>
      </div>

      {/* ── COMPARATIVA ESTADÍSTICA ── */}
      <div className="rounded-xl border border-white/[0.05] bg-white/[0.02] p-4">
        <div className="mb-3 flex items-center justify-between">
          <p className="text-[11px] font-semibold tracking-widest text-zinc-400 uppercase">
            Modelo Cuantitativo
          </p>
          <div className="flex items-center gap-3 text-[10px]">
            <span className="flex items-center gap-1 text-[#a5b4fc]">
              <span className="h-2 w-2 rounded-sm bg-[#6366f1]" />
              {match.home}
            </span>
            <span className="flex items-center gap-1 text-[#fbbf24]">
              <span className="h-2 w-2 rounded-sm bg-[#f59e0b]" />
              {match.away}
            </span>
          </div>
        </div>
        <div className="flex flex-col gap-3">
          <StatBar
            label="Goles Esperados"
            homeVal={match.lambdaHome}
            awayVal={match.lambdaAway}
          />
          <StatBar
            label="Total Goles"
            homeVal={match.lambdaHome}
            awayVal={match.lambdaAway}
            format={() => `${(match.lambdaHome + match.lambdaAway).toFixed(2)} tot.`}
          />
        </div>

        {/* Rhythm tag */}
        <div className="mt-3 flex flex-wrap gap-2">
          {match.lambdaHome + match.lambdaAway < 2 && (
            <span className="rounded-full border border-blue-500/30 bg-blue-500/10 px-3 py-1 text-[11px] font-medium text-blue-300">
              🔒 Duelo cerrado
            </span>
          )}
          {match.lambdaHome + match.lambdaAway >= 2 && match.lambdaHome + match.lambdaAway < 3 && (
            <span className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-[11px] font-medium text-amber-300">
              ⚡ Ritmo moderado
            </span>
          )}
          {match.lambdaHome + match.lambdaAway >= 3 && (
            <span className="rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1 text-[11px] font-medium text-emerald-300">
              🔥 Partido abierto
            </span>
          )}
          {match.lambdaHome > match.lambdaAway * 1.5 && (
            <span className="rounded-full border border-[#6366f1]/30 bg-[#6366f1]/10 px-3 py-1 text-[11px] font-medium text-[#a5b4fc]">
              🏠 Local dominante
            </span>
          )}
          {match.lambdaAway > match.lambdaHome * 1.5 && (
            <span className="rounded-full border border-[#f59e0b]/30 bg-[#f59e0b]/10 px-3 py-1 text-[11px] font-medium text-amber-300">
              ✈️ Visitante superior
            </span>
          )}
        </div>
      </div>

      {/* ── SEÑAL + RIESGO ── */}
      <div className="rounded-xl border border-white/[0.05] bg-white/[0.02] p-4">
        <div className="mb-2 flex items-center gap-3">
          <span
            className={cn(
              'text-[11px] font-bold tracking-widest uppercase',
              SIGNAL_COLOR[match.signal],
            )}
          >
            Señal {SIGNAL_LABEL[match.signal]}
          </span>
          <span className="flex items-center gap-1" aria-hidden>
            {[0, 1, 2].map((i) => (
              <span
                key={i}
                className={cn(
                  'size-2 rounded-full transition-colors',
                  i < signalDots ? 'bg-[#6366f1]' : 'bg-zinc-700',
                )}
              />
            ))}
          </span>
        </div>
        {match.keyRisk && (
          <p className="mb-1.5 text-sm leading-relaxed text-zinc-400">
            <span className="font-semibold text-zinc-200">Riesgo Clave: </span>
            {match.keyRisk}
          </p>
        )}
        {match.summary && (
          <p className="text-sm leading-relaxed text-zinc-500">
            <span className="font-medium text-zinc-300">Resumen: </span>
            {match.summary}
          </p>
        )}
      </div>

      {/* ── PROS / CONTRAS ── */}
      {(hasPros || hasCons) && (
        <div className="grid gap-3 sm:grid-cols-2">
          {hasPros && (
            <div className="flex flex-col gap-2">
              <h4 className="text-[11px] font-semibold tracking-widest text-emerald-400 uppercase">
                ✅ A Favor
              </h4>
              <ul className="flex flex-col gap-2">
                {match.pros.map((item) => (
                  <li
                    key={item.factor}
                    className="flex flex-col gap-1.5 rounded-lg border border-emerald-500/10 bg-emerald-500/[0.04] p-3"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] text-zinc-500">
                        {CATEGORY_ICON[item.category] ?? '📌'} {item.category}
                      </span>
                      <span
                        className={cn(
                          'rounded-sm border px-1.5 py-0.5 text-[10px] font-medium',
                          IMPACT_BADGE[item.impact],
                        )}
                      >
                        {IMPACT_LABEL[item.impact]}
                      </span>
                    </div>
                    <p className="text-xs leading-relaxed text-zinc-300">{item.factor}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {hasCons && (
            <div className="flex flex-col gap-2">
              <h4 className="text-[11px] font-semibold tracking-widest text-rose-400 uppercase">
                ⚠️ En Contra
              </h4>
              <ul className="flex flex-col gap-2">
                {match.cons.map((item) => (
                  <li
                    key={item.factor}
                    className="flex flex-col gap-1.5 rounded-lg border border-rose-500/10 bg-rose-500/[0.04] p-3"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-[10px] text-zinc-500">
                        {CATEGORY_ICON[item.category] ?? '📌'} {item.category}
                      </span>
                      <span
                        className={cn(
                          'rounded-sm border px-1.5 py-0.5 text-[10px] font-medium',
                          IMPACT_BADGE[item.impact],
                        )}
                      >
                        {IMPACT_LABEL[item.impact]}
                      </span>
                    </div>
                    <p className="text-xs leading-relaxed text-zinc-300">{item.factor}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
