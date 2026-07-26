'use client'

import * as React from 'react'
import { CheckCircle2Icon } from 'lucide-react'

import { cn } from '@/lib/utils'
import { fetchLeagues } from '@/lib/api'
import type { LeagueData } from '@/lib/api'

const LEAGUE_FLAGS: Record<string, string> = {
  'Premier League': '\u{1F3F4}\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}',
  'LaLiga': '\u{1F1EA}\u{1F1F8}',
  'Bundesliga': '\u{1F1E9}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}',
  'Serie A': '\u{1F1EE}\u{1F1F9}',
  'Ligue 1': '\u{1F1EB}\u{1F1F7}',
  'Liga BetPlay Dimayor': '\u{1F1E8}\u{1F1F4}',
  'Primera A': '\u{1F1E8}\u{1F1F4}',
  'Serie A (Brazil)': '\u{1F1E7}\u{1F1F7}',
  'Brasileirão': '\u{1F1E7}\u{1F1F7}',
  'Liga Profesional': '\u{1F1E6}\u{1F1F7}',
  'Liga MX': '\u{1F1F2}\u{1F1FD}',
  'Major League Soccer': '\u{1F1FA}\u{1F1F8}',
  'MLS': '\u{1F1FA}\u{1F1F8}',
  'Primera División': '\u{1F1E8}\u{1F1F1}',
  'Liga Pro': '\u{1F1EA}\u{1F1E8}',
  'Liga 1': '\u{1F1F5}\u{1F1EA}',
  'Allsvenskan': '\u{1F1F8}\u{1F1EA}',
  'Superliga': '\u{1F1E9}\u{1F1F0}',
  'Super League': '\u{1F1E8}\u{1F1ED}',
}

const REGION_MAP: Record<string, 'EUROPE' | 'AMERICAS'> = {
  'England': 'EUROPE',
  'Spain': 'EUROPE',
  'Germany': 'EUROPE',
  'Italy': 'EUROPE',
  'France': 'EUROPE',
  'Sweden': 'EUROPE',
  'Denmark': 'EUROPE',
  'Switzerland': 'EUROPE',
  'Portugal': 'EUROPE',
  'Brasil': 'AMERICAS',
  'Colombia': 'AMERICAS',
  'Argentina': 'AMERICAS',
  'USA': 'AMERICAS',
  'Chile': 'AMERICAS',
  'Ecuador': 'AMERICAS',
  'Peru': 'AMERICAS',
}

function resolveFlag(leagueName: string): string {
  return LEAGUE_FLAGS[leagueName] ?? '\u{1F3C1}'
}

function resolveRegion(country: string | null, name: string): 'EUROPE' | 'AMERICAS' {
  if (country && REGION_MAP[country]) return REGION_MAP[country]
  if (name.includes('MLS') || name.includes('Liga') || name.includes('Serie A') && country !== 'Italy') return 'AMERICAS'
  return 'EUROPE'
}

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
      <p className="px-2 py-1 text-[10px] font-semibold tracking-[0.12em] text-subtle">{regionLabel}</p>
      {leagues.map((league) => {
        const leagueId = String(league.external_id)
        const selected = active === leagueId
        return (
          <button
            key={league.id}
            type="button"
            onClick={() => onSelect(leagueId)}
            aria-current={selected}
            className={cn(
              'flex items-center gap-2 rounded-md border px-2 py-1.5 text-left transition-colors',
              selected
                ? 'border-primary/40 bg-primary/10'
                : 'border-transparent hover:bg-muted/50',
            )}
          >
            <span aria-hidden className="text-sm leading-none">
              {resolveFlag(league.name)}
            </span>
            <span className="flex-1 truncate text-xs text-foreground">{league.name}</span>
            <span className="num rounded-sm bg-muted/70 px-1.5 py-0.5 text-[10px] text-muted-foreground">
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

  const europeLeagues = leagues.filter((l) => resolveRegion(l.country, l.name) === 'EUROPE')
  const americasLeagues = leagues.filter((l) => resolveRegion(l.country, l.name) === 'AMERICAS')

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <p className="text-xs font-medium tracking-wide text-muted-foreground">Ligas Activas</p>
        <button
          type="button"
          onClick={() => onSelect('all')}
          aria-current={active === 'all'}
          className={cn(
            'w-fit rounded-sm border px-2 py-1 text-[11px] font-medium transition-colors',
            active === 'all'
              ? 'border-primary/40 bg-primary text-primary-foreground'
              : 'border-border bg-background/40 text-muted-foreground hover:text-foreground',
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
        <>
          <LeagueGroup region="EUROPE" leagues={europeLeagues} active={active} onSelect={onSelect} />
          <LeagueGroup region="AMERICAS" leagues={americasLeagues} active={active} onSelect={onSelect} />
        </>
      )}

      <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-medium text-foreground">Estado del Modelo</p>
          <span className="inline-flex items-center gap-1 rounded-sm border border-positive/30 bg-positive/10 px-1.5 py-0.5 text-[10px] font-medium text-positive">
            <CheckCircle2Icon className="size-2.5" aria-hidden />
            CALIBRADO
          </span>
        </div>
        <dl className="flex flex-col gap-1.5">
          {[
            ['Ligas activas', `${leagues.length} hoy`],
            ['Partidos programados', `${leagues.reduce((sum, l) => sum + l.active_matches, 0)} hoy`],
          ].map(([label, value]) => (
            <div key={label} className="flex items-center justify-between gap-2">
              <dt className="text-[11px] text-subtle">{label}</dt>
              <dd className="num text-[11px] text-muted-foreground">{value}</dd>
            </div>
          ))}
        </dl>
      </div>
    </div>
  )
}
