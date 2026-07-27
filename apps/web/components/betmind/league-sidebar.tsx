'use client'

import * as React from 'react'

import { cn } from '@/lib/utils'
import { fetchLeagues } from '@/lib/api'
import type { LeagueData } from '@/lib/api'
import { resolveLeague } from '@/lib/league-metadata'


interface LeagueSidebarProps {
  active: string
  onSelect: (leagueId: string) => void
}

function LeagueGroup({
  region,
  leagues,
  active,
  onSelect,
}: {
  region: 'EUROPE' | 'AMERICAS'
  leagues: LeagueData[]
  active: string
  onSelect: (id: string) => void
}) {
  const regionLabel = region === 'EUROPE' ? 'EUROPA' : 'AMÉRICA'
  return (
    <div className="flex flex-col gap-1">
      <p className="px-2 py-1 text-[10px] font-bold uppercase tracking-widest text-subtle">{regionLabel}</p>
      {leagues.map((league) => {
        const leagueId = String(league.external_id)
        const selected = active === leagueId
        const meta = resolveLeague(league.external_id, league.name)
        return (
          <button
            key={league.id}
            type="button"
            onClick={() => onSelect(leagueId)}
            aria-current={selected}
            className={cn(
              'group flex w-full items-center justify-between rounded-md px-2.5 py-1.5 text-left text-sm transition-colors',
              selected
                ? 'bg-primary/15 font-medium text-primary'
                : 'text-muted-foreground hover:bg-muted/80 hover:text-foreground',
            )}
          >
            <div className="flex items-center gap-2 min-w-0">
              <span aria-hidden className="text-sm leading-none shrink-0">
                {meta.flag}
              </span>
              <span className="truncate text-xs">{meta.name}</span>
            </div>
            <span
              className={cn(
                'num shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold',
                selected
                  ? 'bg-primary/20 text-primary'
                  : 'bg-muted text-subtle group-hover:text-muted-foreground',
              )}
            >
              {league.active_matches}
            </span>
          </button>
        )
      })}
    </div>
  )
}

export function LeagueSidebar({ active, onSelect }: LeagueSidebarProps) {
  const [leagues, setLeagues] = React.useState<LeagueData[]>([])
  const [loading, setLoading] = React.useState(true)

  React.useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const data = await fetchLeagues()
        if (!cancelled) setLeagues(data)
      } catch {
        // keep empty
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [])

  const europeLeagues = leagues.filter((l) => resolveLeague(l.external_id, l.name).region === 'EUROPE')
  const americasLeagues = leagues.filter((l) => resolveLeague(l.external_id, l.name).region === 'AMERICAS')

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <p className="px-2 text-[11px] font-bold uppercase tracking-widest text-subtle">Ligas Activas</p>
        <button
          type="button"
          onClick={() => onSelect('all')}
          aria-current={active === 'all'}
          className={cn(
            'w-full rounded-md px-3 py-2 text-left text-sm font-medium transition-colors',
            active === 'all'
              ? 'bg-primary text-primary-foreground shadow-sm'
              : 'text-muted-foreground hover:bg-muted/80 hover:text-foreground',
          )}
        >
          Todas las Ligas
        </button>
      </div>

      {loading ? (
        <div className="flex flex-col gap-2">
          {[0, 1, 2, 3, 4].map((i) => (
            <div key={i} className="h-8 animate-pulse rounded-md bg-muted" />
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-5">
          <LeagueGroup region="EUROPE" leagues={europeLeagues} active={active} onSelect={onSelect} />
          <LeagueGroup region="AMERICAS" leagues={americasLeagues} active={active} onSelect={onSelect} />
        </div>
      )}

      <div className="mt-2 flex flex-col gap-3 rounded-xl border border-border bg-card p-4">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-semibold text-foreground">Estado del Modelo</p>
          <span className="inline-flex items-center gap-1 rounded-full border border-positive/30 bg-positive/10 px-2 py-0.5 text-[10px] font-bold text-positive">
            <span className="live-dot size-1.5 rounded-full bg-positive" aria-hidden />
            CALIBRADO
          </span>
        </div>
        <dl className="flex flex-col gap-2">
          {[
            ['Ligas activas', `${leagues.length} hoy`],
            ['Partidos programados', `${leagues.reduce((sum, l) => sum + l.active_matches, 0)} hoy`],
          ].map(([label, value]) => (
            <div key={label} className="flex items-center justify-between gap-2">
              <dt className="text-xs text-subtle">{label}</dt>
              <dd className="num text-xs font-medium text-foreground">{value}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  )
}
