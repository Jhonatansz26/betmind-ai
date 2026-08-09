'use client'

import * as React from 'react'
import type { ReactNode } from 'react'
import Link from 'next/link'
import { usePathname, useRouter } from 'next/navigation'
import { BarChart3, CalendarIcon, ChevronDown, History, LogOut, MenuIcon, Monitor, Moon, Sun, User, Wallet } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { clearToken } from '@/lib/auth'
import { useAuthSession } from '@/lib/hooks/use-auth-session'
import { applyTheme, getStoredTheme, setStoredTheme, type ThemePreference } from '@/lib/theme'
import { cn } from '@/lib/utils'
import { useProStatus } from './use-pro-status'

const NAV_ITEMS = [
  { href: '/senales', label: 'Señales', icon: <BarChart3 className="size-4" aria-hidden="true" /> },
  { href: '/partidos', label: 'Partidos', icon: <CalendarIcon className="size-4" aria-hidden="true" /> },
  { href: '/historial', label: 'Historial', icon: <History className="size-4" aria-hidden="true" /> },
  { href: '/bankroll', label: 'Bankroll', icon: <Wallet className="size-4" aria-hidden="true" /> },
] as const

const THEME_OPTIONS: Array<{ value: ThemePreference; label: string; icon: ReactNode }> = [
  { value: 'light', label: 'Claro', icon: <Sun className="size-3.5" aria-hidden="true" /> },
  { value: 'dark', label: 'Oscuro', icon: <Moon className="size-3.5" aria-hidden="true" /> },
  { value: 'system', label: 'Sistema', icon: <Monitor className="size-3.5" aria-hidden="true" /> },
]

const THEME_ICONS: Record<ThemePreference, ReactNode> = {
  light: <Sun className="size-4" aria-hidden="true" />,
  dark: <Moon className="size-4" aria-hidden="true" />,
  system: <Monitor className="size-4" aria-hidden="true" />,
}

function ThemeControl() {
  const [theme, setTheme] = React.useState<ThemePreference>('system')
  const [mobileOpen, setMobileOpen] = React.useState(false)

  React.useEffect(() => {
    const storedTheme = getStoredTheme()
    setTheme(storedTheme)
    applyTheme(storedTheme)

    const media = window.matchMedia('(prefers-color-scheme: dark)')
    const handleSystemThemeChange = () => {
      if (getStoredTheme() === 'system') applyTheme('system')
    }
    media.addEventListener('change', handleSystemThemeChange)
    return () => media.removeEventListener('change', handleSystemThemeChange)
  }, [])

  function chooseTheme(nextTheme: ThemePreference) {
    setStoredTheme(nextTheme)
    applyTheme(nextTheme)
    setTheme(nextTheme)
    setMobileOpen(false)
  }

  return (
    <div className="relative shrink-0">
      <div role="radiogroup" aria-label="Preferencia de tema" className="hidden items-center gap-0.5 rounded-lg border border-border bg-surface/70 p-1 sm:inline-flex">
        {THEME_OPTIONS.map((option) => (
          <button key={option.value} type="button" role="radio" aria-checked={theme === option.value} aria-label={option.label} onClick={() => chooseTheme(option.value)} className={cn('inline-flex size-7 items-center justify-center rounded-md text-muted-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60', theme === option.value ? 'bg-surface-raised text-foreground shadow-sm' : 'hover:text-foreground')}>
            {option.icon}
          </button>
        ))}
      </div>

      <div className="sm:hidden">
        <button type="button" aria-label={`Tema: ${THEME_OPTIONS.find((option) => option.value === theme)?.label ?? 'Sistema'}`} aria-expanded={mobileOpen} aria-haspopup="menu" onClick={() => setMobileOpen((open) => !open)} className="inline-flex size-9 items-center justify-center rounded-lg border border-border bg-surface/70 text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60">
          {THEME_ICONS[theme]}
        </button>
        {mobileOpen && (
          <div role="radiogroup" aria-label="Preferencia de tema" className="absolute right-0 top-[calc(100%+0.5rem)] z-50 flex min-w-32 flex-col gap-1 rounded-lg border border-border bg-popover p-1.5 shadow-lg">
            {THEME_OPTIONS.map((option) => (
              <button key={option.value} type="button" role="radio" aria-checked={theme === option.value} onClick={() => chooseTheme(option.value)} className={cn('inline-flex min-h-9 items-center gap-2 rounded-md px-2.5 text-left text-xs text-muted-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60', theme === option.value ? 'bg-surface-raised text-foreground shadow-sm' : 'hover:text-foreground')}>
                {option.icon}
                {option.label}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

/** Avatar with user initials */
function UserAvatar({ name, email }: { name?: string | null; email: string }) {
  const initials = name
    ? name.split(' ').map((w) => w[0]).slice(0, 2).join('').toUpperCase()
    : email.slice(0, 2).toUpperCase()
  return (
    <span className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/15 text-xs font-bold text-primary">
      {initials}
    </span>
  )
}

/** Session button / popover */
function SessionControl() {
  const router = useRouter()
  const { user, isLoading } = useAuthSession()
  const [open, setOpen] = React.useState(false)
  const popoverRef = React.useRef<HTMLDivElement>(null)

  // Close popover on outside click
  React.useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (popoverRef.current && !popoverRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  if (isLoading) {
    // Skeleton to avoid flash between states
    return <div className="h-8 w-[90px] animate-pulse rounded-lg bg-surface-raised" />
  }

  if (!user) {
    return (
      <Link
        href="/cuenta/login"
        id="topnav-login"
        className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface/70 px-3 py-1.5 text-xs font-semibold text-foreground transition-colors hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
      >
        <User className="size-3.5" aria-hidden />
        Iniciar sesión
      </Link>
    )
  }

  function handleLogout() {
    setOpen(false)
    clearToken()
    router.push('/')
  }

  return (
    <div className="relative shrink-0" ref={popoverRef}>
      <button
        type="button"
        id="topnav-user-menu"
        aria-expanded={open}
        aria-haspopup="menu"
        onClick={() => setOpen((o) => !o)}
        className="inline-flex items-center gap-2 rounded-lg border border-border bg-surface/70 px-2 py-1 text-xs font-medium text-foreground transition-colors hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
      >
        <UserAvatar name={user.full_name} email={user.email} />
        <ChevronDown className={cn('size-3.5 text-muted-foreground transition-transform', open && 'rotate-180')} aria-hidden />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 top-[calc(100%+0.5rem)] z-50 min-w-52 rounded-xl border border-border bg-popover p-2 shadow-lg"
        >
          {/* Identity */}
          <div className="mb-1 flex items-center gap-3 rounded-lg bg-surface/40 px-3 py-2.5">
            <UserAvatar name={user.full_name} email={user.email} />
            <div className="min-w-0">
              {user.full_name && (
                <p className="truncate text-xs font-semibold text-foreground">{user.full_name}</p>
              )}
              <p className="truncate text-[11px] text-muted-foreground">{user.email}</p>
            </div>
            {user.is_pro && (
              <span className="ml-auto shrink-0 inline-flex items-center rounded-md border border-brand/40 bg-brand/10 px-2 py-0.5 text-[10px] font-bold text-brand">
                PRO
              </span>
            )}
          </div>

          <div className="my-1 h-px bg-border/60" />

          <Link
            role="menuitem"
            href="/historial"
            onClick={() => setOpen(false)}
            className="flex items-center gap-2 rounded-lg px-3 py-2 text-xs text-muted-foreground transition-colors hover:bg-surface hover:text-foreground"
          >
            <History className="size-3.5" aria-hidden />
            Mi historial
          </Link>

          <div className="my-1 h-px bg-border/60" />

          <button
            role="menuitem"
            type="button"
            id="topnav-logout"
            onClick={handleLogout}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-negative/80 transition-colors hover:bg-negative/10 hover:text-negative"
          >
            <LogOut className="size-3.5" aria-hidden />
            Cerrar sesión
          </button>
        </div>
      )}
    </div>
  )
}

function isActivePath(pathname: string, href: string) {
  return pathname === href || (href === '/partidos' && pathname.startsWith('/partidos/'))
}

interface TopNavProps {
  onToggleSidebar?: () => void
  activeLeagueCount?: number
}

export function TopNav({ onToggleSidebar, activeLeagueCount = 0 }: TopNavProps) {
  const pathname = usePathname()
  const isPro = useProStatus()

  return (
    <header className="sticky top-0 z-40 border-b border-border/60 bg-background/90 backdrop-blur-xl">
      <div className="mx-auto flex min-h-16 w-full max-w-[1600px] items-center gap-4 px-4 sm:px-6">
        {onToggleSidebar && (
          <Button variant="ghost" size="icon-sm" className="shrink-0 lg:hidden" onClick={onToggleSidebar} aria-label="Abrir catálogo de ligas">
            <MenuIcon aria-hidden="true" />
          </Button>
        )}

        <Link href="/" className="flex min-w-0 shrink-0 items-center gap-3" aria-label="BetMind AI, ir al inicio">
          <div className="flex size-8 items-center justify-center rounded-md border border-positive/40 bg-positive/10 font-mono text-xs font-bold text-positive">BM</div>
          <div className="hidden min-w-0 sm:block">
            <p className="truncate text-sm font-semibold tracking-tight text-foreground">BetMind AI</p>
            <p className="terminal-kicker">Quant Terminal · v0.1.0</p>
          </div>
          <span className="terminal-kicker hidden border-l border-border/70 pl-3 lg:block">Signal Desk</span>
        </Link>

        <nav aria-label="Navegación principal" className="no-scrollbar mx-auto hidden items-center gap-1 overflow-x-auto md:flex">
          {NAV_ITEMS.map((item) => (
            <Link key={item.href} href={item.href} aria-current={isActivePath(pathname, item.href) ? 'page' : undefined} className={cn('flex items-center gap-2 rounded-md border border-transparent px-4 py-2.5 text-xs font-medium whitespace-nowrap transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60', isActivePath(pathname, item.href) ? 'border-border/70 bg-surface-raised text-foreground' : 'text-muted-foreground hover:border-border/50 hover:text-foreground')}>
              {item.icon}
              {item.label}
            </Link>
          ))}
        </nav>

        <div className="ml-auto flex shrink-0 items-center gap-2">
          {isPro ? (
            <span className="inline-flex items-center rounded-md border border-brand/40 bg-brand/10 px-3 py-1.5 text-xs font-bold text-brand">PRO ✓</span>
          ) : (
            <Link href="/planes" className="inline-flex items-center rounded-md border border-brand/40 bg-brand/10 px-3 py-1.5 text-xs font-bold text-brand transition-colors hover:bg-brand/20 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">PRO</Link>
          )}
          <ThemeControl />
          <span className="hidden rounded-md border border-border/60 bg-surface/40 px-3 py-1.5 text-xs font-mono tabular-nums text-muted-foreground sm:inline-flex">COT · UTC−5</span>
          <span className="hidden items-center gap-2 rounded-md border border-positive/30 bg-positive/5 px-3 py-1.5 text-xs font-mono tabular-nums font-semibold text-positive sm:inline-flex">
            <span className="live-dot size-1.5 rounded-full bg-positive" aria-hidden="true" />
            {activeLeagueCount} ACTIVAS
          </span>
          {/* Session control — login button or user avatar/popover */}
          <SessionControl />
        </div>
      </div>
    </header>
  )
}

export function BottomNav() {
  const pathname = usePathname()

  return (
    <nav aria-label="Navegación principal móvil" className="fixed inset-x-0 bottom-0 z-40 grid grid-cols-4 border-t border-border bg-background/95 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl md:hidden">
      {NAV_ITEMS.map((item) => (
        <Link key={item.href} href={item.href} aria-current={isActivePath(pathname, item.href) ? 'page' : undefined} className={cn('flex min-h-14 flex-col items-center justify-center gap-1 px-2 py-2 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60', isActivePath(pathname, item.href) ? 'text-primary' : 'text-muted-foreground hover:text-foreground')}>
          {item.icon}
          {item.label}
        </Link>
      ))}
    </nav>
  )
}
