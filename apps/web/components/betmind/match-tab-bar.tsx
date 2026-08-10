'use client'

import * as React from 'react'
import { BarChart3Icon, SwordsIcon, TargetIcon, TrendingUpIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

export type MatchTab = 'preview' | 'markets' | 'builder' | 'h2h'

interface TabDef { id: MatchTab; icon: React.ElementType; label: string }

const TABS: TabDef[] = [
  { id: 'preview', icon: TrendingUpIcon, label: 'Resumen & Insights' },
  { id: 'markets', icon: BarChart3Icon, label: 'Pronósticos' },
  { id: 'builder', icon: TargetIcon, label: 'Bet Builder' },
  { id: 'h2h', icon: SwordsIcon, label: 'Cara a Cara' },
]

interface MatchTabBarProps { active: MatchTab; onChange: (tab: MatchTab) => void; className?: string }

export function MatchTabBar({ active, onChange, className }: MatchTabBarProps) {
  return (
    <nav className={cn('sticky top-14 z-30 border-y border-border/80 bg-background/90 backdrop-blur-xl', className)} aria-label="Navegación del partido">
      <div role="tablist" aria-orientation="horizontal" className="no-scrollbar mx-auto flex w-full max-w-5xl gap-1 overflow-x-auto px-2 py-2 sm:px-4">
        {TABS.map(({ id, icon: Icon, label }) => {
          const isActive = active === id
          return (
            <button
              key={id}
              type="button"
              id={`match-tab-${id}`}
              role="tab"
              aria-selected={isActive}
              aria-controls={`match-panel-${id}`}
              onClick={() => onChange(id)}
              className={cn(
                'group relative flex min-h-10 shrink-0 items-center gap-2 rounded-lg border px-3 py-2 text-[11px] font-semibold tracking-[0.06em] transition-[color,background-color,border-color,transform] duration-180 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/70',
                isActive ? 'border-primary/30 bg-primary/10 text-primary' : 'border-transparent text-subtle hover:border-border hover:bg-surface/70 hover:text-foreground',
              )}
            >
              <Icon className={cn('size-3.5 shrink-0 transition-colors', isActive ? 'text-primary' : 'text-subtle group-hover:text-foreground')} aria-hidden />
              {label}
              {isActive && <span className="absolute inset-x-3 -bottom-[9px] h-px bg-primary" aria-hidden="true" />}
            </button>
          )
        })}
      </div>
    </nav>
  )
}
