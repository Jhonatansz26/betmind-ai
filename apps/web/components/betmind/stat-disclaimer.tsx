import { Info } from 'lucide-react'

import { STAT_DISCLAIMER_TEXT } from '@/lib/disclaimers'
import { cn } from '@/lib/utils'

export function StatDisclaimer({ className }: { className?: string }) {
  return (
    <p className={cn('flex items-start gap-1.5 text-[11px] leading-5 text-subtle', className)}>
      <Info size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
      <span>{STAT_DISCLAIMER_TEXT}</span>
    </p>
  )
}
