'use client'

import type { ReactNode } from 'react'
import { CalendarIcon, MenuIcon, ScanIcon, TicketIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export const NAV_TABS = ['Boletos', 'Partidos', 'Escáner'] as const
export type NavTab = (typeof NAV_TABS)[number]

const NAV_ICONS: Record<NavTab, ReactNode> = {
  Boletos: <TicketIcon className="size-4" aria-hidden="true" />,
  Partidos: <CalendarIcon className="size-4" aria-hidden="true" />,
  Escáner: <ScanIcon className="size-4" aria-hidden="true" />,
}

interface TopNavProps {
  active: NavTab
  onChange: (tab: NavTab) => void
  onToggleSidebar: () => void
  activeLeagueCount?: number
}

export function TopNav({ active, onChange, onToggleSidebar, activeLeagueCount = 0 }: TopNavProps) {
  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/90 backdrop-blur-xl">
      <div className="mx-auto flex min-h-16 w-full max-w-[1600px] items-center gap-4 px-4 sm:px-6">
        <Button
          variant="ghost"
          size="icon-sm"
          className="shrink-0 lg:hidden"
          onClick={onToggleSidebar}
          aria-label="Abrir catálogo de ligas"
        >
          <MenuIcon aria-hidden="true" />
        </Button>

        <div className="flex min-w-0 shrink-0 items-center gap-3">
          <div className="flex size-8 items-center justify-center rounded-md border border-positive/40 bg-positive/10 font-mono text-xs font-bold text-positive">
            BM
          </div>
          <div className="hidden min-w-0 sm:block">
            <p className="truncate text-sm font-semibold tracking-tight text-foreground">BetMind AI</p>
            <p className="terminal-kicker">Quant Terminal · v0.1.0</p>
          </div>
          <span className="terminal-kicker hidden border-l border-border/70 pl-3 lg:block">Signal Desk</span>
        </div>

        <nav aria-label="Navegación principal" className="no-scrollbar mx-auto hidden items-center gap-1 overflow-x-auto md:flex">
          {NAV_TABS.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => onChange(tab)}
              aria-current={active === tab ? 'page' : undefined}
              className={cn(
                'flex items-center gap-2 rounded-md border border-transparent px-4 py-2.5 text-xs font-medium whitespace-nowrap transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60',
                active === tab
                  ? 'border-border/70 bg-surface-raised text-foreground'
                  : 'text-muted-foreground hover:border-border/50 hover:text-foreground',
              )}
            >
              {NAV_ICONS[tab]}
              {tab}
            </button>
          ))}
        </nav>

        <div className="ml-auto flex shrink-0 items-center gap-2">
          <span className="hidden rounded-md border border-border/60 bg-surface/40 px-3 py-1.5 text-xs font-mono tabular-nums text-muted-foreground sm:inline-flex">
            COT · UTC−5
          </span>
          <span className="hidden items-center gap-2 rounded-md border border-positive/30 bg-positive/5 px-3 py-1.5 text-xs font-mono tabular-nums font-semibold text-positive sm:inline-flex">
            <span className="live-dot size-1.5 rounded-full bg-positive" aria-hidden="true" />
            {activeLeagueCount} ACTIVAS
          </span>
        </div>
      </div>
    </header>
  )
}

export function BottomNav({ active, onChange }: { active: NavTab; onChange: (tab: NavTab) => void }) {
  return (
    <nav
      aria-label="Navegación principal móvil"
      className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-3 border-t border-border bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl md:hidden"
    >
      {NAV_TABS.map((tab) => (
        <button
          key={tab}
          type="button"
          onClick={() => onChange(tab)}
          aria-current={active === tab ? 'page' : undefined}
          className={cn(
            'flex min-h-14 flex-col items-center justify-center gap-1 px-2 py-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60',
            active === tab ? 'text-primary' : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {NAV_ICONS[tab]}
          {tab}
        </button>
      ))}
    </nav>
  )
}
