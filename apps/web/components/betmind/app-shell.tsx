'use client'

import * as React from 'react'

import { BottomNav, TopNav } from './top-nav'
import { ResponsibleGamingFooter } from './responsible-gaming-footer'
import { DevProToggle } from './dev-pro-toggle'
import { ProLimitModalHost } from './pro-limit-modal'

export function AppShell({
  children,
  onToggleSidebar,
  activeLeagueCount = 0,
}: {
  children: React.ReactNode
  onToggleSidebar?: () => void
  activeLeagueCount?: number
}) {
  return (
    <div className="min-h-svh bg-background pb-[calc(4rem+env(safe-area-inset-bottom))] md:pb-0">
      <TopNav onToggleSidebar={onToggleSidebar} activeLeagueCount={activeLeagueCount} />
      <main className="mx-auto w-full max-w-[1600px] px-4 py-6 sm:px-6">{children}</main>
      <ResponsibleGamingFooter />
      <BottomNav />
      <DevProToggle />
      <ProLimitModalHost />
    </div>
  )
}
