'use client'

import * as React from 'react'

import { cn } from '@/lib/utils'
import type { Match } from '@/lib/betmind'
import { resolveLeague } from '@/lib/league-metadata'


interface LeagueSidebarProps {
  active: string
  onSelect: (leagueId: string) => void
  matches: Match[]
}

function LeagueGroup({
  region,
  items,
  active,
  onSelect,
}: {
  region: 'EUROPE' | 'AMERICAS'
  items: { leagueId: string; name: string; count: number; flag: string; region: string }[]
  active: string
  onSelect: (id: string) => void
}) {
  const regionLabel = region === 'EUROPE' ? 'EUROPA' : 'AMERICA'
  return (
    <div className="flex flex-col gap-1">
      <p className="px-2 py-1 text-[10px] font-bold uppercase tracking-widest text-subtle">{regionLabel}</p>
      {items.map((item) => {
        const selected = active === item.leagueId
        return (
          <button
            key={item.leagueId}
            type="button"
            onClick={() => onSelect(item.leagueId)}
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
                {item.flag}
              </span>
              <span className="truncate text-xs">{item.name}</span>
            </div>
            <span
              className={cn(
                'num shrink-0 rounded px-1.5 py-0.5 text-[10px] font-semibold',
                selected
                  ? 'bg-primary/20 text-primary'
                  : 'bg-muted text-subtle group-hover:text-muted-foreground',
              )}
            >
              {item.count}
            </span>
          </button>
        )
      })}
    </div>
  )
}

export function LeagueSidebar({ active, onSelect, matches }: LeagueSidebarProps) {
  const sidebarLeagues = React.useMemo(() => {
    const countMap = new Map<string, { leagueId: string; name: string; shortName: string; count: number; flag: string; region: string }>()

    for (const m of matches) {
      const lid = String(m.leagueExternalId ?? 'other')
      if (!countMap.has(lid)) {
        const meta = resolveLeague(m.leagueExternalId, m.league)
        countMap.set(lid, {
          leagueId: lid,
          name: meta.shortName,
          shortName: meta.shortName,
          count: 0,
          flag: meta.flag,
          region: meta.region,
        })
      }
      countMap.get(lid)!.count++
    }

    return Array.from(countMap.values())
      .filter((l) => l.count > 0)
      .sort((a, b) => b.count - a.count)
  }, [matches])

  const europeLeagues = sidebarLeagues.filter((l) => l.region === 'EUROPE')
  const americasLeagues = sidebarLeagues.filter((l) => l.region === 'AMERICAS')

  const totalMatches = matches.length

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
          Todas las Ligas ({totalMatches})
        </button>
      </div>

      <div className="flex flex-col gap-5">
        {europeLeagues.length > 0 && (
          <LeagueGroup region="EUROPE" items={europeLeagues} active={active} onSelect={onSelect} />
        )}
        {americasLeagues.length > 0 && (
          <LeagueGroup region="AMERICAS" items={americasLeagues} active={active} onSelect={onSelect} />
        )}
      </div>

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
            ['Ligas activas', `${sidebarLeagues.length} hoy`],
            ['Partidos programados', `${totalMatches} hoy`],
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
