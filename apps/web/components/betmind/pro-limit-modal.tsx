'use client'

import * as React from 'react'
import Link from 'next/link'
import { X } from 'lucide-react'

import { PRO_LIMIT_REACHED_EVENT } from '@/lib/subscription'

const COPY = {
  generations: {
    title: 'Ya generaste tus 2 boletos gratis de hoy',
    body: 'Con PRO generás boletos ilimitados en los 3 perfiles de riesgo. Desbloquealo cuando estés listo.',
    secondary: 'Entendido, vuelvo mañana',
  },
  saved: {
    title: 'Tu plan gratuito guarda hasta 5 boletos',
    body: 'Con PRO guardás todos los que quieras y accedés a tu historial completo de ROI.',
    secondary: 'Entendido',
  },
} as const

export function ProLimitModal({ kind, onClose }: { kind: keyof typeof COPY; onClose: () => void }) {
  const copy = COPY[kind]
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 px-4 backdrop-blur-sm" role="presentation" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose() }}>
      <section role="dialog" aria-modal="true" aria-labelledby="pro-limit-title" className="relative w-full max-w-md rounded-2xl border border-border bg-card p-6 shadow-2xl">
        <button type="button" onClick={onClose} aria-label="Cerrar" className="absolute right-4 top-4 text-subtle hover:text-foreground"><X size={17} aria-hidden="true" /></button>
        <h2 id="pro-limit-title" className="pr-7 text-lg font-semibold text-foreground">{copy.title}</h2>
        <p className="mt-3 text-sm leading-6 text-muted-foreground">{copy.body}</p>
        <div className="mt-6 flex flex-col gap-2 sm:flex-row sm:justify-end">
          <button type="button" onClick={onClose} className="order-2 min-h-10 rounded-lg border border-border px-4 text-xs font-semibold text-muted-foreground hover:bg-surface-raised sm:order-1">{copy.secondary}</button>
          <Link href="/planes" onClick={onClose} className="order-1 inline-flex min-h-10 items-center justify-center rounded-lg bg-primary px-4 text-xs font-semibold text-primary-foreground hover:opacity-90 sm:order-2">Desbloquear PRO →</Link>
        </div>
      </section>
    </div>
  )
}

export function ProLimitModalHost() {
  const [kind, setKind] = React.useState<keyof typeof COPY | null>(null)

  React.useEffect(() => {
    const handleLimit = (event: Event) => {
      const detail = (event as CustomEvent<{ kind?: keyof typeof COPY }>).detail
      if (detail?.kind) setKind(detail.kind)
    }
    window.addEventListener(PRO_LIMIT_REACHED_EVENT, handleLimit)
    return () => window.removeEventListener(PRO_LIMIT_REACHED_EVENT, handleLimit)
  }, [])

  return kind ? <ProLimitModal kind={kind} onClose={() => setKind(null)} /> : null
}
