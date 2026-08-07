'use client'

import * as React from 'react'
import { cn } from '@/lib/utils'

interface LeagueLogoProps {
  logoUrl: string | null
  flag: string
  label?: string
  className?: string
  size?: 'sm' | 'md' | 'lg'
}

const sizeMap = {
  sm: 'w-4 h-4',
  md: 'w-6 h-6',
  lg: 'w-8 h-8',
}

const containerSizeMap = {
  sm: 'size-4',
  md: 'size-6',
  lg: 'size-8',
}

export function LeagueLogo({ logoUrl, flag: _flag, label, className, size = 'md' }: LeagueLogoProps) {
  const [imgError, setImgError] = React.useState(false)
  const fallbackLabel = label
    ? label.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase()
    : 'LG'

  if (!logoUrl || imgError) {
    return <span aria-hidden className={cn('inline-flex shrink-0 items-center justify-center rounded border border-border/60 bg-surface-raised font-mono text-xs font-semibold text-subtle', sizeMap[size], className)}>{fallbackLabel}</span>
  }

  return (
    <span
      className={cn(
        'inline-flex shrink-0 items-center justify-center rounded-full bg-white/10 p-0.5',
        containerSizeMap[size],
        className,
      )}
    >
      <img
        src={logoUrl}
        alt=""
        aria-hidden
        referrerPolicy="no-referrer"
        className="h-full w-full object-contain"
        onError={() => setImgError(true)}
        loading="lazy"
      />
    </span>
  )
}
