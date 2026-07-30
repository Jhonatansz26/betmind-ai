'use client'

import * as React from 'react'
import { toast } from 'sonner'
import { cn } from '@/lib/utils'

interface BetBuilderSelection {
  market_name: string
  label: string
  probability: number
  odds_estimate: number
}

interface BetBuilderProfile {
  profile: string
  label: string
  selections: BetBuilderSelection[]
  combined_odds: number
  combined_probability: number
}

interface BetBuilderCardsProps {
  profiles: BetBuilderProfile[]
  homeTeam: string
  awayTeam: string
}

const PROFILE_CONFIG: Record<
  string,
  {
    gradient: string
    border: string
    badgeBg: string
    badgeText: string
    icon: string
    riskLabel: string
    oddsColor: string
    glowColor: string
  }
> = {
  CONSERVATIVE: {
    gradient: 'from-emerald-950/60 to-zinc-900/60',
    border: 'border-emerald-500/20',
    badgeBg: 'bg-emerald-500/15',
    badgeText: 'text-emerald-400',
    icon: '🛡️',
    riskLabel: 'BAJO RIESGO',
    oddsColor: 'text-emerald-400',
    glowColor: 'shadow-emerald-900/40',
  },
  MODERATE: {
    gradient: 'from-amber-950/60 to-zinc-900/60',
    border: 'border-amber-500/20',
    badgeBg: 'bg-amber-500/15',
    badgeText: 'text-amber-400',
    icon: '⚖️',
    riskLabel: 'RIESGO MEDIO',
    oddsColor: 'text-amber-400',
    glowColor: 'shadow-amber-900/40',
  },
  BOLD: {
    gradient: 'from-rose-950/60 to-zinc-900/60',
    border: 'border-rose-500/20',
    badgeBg: 'bg-rose-500/15',
    badgeText: 'text-rose-400',
    icon: '🔥',
    riskLabel: 'ALTO RIESGO',
    oddsColor: 'text-rose-400',
    glowColor: 'shadow-rose-900/40',
  },
  CAZADOR: {
    gradient: 'from-rose-950/60 to-zinc-900/60',
    border: 'border-rose-500/20',
    badgeBg: 'bg-rose-500/15',
    badgeText: 'text-rose-400',
    icon: '🎯',
    riskLabel: '+EV MÁXIMO',
    oddsColor: 'text-rose-400',
    glowColor: 'shadow-rose-900/40',
  },
}

function getConfig(profile: string) {
  const upper = profile.toUpperCase()
  return (
    PROFILE_CONFIG[upper] ??
    PROFILE_CONFIG[
      upper.includes('CONS') || upper.includes('CONSERV')
        ? 'CONSERVATIVE'
        : upper.includes('MOD')
          ? 'MODERATE'
          : 'BOLD'
    ] ??
    PROFILE_CONFIG.BOLD
  )
}

export function BetBuilderCards({ profiles, homeTeam, awayTeam }: BetBuilderCardsProps) {
  if (!profiles || profiles.length === 0) return null

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <span className="text-[11px] font-semibold tracking-widest text-zinc-400 uppercase">
          Bet Builder Sugerido
        </span>
        <span className="h-px flex-1 bg-white/[0.05]" />
        <span className="rounded-sm bg-[#6366f1]/15 px-1.5 py-0.5 text-[10px] font-medium text-[#a5b4fc]">
          IA · Groq
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        {profiles.map((profile) => {
          const cfg = getConfig(profile.profile)
          return (
            <div
              key={profile.profile}
              className={cn(
                'group relative flex flex-col gap-3 overflow-hidden rounded-xl border p-4 transition-all duration-200',
                `bg-gradient-to-b ${cfg.gradient}`,
                cfg.border,
                'hover:scale-[1.01] hover:shadow-lg',
                cfg.glowColor,
              )}
            >
              {/* Top badge row */}
              <div className="flex items-start justify-between gap-2">
                <div className="flex flex-col gap-1">
                  <span
                    className={cn(
                      'inline-flex w-fit items-center gap-1 rounded-sm px-1.5 py-0.5 text-[10px] font-semibold tracking-wider uppercase',
                      cfg.badgeBg,
                      cfg.badgeText,
                    )}
                  >
                    {cfg.icon} {cfg.riskLabel}
                  </span>
                  <span className="text-sm font-semibold text-zinc-100">{profile.label}</span>
                </div>
                {/* Combined odds */}
                <div className="flex flex-col items-end gap-0.5">
                  <span className="text-[10px] text-zinc-500">Cuota comb.</span>
                  <span className={cn('num text-xl font-bold', cfg.oddsColor)}>
                    {profile.combined_odds.toFixed(2)}
                  </span>
                </div>
              </div>

              {/* Selections */}
              <ul className="flex flex-col gap-1.5">
                {profile.selections.map((sel) => (
                  <li
                    key={sel.market_name}
                    className="flex items-center justify-between gap-2 rounded-md border border-white/[0.05] bg-black/20 px-2.5 py-1.5"
                  >
                    <span className="text-[11px] text-zinc-300 leading-tight">{sel.label}</span>
                    <span className="num shrink-0 text-[11px] font-medium text-zinc-400">
                      {sel.odds_estimate.toFixed(2)}
                    </span>
                  </li>
                ))}
              </ul>

              {/* Probability pill */}
              <div className="flex items-center justify-between">
                <span className="text-[10px] text-zinc-500">
                  Prob. comb. {(profile.combined_probability * 100).toFixed(0)}%
                </span>
                <button
                  type="button"
                  onClick={() =>
                    toast.success('Añadido al boleto', {
                      description: `${profile.label} · ${homeTeam} vs ${awayTeam}`,
                    })
                  }
                  className={cn(
                    'rounded-md px-2.5 py-1 text-[11px] font-semibold transition-all',
                    cfg.badgeBg,
                    cfg.badgeText,
                    'hover:brightness-125',
                  )}
                >
                  Copiar al boleto →
                </button>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
