'use client'

import * as React from 'react'
import { cn } from '@/lib/utils'

interface TeamLogoProps {
  logoUrl: string | null
  teamName: string
  className?: string
  size?: 'sm' | 'md' | 'lg'
}

const sizeMap = {
  sm: 'w-4 h-4',
  md: 'w-5 h-5',
  lg: 'w-7 h-7',
}

const initialsSizeMap = {
  sm: 'text-[8px]',
  md: 'text-[10px]',
  lg: 'text-xs',
}

export function TeamLogo({ logoUrl, teamName, className, size = 'md' }: TeamLogoProps) {
  const [imgError, setImgError] = React.useState(false)

  const initials = teamName
    .split(' ')
    .slice(0, 2)
    .map((w) => w[0] ?? '')
    .join('')
    .toUpperCase()

  if (!logoUrl || imgError) {
    return (
      <span
        aria-hidden
        className={cn(
          'inline-flex shrink-0 items-center justify-center rounded-full bg-muted font-bold text-muted-foreground',
          sizeMap[size],
          initialsSizeMap[size],
          className,
        )}
      >
        {initials}
      </span>
    )
  }

  return (
    <img
      src={logoUrl}
      alt={teamName}
      referrerPolicy="no-referrer"
      className={cn('shrink-0 object-contain', sizeMap[size], className)}
      onError={() => setImgError(true)}
      loading="lazy"
    />
  )
}
