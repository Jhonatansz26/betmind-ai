'use client'

import { CalendarIcon, ScanIcon, TicketIcon } from 'lucide-react'
import { MenuIcon } from 'lucide-react'

import { Avatar, AvatarFallback } from '@/components/ui/avatar'
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
    <header className="sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur-md">
      <div className="mx-auto flex h-14 w-full max-w-[1600px] items-center gap-3 px-4">
        <Button
          variant="ghost"
          size="icon-sm"
          className="lg:hidden"
          onClick={onToggleSidebar}
          aria-label="Toggle league sidebar"
        >
          <MenuIcon aria-hidden="true" />
        </Button>

        <p className="flex shrink-0 items-center text-base font-bold tracking-tight text-foreground">
          <span>
            Bet<span className="font-bold">Mind</span>
          </span>
          <span className="ml-1.5 rounded-full border border-primary/20 bg-primary/10 px-1.5 py-0.5 text-[10px] font-bold text-primary shadow-sm backdrop-blur-md">
            AI
          </span>
        </p>

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

        <div className="ml-auto flex items-center gap-3 md:ml-0">
          <span className="hidden items-center gap-1.5 text-[10px] font-semibold tracking-wide text-positive sm:flex">
            <span className="live-dot size-1.5 rounded-full bg-positive" aria-hidden />
            DATOS EN VIVO
          </span>
          <span className="hidden rounded-md border border-primary/30 bg-primary/10 px-2 py-1 text-[10px] font-medium tracking-wide text-primary lg:inline-flex">
            MIEMBRO EDGE
          </span>
          <Avatar className="size-7">
            <AvatarFallback className="bg-muted text-[10px] text-muted-foreground">AM</AvatarFallback>
          </Avatar>
        </div>
      </div>
    </header>
  )
}

export function BottomNav({ active, onChange }: { active: NavTab; onChange: (tab: NavTab) => void }) {
  return (
    <nav
      aria-label="Primary mobile"
      className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-3 border-t border-border bg-background/95 backdrop-blur-md md:hidden"
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
