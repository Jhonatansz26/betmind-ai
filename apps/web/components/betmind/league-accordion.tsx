'use client'

import * as React from 'react'
import { ChevronDownIcon } from 'lucide-react'
import { cn } from '@/lib/utils'
import { type Match } from '@/lib/betmind'
import { resolveLeague } from '@/lib/league-metadata'
import { LeagueLogo } from './league-logo'
import { MatchCard } from './match-card'

interface LeagueAccordionProps {
  leagueExternalId?: number | null
  leagueName: string
  matches: Match[]
  isOpen: boolean
  onToggle: () => void
}

export function LeagueAccordion({
  leagueExternalId,
  leagueName,
  matches,
  isOpen,
  onToggle,
}: LeagueAccordionProps) {
  const meta = resolveLeague(leagueExternalId, leagueName)
  const liveCount = matches.filter((m) => m.status === 'LIVE' || m.status === 'IN_PLAY').length
  const logoUrl = matches[0]?.leagueLogoUrl || meta.logoUrl

  return (
    <div className="overflow-hidden rounded-xl border border-border bg-card/80 transition-all">
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={isOpen}
        className="flex w-full items-center justify-between px-4 py-3 transition-colors hover:bg-muted/50"
      >
        <div className="flex items-center gap-2.5">
          <LeagueLogo logoUrl={logoUrl} flag={meta.flag} size="md" />
          <div className="flex flex-col items-start">
            <span className="text-sm font-semibold text-foreground">{meta.name}</span>
            <span className="text-[11px] text-subtle">{meta.country}</span>
          </div>
          {liveCount > 0 && (
            <span className="ml-1 inline-flex items-center gap-1 rounded-full border border-positive/20 bg-positive/10 px-2 py-0.5 text-[10px] font-bold text-positive">
              <span className="live-dot size-1.5 rounded-full bg-positive" aria-hidden />
              {liveCount} en vivo
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          <span className="num rounded-md bg-muted px-2 py-0.5 text-xs font-semibold text-muted-foreground">
            {matches.length}
          </span>
          <ChevronDownIcon
            className={cn(
              'size-4 text-subtle transition-transform duration-200',
              isOpen && 'rotate-180',
            )}
            aria-hidden
          />
        </div>
      </button>

      {isOpen && (
        <div className="accordion-content flex flex-col gap-2 border-t border-border bg-surface/40 p-2">
          {matches.map((match, i) => (
            <div key={match.id} className="stagger-item" style={{ animationDelay: `${i * 40}ms` }}>
              <MatchCard match={match} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
