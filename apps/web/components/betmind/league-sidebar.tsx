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

type CatalogGroup = 'BIG 5 EUROPA' | 'SUDAMÉRICA' | 'TORNEOS UEFA' | 'OTRAS LIGAS ACTIVAS'

interface SidebarLeague {
  leagueId: string
  name: string
  activeMatches: number
  flag: string
  logoUrl: string | null
  matchType: string
  group: CatalogGroup
}

const BIG_FIVE = new Set(['Premier League', 'LaLiga EA Sports', 'Bundesliga', 'Serie A', "Ligue 1 McDonald's"])

function getGroup(league: SidebarLeague): CatalogGroup {
  if (BIG_FIVE.has(league.name)) return 'BIG 5 EUROPA'
  if (league.name.toLowerCase().includes('uefa')) return 'TORNEOS UEFA'
  const lowerName = league.name.toLowerCase()
  if (/(argentina|brasil|colombia|chile|ecuador|perú|peru|uruguay|paraguay|bolivia|libertadores|sudamericana)/.test(lowerName)) return 'SUDAMÉRICA'
  return 'OTRAS LIGAS ACTIVAS'
}

function LeagueGroup({
  label,
  items,
  active,
  onSelect,
}: {
  label: CatalogGroup
  items: SidebarLeague[]
  active: string
  onSelect: (id: string) => void
}) {
  if (items.length === 0) return null

  return (
    <section aria-labelledby={`league-group-${label}`} className="flex flex-col gap-1">
      <div className="flex items-center justify-between px-2 pb-1 pt-2">
        <h2 id={`league-group-${label}`} className="terminal-label">{label}</h2>
        <span className="font-mono text-xs tabular-nums text-subtle">{items.length}</span>
      </div>
      {items.map((item) => {
        const selected = active === item.leagueId
        return (
          <button
            key={item.leagueId}
            type="button"
            onClick={() => onSelect(item.leagueId)}
            aria-current={selected ? 'page' : undefined}
            className={cn(
              'group flex min-h-10 w-full items-center justify-between gap-3 rounded-md border px-2.5 py-2 text-left text-xs transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60',
              selected
                ? 'border-positive/30 bg-positive/10 text-foreground'
                : 'border-transparent text-muted-foreground hover:border-border/60 hover:bg-surface-raised hover:text-foreground',
            )}
          >
            <span className="flex min-w-0 items-center gap-2.5">
              <LeagueLogo logoUrl={item.logoUrl} flag={item.flag} label={item.name} size="sm" />
              <span className="min-w-0 truncate font-medium">{item.name}</span>
            </span>
            <span className={cn(
              'shrink-0 rounded border border-border/60 bg-surface-inset px-1.5 py-0.5 font-mono text-xs font-semibold tabular-nums text-foreground',
              selected && 'border-positive/30 text-positive',
            )}>
              {item.activeMatches}
            </span>
          </button>
        )
      })}
    </section>
  )
}

export function LeagueSidebar({ active, onSelect, matches, leagues = [] }: LeagueSidebarProps) {
  const sidebarLeagues = React.useMemo<SidebarLeague[]>(() => {
    const matchTypeMap = new Map(
      matches.map((match) => [String(match.leagueExternalId ?? 'other'), match.matchType]),
    )

    if (leagues.length > 0) {
      return leagues
        .filter((league) => league.active_matches > 0)
        .map((league) => {
          const meta = resolveLeague(league.external_id, league.name)
          const item: SidebarLeague = {
            leagueId: String(league.external_id),
            name: meta.shortName,
            activeMatches: league.active_matches,
            flag: meta.flag,
            logoUrl: league.logo_url || meta.logoUrl,
            matchType: matchTypeMap.get(String(league.external_id)) ?? 'LEAGUE',
            group: 'OTRAS LIGAS ACTIVAS',
          }
          item.group = getGroup(item)
          return item
        })
        .sort((a, b) => b.activeMatches - a.activeMatches)
    }

    const countMap = new Map<string, SidebarLeague>()
    for (const match of matches) {
      const leagueId = String(match.leagueExternalId ?? 'other')
      const existing = countMap.get(leagueId)
      if (existing) {
        existing.activeMatches += 1
        continue
      }

      const meta = resolveLeague(match.leagueExternalId, match.league)
      const item: SidebarLeague = {
        leagueId,
        name: meta.shortName,
        activeMatches: 1,
        flag: meta.flag,
        logoUrl: match.leagueLogoUrl || meta.logoUrl,
        matchType: match.matchType,
        group: 'OTRAS LIGAS ACTIVAS',
      }
      item.group = getGroup(item)
      countMap.set(leagueId, item)
    }

    return Array.from(countMap.values()).sort((a, b) => b.activeMatches - a.activeMatches)
  }, [leagues, matches])

  const totalMatches = sidebarLeagues.reduce((total, league) => total + league.activeMatches, 0)
  const groups: CatalogGroup[] = ['BIG 5 EUROPA', 'SUDAMÉRICA', 'TORNEOS UEFA', 'OTRAS LIGAS ACTIVAS']

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-2">
        <div className="flex items-end justify-between px-2">
          <div>
            <p className="terminal-label">Market watch</p>
            <p className="mt-1 text-xs text-subtle">Competiciones activas</p>
          </div>
          <span className="font-mono text-xs tabular-nums text-positive">{sidebarLeagues.length}/26</span>
        </div>
        <button
          type="button"
          onClick={() => onSelect('all')}
          aria-current={active === 'all' ? 'page' : undefined}
          className={cn(
            'flex min-h-11 w-full items-center justify-between rounded-lg border px-3 text-xs font-semibold transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60',
            active === 'all'
              ? 'border-positive/30 bg-positive/10 text-positive'
              : 'border-border/60 bg-surface/40 text-foreground hover:border-border hover:bg-surface-raised',
          )}
        >
          <span>Todas las ligas</span>
          <span className="rounded border border-border/60 bg-surface-inset px-1.5 py-0.5 font-mono text-xs font-bold tabular-nums text-foreground">
            {totalMatches}
          </span>
        </button>
      </div>

      <div className="flex flex-col gap-3">
        {groups.map((group) => (
          <LeagueGroup
            key={group}
            label={group}
            items={sidebarLeagues.filter((league) => league.group === group)}
            active={active}
            onSelect={onSelect}
          />
        ))}
      </div>
    </div>
  )
}
