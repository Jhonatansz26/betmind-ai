'use client'

import * as React from 'react'

import { cn } from '@/lib/utils'
import type { Match } from '@/lib/betmind'
import type { LeagueData } from '@/lib/api'
import { resolveLeague } from '@/lib/league-metadata'
import { LeagueLogo } from './league-logo'

interface LeagueSidebarProps {
  active: string
  onSelect: (leagueId: string) => void
  matches: Match[]
  leagues?: LeagueData[]
}

function LeagueGroup({
  region,
  items,
  active,
  onSelect,
}: {
  region: 'EUROPE' | 'AMERICAS'
  items: {
    leagueId: string
    name: string
    active_matches: number
    flag: string
    logoUrl: string | null
    region: string
    matchType: string
  }[]
  active: string
  onSelect: (id: string) => void
}) {
  const regionLabel = region === 'EUROPE' ? 'EUROPA' : 'AMERICA'
  return (
    <div className="flex flex-col gap-1">
       <p className="px-3 py-1 text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground">{regionLabel}</p>
      {items.map((item) => {
        const selected = active === item.leagueId
        return (
          <button
            key={item.leagueId}
            type="button"
            onClick={() => onSelect(item.leagueId)}
            aria-current={selected}
            className={cn(
               'group flex w-full items-center justify-between rounded-md px-3 py-1.5 text-left text-xs transition-colors',
               selected
                 ? 'bg-primary/10 font-semibold text-primary'
                 : 'text-foreground hover:bg-surface/50',
            )}
          >
            <div className="flex items-center gap-2 min-w-0">
              <LeagueLogo logoUrl={item.logoUrl} flag={item.flag} size="sm" />
              <span className="flex min-w-0 items-center truncate text-xs font-medium text-foreground">
                <span className="max-w-[170px] truncate">{item.name}</span>
                {item.matchType === 'KNOCKOUT_CUP' && (
                  <span className="ml-1.5 rounded border border-warning/30 bg-warning/10 px-1 py-0.2 text-[9px] font-mono text-warning">
                    COPA
                  </span>
                )}
              </span>
            </div>
            <span
              className={cn(
                'shrink-0 rounded border border-border/60 bg-surface-inset px-1.5 py-0.5 font-mono text-[11px] font-bold tabular-nums text-foreground',
                item.active_matches === 0 && 'text-subtle opacity-50',
              )}
            >
              {item.active_matches}
            </span>
          </button>
        )
      })}
    </div>
  )
}

export function LeagueSidebar({ active, onSelect, matches, leagues = [] }: LeagueSidebarProps) {
  const sidebarLeagues = React.useMemo(() => {
    const matchTypeMap = new Map(
      matches.map((match) => [String(match.leagueExternalId ?? 'other'), match.matchType]),
    )

    if (leagues.length > 0) {
      return leagues
        .map((league) => {
          const meta = resolveLeague(league.external_id, league.name)
          return {
            leagueId: String(league.external_id),
            name: meta.shortName,
            active_matches: league.active_matches,
            flag: meta.flag,
            logoUrl: league.logo_url || meta.logoUrl,
            region: meta.region,
            matchType: matchTypeMap.get(String(league.external_id)) ?? 'LEAGUE',
          }
        })
        .sort((a, b) => b.active_matches - a.active_matches)
    }

    const countMap = new Map<string, {
      leagueId: string
      name: string
      active_matches: number
      flag: string
      logoUrl: string | null
      region: string
      matchType: string
    }>()

    for (const m of matches) {
      const lid = String(m.leagueExternalId ?? 'other')
      if (!countMap.has(lid)) {
        const meta = resolveLeague(m.leagueExternalId, m.league)
        countMap.set(lid, {
          leagueId: lid,
          name: meta.shortName,
          active_matches: 0,
          flag: meta.flag,
          logoUrl: m.leagueLogoUrl || meta.logoUrl,
          region: meta.region,
          matchType: m.matchType,
        })
      }
      countMap.get(lid)!.active_matches++
    }

    return Array.from(countMap.values())
      .filter((l) => l.active_matches > 0)
      .sort((a, b) => b.active_matches - a.active_matches)
  }, [leagues, matches])

  const europeLeagues = sidebarLeagues.filter((l) => l.region === 'EUROPE')
  const americasLeagues = sidebarLeagues.filter((l) => l.region === 'AMERICAS')

  const totalMatches = leagues.length > 0
    ? sidebarLeagues.reduce((total, league) => total + league.active_matches, 0)
    : matches.length

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <p className="px-3 py-2 text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground">CATÁLOGO DE LIGAS (26)</p>
        <button
          type="button"
          onClick={() => onSelect('all')}
          aria-current={active === 'all'}
          className={cn(
            'flex w-full items-center justify-between rounded-lg border border-border/40 bg-surface/30 px-3 py-2 text-xs font-semibold transition-colors hover:bg-surface/60',
            active === 'all'
              ? 'border-primary/30 bg-primary/10 text-primary'
              : 'text-foreground',
          )}
        >
          <span>Todas las Ligas</span>
          <span className="rounded border border-border/60 bg-surface-inset px-1.5 py-0.5 font-mono text-[11px] font-bold tabular-nums text-foreground">
            {totalMatches}
          </span>
        </button>
      </div>

      <div className="flex flex-col gap-4">
        {europeLeagues.length > 0 && (
          <LeagueGroup region="EUROPE" items={europeLeagues} active={active} onSelect={onSelect} />
        )}
        {americasLeagues.length > 0 && (
          <LeagueGroup region="AMERICAS" items={americasLeagues} active={active} onSelect={onSelect} />
        )}
      </div>

    </div>
  )
}
