'use client'

import { CalendarIcon, ScanIcon, TicketIcon } from 'lucide-react'
import { MenuIcon } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export const NAV_TABS = ['Boletos', 'Partidos', 'Escáner'] as const
export type NavTab = (typeof NAV_TABS)[number]

const NAV_ICONS: Record<NavTab, React.ReactNode> = {
  Boletos: <TicketIcon className="size-4" aria-hidden />,
  Partidos: <CalendarIcon className="size-4" aria-hidden />,
  Escáner: <ScanIcon className="size-4" aria-hidden />,
}

interface TopNavProps {
  active: NavTab
  onChange: (tab: NavTab) => void
  onToggleSidebar: () => void
}

export function TopNav({ active, onChange, onToggleSidebar }: TopNavProps) {
  return (
    <header className="sticky top-0 z-40 flex h-14 items-center justify-between gap-4 border-b border-border/60 bg-card/80 px-6 backdrop-blur-md">
      <div className="mx-auto flex w-full max-w-[1600px] items-center justify-between gap-4">
        <Button
          variant="ghost"
          size="icon-sm"
          className="lg:hidden"
          onClick={onToggleSidebar}
          aria-label="Toggle league sidebar"
        >
          <MenuIcon aria-hidden="true" />
        </Button>

        <div className="flex shrink-0 items-center gap-2">
          <p className="text-base font-bold tracking-tight text-foreground">
          <span>
            Bet<span className="font-bold">Mind</span>
          </span>
          </p>
          <span className="rounded border border-border/60 bg-surface/50 px-2 py-0.5 text-[10px] font-mono font-medium text-muted-foreground">
            v0.1.0 • QUANT ENGINE
          </span>
        </div>

        <nav
          aria-label="Primary"
          className="no-scrollbar mx-auto hidden items-center gap-1 overflow-x-auto md:flex"
        >
          {NAV_TABS.map((tab) => (
            <button
              key={tab}
              type="button"
              onClick={() => onChange(tab)}
              aria-current={active === tab ? 'page' : undefined}
              className={cn(
                'flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium whitespace-nowrap transition-colors',
                active === tab
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:text-foreground',
              )}
            >
              {NAV_ICONS[tab]}
              {tab}
            </button>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2">
          <span className="hidden rounded-md border border-border/50 bg-surface/30 px-2.5 py-1 text-[11px] font-mono text-muted-foreground sm:inline-flex">
            COT (UTC-5)
          </span>
          <span className="hidden items-center gap-1.5 rounded-md border border-positive/30 bg-positive/10 px-2.5 py-1 text-[11px] font-mono font-semibold text-positive sm:inline-flex">
            <span className="live-dot size-1.5 rounded-full bg-positive" aria-hidden />
            26 LIGAS EN VIVO
          </span>
        </div>
      </div>
    </header>
  )
}

export function BottomNav({ active, onChange }: { active: NavTab; onChange: (tab: NavTab) => void }) {
  return (
    <nav
      aria-label="Primary mobile"
      className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-3 border-t border-border bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-md md:hidden"
    >
      {NAV_TABS.map((tab) => (
        <button
          key={tab}
          type="button"
          onClick={() => onChange(tab)}
          aria-current={active === tab ? 'page' : undefined}
          className={cn(
            'flex flex-col items-center gap-1 px-2 py-2.5 text-[10px] font-medium transition-colors',
            active === tab ? 'text-primary' : 'text-muted-foreground',
          )}
        >
          {NAV_ICONS[tab]}
          {tab}
        </button>
      ))}
    </nav>
  )
}
