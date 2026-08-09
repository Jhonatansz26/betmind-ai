'use client'

import * as React from 'react'
import { FlaskConical, LockKeyhole, UnlockKeyhole } from 'lucide-react'

import { isProUser, setDevProFlag } from '@/lib/subscription'

export function DevProToggle() {
  const [isPro, setIsPro] = React.useState(false)

  React.useEffect(() => {
    setIsPro(isProUser())
  }, [])

  if (process.env.NODE_ENV === 'production') return null

  function toggle() {
    const next = !isPro
    setDevProFlag(next)
    setIsPro(next)
  }

  return (
    <button type="button" role="switch" aria-checked={isPro} onClick={toggle} className="fixed bottom-[calc(4.5rem+env(safe-area-inset-bottom))] left-4 z-50 inline-flex min-h-9 items-center gap-2 rounded-full border border-warning/40 bg-surface/95 px-3 text-[10px] font-semibold text-warning shadow-lg backdrop-blur md:bottom-4">
      <FlaskConical size={13} aria-hidden="true" />
      Simular PRO (dev)
      {isPro ? <UnlockKeyhole size={12} aria-hidden="true" /> : <LockKeyhole size={12} aria-hidden="true" />}
    </button>
  )
}
