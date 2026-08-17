'use client'

import Link from 'next/link'
import { Lock, Sparkles, Target } from 'lucide-react'

import { cn } from '@/lib/utils'

/* ------------------------------------------------------------------ */
/* UnlockGate                                                          */
/* ------------------------------------------------------------------ */

interface UnlockGateProps {
  /** "register" = anónimo sin sesión; "limit" = registrado free sin cuota; "retry" = fallo transitorio. */
  variant?: 'register' | 'limit' | 'retry'
  title?: string
  body?: string
  ctaLabel?: string
  /** Solo para variant="retry": recarga la vista. */
  onRetry?: () => void
  className?: string
}

const DEFAULT_COPY = {
  register: {
    title: 'El análisis completo es gratis para registrados',
    body: 'Registrate sin costo para desbloquear hasta 3 pronósticos por día y ver EV, mercados y narrativa táctica de los partidos que elijas.',
    ctaLabel: 'Crear cuenta gratis',
    href: '/cuenta/registro',
  },
  limit: {
    title: 'Ya usaste tus 3 gratis de hoy',
    body: 'Volvé mañana para renovar tu cuota, o hacete PRO para ver análisis completo sin límite.',
    ctaLabel: 'Ver planes PRO →',
    href: '/planes',
  },
  retry: {
    title: 'El análisis está tardando más de lo habitual',
    body: 'El modelo puede tardar hasta un minuto en generar la predicción. Reintentá o volvé un rato después.',
    ctaLabel: 'Reintentar',
    href: null,
  },
} as const

/** Placeholder difuminado que simula el análisis bloqueado (patrón LockedMarkets). */
function LockedPlaceholder() {
  return (
    <div aria-hidden="true" className="flex flex-col gap-3 p-5">
      <div className="h-3 w-2/3 rounded bg-surface-raised" />
      <div className="grid grid-cols-3 gap-2">
        {[0, 1, 2].map((item) => (
          <div key={item} className="h-16 rounded-lg bg-surface-raised" />
        ))}
      </div>
      <div className="flex flex-col gap-2">
        {[0, 1, 2].map((item) => (
          <div key={item} className="flex items-center gap-3 rounded-lg bg-surface-raised/80 px-3 py-2.5">
            <div className="h-2.5 w-24 rounded bg-surface-inset" />
            <div className="ml-auto h-4 w-14 rounded bg-surface-inset" />
          </div>
        ))}
      </div>
    </div>
  )
}

export function UnlockGate({
  variant = 'register',
  title,
  body,
  ctaLabel,
  onRetry,
  className,
}: UnlockGateProps) {
  const copy = DEFAULT_COPY[variant]
  return (
    <div className={cn('relative overflow-hidden rounded-2xl border border-brand/30 bg-surface', className)}>
      <div className="pointer-events-none select-none opacity-40 blur-[3px]">
        <LockedPlaceholder />
      </div>
      <div className="absolute inset-0 flex flex-col items-center justify-center bg-background/55 px-5 py-8 text-center backdrop-blur-[1px]">
        <div className="flex size-11 items-center justify-center rounded-xl border border-brand/30 bg-brand/10 text-brand">
          <Lock size={18} aria-hidden="true" />
        </div>
        <p className="mt-3 text-sm font-semibold text-foreground">{title ?? copy.title}</p>
        <p className="mt-2 max-w-md text-xs leading-5 text-muted-foreground">{body ?? copy.body}</p>
        {variant === 'retry' ? (
          <button
            type="button"
            onClick={onRetry}
            className="mt-4 inline-flex min-h-10 items-center rounded-lg bg-brand px-4 text-xs font-bold text-primary-foreground transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
          >
            {ctaLabel ?? copy.ctaLabel}
          </button>
        ) : (
          <Link
            href={copy.href ?? '/planes'}
            className="mt-4 inline-flex min-h-10 items-center rounded-lg bg-brand px-4 text-xs font-bold text-primary-foreground transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand"
          >
            {ctaLabel ?? copy.ctaLabel}
          </Link>
        )}
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* UnlocksBanner                                                       */
/* ------------------------------------------------------------------ */

/** Contador "Te quedan X de 3 pronósticos gratis hoy" para usuarios free. */
export function UnlocksBanner({ remaining, className }: { remaining: number; className?: string }) {
  if (remaining == null) return null
  return (
    <div className={cn('flex flex-wrap items-center justify-between gap-2 rounded-xl border border-primary/25 bg-primary/[0.06] px-4 py-2.5', className)}>
      <p className="flex items-center gap-2 text-xs font-medium text-foreground">
        <Sparkles size={13} className="shrink-0 text-primary" aria-hidden="true" />
        <span>
          Te quedan <strong className="font-bold text-primary">{remaining} de 3</strong> pronósticos gratis hoy
        </span>
      </p>
      <Link href="/planes" className="text-[11px] font-semibold text-brand transition-colors hover:underline">
        Hacete PRO y sin límites →
      </Link>
    </div>
  )
}

/* ------------------------------------------------------------------ */
/* FreePicksGate                                                       */
/* ------------------------------------------------------------------ */

/**
 * Estado para usuarios registrados sin PRO en home/senales: la cuota de 3
 * se gasta SOLO cuando el usuario abre el detalle de un partido (nunca con
 * generación automática de boletos).
 */
export function FreePicksGate({ remaining }: { remaining: number | null }) {
  return (
    <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-primary/30 bg-primary/[0.04] px-6 py-12 text-center">
      <div className="flex size-11 items-center justify-center rounded-xl border border-primary/25 bg-primary/10 text-primary">
        <Target size={18} aria-hidden="true" />
      </div>
      <h2 className="mt-3 text-base font-semibold text-foreground">
        Elegí tus {remaining != null ? remaining : 3} pronósticos de hoy
      </h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">
        Tu plan gratuito incluye hasta 3 partidos por día con análisis completo. Abrí un partido para desbloquearlo; las señales y boletos se arman sobre los partidos que elegiste.
      </p>
      <Link href="/partidos" className="mt-5 inline-flex min-h-11 items-center rounded-lg bg-primary px-5 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
        Explorar partidos →
      </Link>
    </div>
  )
}
