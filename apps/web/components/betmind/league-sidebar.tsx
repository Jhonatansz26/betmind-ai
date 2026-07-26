'use client'

import * as React from 'react'
import { CheckCircle2Icon } from 'lucide-react'

import { cn } from '@/lib/utils'
import { fetchLeagues, flagForCountry, formatCompositeLeagueName } from '@/lib/api'
import type { LeagueData } from '@/lib/api'

const AMERICAS_COUNTRIES = new Set([
  'Brazil', 'Brasil', 'Colombia', 'Argentina', 'USA', 'United States',
  'Mexico', 'México', 'Chile', 'Ecuador', 'Peru', 'Perú', 'Uruguay', 'Paraguay', 'Bolivia', 'Venezuela'
])

function resolveFlag(league: LeagueData): string {
  return flagForCountry(league.country, league.name)
}

function resolveRegion(country: string | null, name: string): 'EUROPE' | 'AMERICAS' {
  if (country) {
    if (AMERICAS_COUNTRIES.has(country)) return 'AMERICAS'
    return 'EUROPE'
  }
  if (name.includes('MLS') || name.includes('Liga') || name.includes('BetPlay') || name.includes('Brasileir') || (name.includes('Serie A') && !name.includes('Italy'))) return 'AMERICAS'
  return 'EUROPE'
}

function formatLeagueName(league: LeagueData): string {
  return formatCompositeLeagueName(league.name, league.country)
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
              {resolveFlag(league)}
            </span>
            <span className="flex-1 truncate text-xs text-foreground">{formatLeagueName(league)}</span>
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
