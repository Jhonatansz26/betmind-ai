'use client'

import { CheckCircle2Icon } from 'lucide-react'

import { LEAGUES, MODEL_HEALTH } from '@/lib/betmind'
import { cn } from '@/lib/utils'

interface LeagueSidebarProps {
  active: string
  onSelect: (leagueId: string) => void
}

function LeagueGroup({
  region,
  active,
  onSelect,
}: {
  region: 'EUROPE' | 'AMERICAS'
  active: string
  onSelect: (id: string) => void
}) {
  return (
    <div className="flex flex-col gap-1">
      <p className="px-2 py-1 text-[10px] font-semibold tracking-[0.12em] text-subtle">{region}</p>
      {LEAGUES.filter((l) => l.region === region).map((league) => {
        const selected = active === league.id
        return (
          <button
            key={league.id}
            type="button"
            onClick={() => onSelect(league.id)}
            aria-current={selected}
            className={cn(
              'flex items-center gap-2 rounded-md border px-2 py-1.5 text-left transition-colors',
              selected
                ? 'border-primary/40 bg-primary/10'
                : 'border-transparent hover:bg-muted/50',
            )}
          >
            <span aria-hidden className="text-sm leading-none">
              {league.flag}
            </span>
            <span className="flex-1 truncate text-xs text-foreground">{league.name}</span>
            <span className="num rounded-sm bg-muted/70 px-1.5 py-0.5 text-[10px] text-muted-foreground">
              {league.matches}
            </span>
          </button>
        )
      })}
    </div>
  )
}

export function LeagueSidebar({ active, onSelect }: LeagueSidebarProps) {
  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <p className="text-xs font-medium tracking-wide text-muted-foreground">Active Leagues</p>
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
          All Leagues
        </button>
      </div>

      <LeagueGroup region="EUROPE" active={active} onSelect={onSelect} />
      <LeagueGroup region="AMERICAS" active={active} onSelect={onSelect} />

      <div className="flex flex-col gap-2 rounded-lg border border-border bg-card p-3">
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs font-medium text-foreground">Model Status</p>
          <span className="inline-flex items-center gap-1 rounded-sm border border-positive/30 bg-positive/10 px-1.5 py-0.5 text-[10px] font-medium text-positive">
            <CheckCircle2Icon className="size-2.5" aria-hidden />
            CALIBRATED
          </span>
        </div>
        <dl className="flex flex-col gap-1.5">
          {[
            ['Brier Score', `${MODEL_HEALTH.brier.toFixed(2)} ✓`],
            ['Hit Rate', `${MODEL_HEALTH.hitRate.toFixed(1)}% ✓`],
            ['EV Opportunities', `${MODEL_HEALTH.opportunities} today`],
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
