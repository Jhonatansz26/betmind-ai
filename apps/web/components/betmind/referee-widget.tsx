'use client'

import * as React from 'react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'
import type { Referee } from '@/lib/betmind'

/* ------------------------------------------------------------------ */
/* Helpers                                                              */
/* ------------------------------------------------------------------ */

function strictnessLabel(score: number): { label: string; color: string } {
  if (score >= 70) return { label: 'Muy estricto', color: 'text-rose-400' }
  if (score >= 45) return { label: 'Moderado', color: 'text-amber-400' }
  return { label: 'Permisivo', color: 'text-emerald-400' }
}

function strictnessBarColor(score: number): string {
  if (score >= 70) return 'from-rose-500 to-rose-400'
  if (score >= 45) return 'from-amber-500 to-amber-400'
  return 'from-emerald-500 to-emerald-400'
}

/* ------------------------------------------------------------------ */
/* Empty / Pending State                                                */
/* ------------------------------------------------------------------ */

function RefereePending() {
  const [notified, setNotified] = React.useState(false)

  // Context stats — shown regardless of referee assignment
  const contextStats = [
    { icon: '🟨', label: 'Tarjetas prom. Liga', value: '4.2', sub: 'por partido' },
    { icon: '🟥', label: 'Rojas prom. Liga', value: '0.3', sub: 'por partido' },
    { icon: '⚽', label: 'Faltas prom. liga', value: '22.1', sub: 'por partido' },
  ]

  return (
    <div className="flex flex-col gap-5">
      {/* Pending slot */}
      <div className="flex flex-col items-center gap-4 rounded-xl border border-dashed border-white/[0.08] bg-white/[0.015] py-8 px-6">
        {/* Animated avatar placeholder */}
        <div className="relative flex size-16 items-center justify-center rounded-full border border-white/[0.08] bg-zinc-800/60">
          <svg
            className="size-7 text-zinc-600"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
            aria-hidden
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"
            />
          </svg>
          {/* Pulse ring */}
          <span className="absolute inset-0 rounded-full border border-[#6366f1]/30 animate-ping opacity-40" />
          <span className="absolute inset-[-3px] rounded-full border border-[#6366f1]/15" />
        </div>

        <div className="flex flex-col items-center gap-1 text-center">
          <p className="text-sm font-semibold text-zinc-300">Árbitro pendiente de confirmación</p>
          <p className="text-xs text-zinc-500 max-w-[240px]">
            Normalmente se confirma{' '}
            <span className="text-zinc-400 font-medium">4–6 horas</span> antes del partido
          </p>
        </div>

        <button
          type="button"
          onClick={() => {
            setNotified(true)
            toast.success('Notificación activada', {
              description: 'Te avisaremos cuando se confirme el árbitro de este partido.',
            })
          }}
          disabled={notified}
          className={cn(
            'flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-semibold transition-all',
            notified
              ? 'border border-emerald-500/30 bg-emerald-500/10 text-emerald-400 cursor-default'
              : 'border border-[#6366f1]/40 bg-[#6366f1]/15 text-[#a5b4fc] hover:bg-[#6366f1]/25 hover:scale-[1.02]',
          )}
        >
          {notified ? (
            <>
              <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
              Notificación activada
            </>
          ) : (
            <>
              <svg className="size-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1.5}
                  d="M14.857 17.082a23.848 23.848 0 005.454-1.31A8.967 8.967 0 0118 9.75v-.7V9A6 6 0 006 9v.75a8.967 8.967 0 01-2.312 6.022c1.733.64 3.56 1.085 5.455 1.31m5.714 0a24.255 24.255 0 01-5.714 0m5.714 0a3 3 0 11-5.714 0"
                />
              </svg>
              Notificarme cuando se confirme
            </>
          )}
        </button>
      </div>

      {/* Context stats — always visible */}
      <div className="flex flex-col gap-2">
        <p className="text-[11px] font-semibold tracking-widest text-zinc-400 uppercase">
          Contexto de la Liga
        </p>
        <div className="grid grid-cols-3 gap-2">
          {contextStats.map((stat) => (
            <div
              key={stat.label}
              className="flex flex-col items-center gap-1 rounded-xl border border-white/[0.05] bg-white/[0.02] py-3 px-2 text-center"
            >
              <span className="text-xl">{stat.icon}</span>
              <span className="num text-base font-bold text-zinc-100">{stat.value}</span>
              <span className="text-[10px] text-zinc-500 leading-tight">{stat.label}</span>
              <span className="text-[9px] text-zinc-600">{stat.sub}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Tip */}
      <p className="rounded-lg border border-[#6366f1]/15 bg-[#6366f1]/[0.04] px-4 py-3 text-[11px] leading-relaxed text-zinc-400">
        💡 <span className="font-medium text-zinc-300">Consejo:</span> En este mercado, el árbitro
        puede mover las cuotas de tarjetas hasta un{' '}
        <span className="font-semibold text-[#a5b4fc]">15–25%</span>. Espera la confirmación antes
        de apostar en mercados de disciplina.
      </p>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Assigned Referee State                                               */
/* ------------------------------------------------------------------ */

function RefereeProfile({ referee }: { referee: Referee }) {
  const sl = strictnessLabel(referee.strictness)
  const barColor = strictnessBarColor(referee.strictness)

  const kpis = [
    { icon: '🟨', label: 'Amarillas / partido', value: referee.yellows.toFixed(1) },
    { icon: '🟥', label: 'Rojas / partido', value: referee.reds.toFixed(2) },
    { icon: '🦵', label: 'Faltas cobradas', value: referee.fouls.toFixed(1) },
    { icon: '⚡', label: 'Partidos clave', value: referee.highStakes.toFixed(1) },
  ]

  return (
    <div className="flex flex-col gap-5">
      {/* Header */}
      <div className="flex items-center gap-4 rounded-xl border border-white/[0.05] bg-white/[0.02] p-4">
        <div className="flex size-12 shrink-0 items-center justify-center rounded-full border border-white/[0.08] bg-zinc-800/80 text-lg font-bold text-zinc-300">
          {referee.name.charAt(0).toUpperCase()}
        </div>
        <div className="flex flex-col gap-0.5">
          <p className="font-semibold text-zinc-100">{referee.name}</p>
          <p className="text-xs text-zinc-500">
            Tendencia reciente:{' '}
            <span className="font-medium text-zinc-300">{referee.trend}</span>
          </p>
        </div>
        <div className="ml-auto flex flex-col items-end gap-0.5">
          <span className={cn('text-xs font-semibold', sl.color)}>{sl.label}</span>
          <span className="num text-[10px] text-zinc-500">Estrictez {referee.strictness}/100</span>
        </div>
      </div>

      {/* KPI grid */}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {kpis.map((k) => (
          <div
            key={k.label}
            className="flex flex-col items-center gap-1 rounded-xl border border-white/[0.05] bg-white/[0.02] py-3 px-2 text-center"
          >
            <span className="text-xl">{k.icon}</span>
            <span className="num text-lg font-bold text-zinc-100">{k.value}</span>
            <span className="text-[10px] text-zinc-500 leading-tight">{k.label}</span>
          </div>
        ))}
      </div>

      {/* Strictness bar */}
      <div className="flex flex-col gap-2">
        <div className="flex items-center justify-between text-xs">
          <span className="text-zinc-500">Índice de Estrictez</span>
          <span className={cn('num font-semibold', sl.color)}>
            {referee.strictness}/100 · {sl.label}
          </span>
        </div>
        <div
          className="h-2 w-full overflow-hidden rounded-full bg-zinc-800"
          role="meter"
          aria-valuenow={referee.strictness}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Índice de estrictez de ${referee.name}`}
        >
          <div
            className={cn('h-full rounded-full bg-gradient-to-r transition-all', barColor)}
            style={{ width: `${referee.strictness}%` }}
          />
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* Export                                                               */
/* ------------------------------------------------------------------ */

export function RefereeWidget({ referee }: { referee: Referee }) {
  const isPending = referee.name === 'Por confirmar'
  return isPending ? <RefereePending /> : <RefereeProfile referee={referee} />
}
