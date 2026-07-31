'use client'

import * as React from 'react'
import { ShieldIcon, SwordsIcon, TrendingUpIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

export type MatchTab = 'preview' | 'h2h' | 'referee'

interface TabDef {
  id: MatchTab
  icon: React.ElementType
  label: string
}

const TABS: TabDef[] = [
  { id: 'preview', icon: TrendingUpIcon, label: 'Previa & Pronóstico' },
  { id: 'h2h',     icon: SwordsIcon,    label: 'H2H & Táctico' },
  { id: 'referee', icon: ShieldIcon,    label: 'Árbitro' },
]

interface MatchTabBarProps {
  active: MatchTab
  onChange: (tab: MatchTab) => void
  className?: string
}

/**
 * MatchTabBar
 *
 * Barra de navegación compacta de 3 pestañas, sticky debajo del header.
 * Sin fondos rellenos — el indicador activo es solo un borde inferior.
 * Scroll horizontal silencioso en mobile gracias a `no-scrollbar`.
 */
export function MatchTabBar({ active, onChange, className }: MatchTabBarProps) {
  return (
    <nav
      className={cn(
        'sticky top-14 z-30 border-b border-border bg-background/95 backdrop-blur-sm',
        className,
      )}
      aria-label="Navegación del partido"
    >
      <div
        role="tablist"
        aria-orientation="horizontal"
        className="no-scrollbar mx-auto flex w-full max-w-3xl items-end overflow-x-auto px-4"
      >
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
                'flex shrink-0 items-center gap-1.5 border-b-2 px-3 py-3 text-[11px] font-semibold uppercase tracking-wide transition-colors',
                isActive
                  ? 'border-primary text-primary'
                  : 'border-transparent text-subtle hover:text-foreground',
              )}
            >
              <Icon
                className={cn('size-3.5 shrink-0', isActive ? 'text-primary' : 'text-subtle')}
                aria-hidden
              />
              {label}
            </button>
          )
        })}
      </div>
    </nav>
  )
}
