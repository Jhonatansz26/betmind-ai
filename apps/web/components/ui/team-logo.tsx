'use client'

import * as React from 'react'
import { cn } from '@/lib/utils'

interface TeamLogoProps {
  src?: string | null
  teamName: string
  teamId?: number | null
  size?: number
  className?: string
}

function cdnutf(url: string, id: number) {
  return `https://media.api-sports.io/football/teams/${id}.png`
}

function buildInitials(name: string, count = 2) {
  return name
    .split(' ')
    .filter(w => w.length > 1 && !['de', 'la', 'y', 'e', 'of', 'the', '&', 'fc', 'cf', 'ac'].includes(w.toLowerCase()))
    .map(w => w[0] ?? '')
    .join('')
    .slice(0, count)
    .toUpperCase() || name.slice(0, count).toUpperCase()
}

/* ------------------------------------------------------------------ */
/* SVG Shield fallback                                                 */
/* ------------------------------------------------------------------ */

function ShieldFallback({
  initials,
  size,
  className,
}: {
  initials: string
  size: number
  className?: string
}) {
  const width = size
  const height = Math.round(size * 1.05)
  const borderW = Math.max(1, Math.round(size * 0.02))
  const fontSize = Math.round(size * 0.32)
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      className={cn('shrink-0 select-none', className)}
      aria-hidden
    >
      <defs>
        <linearGradient id={`shield-grad-${initials}`} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="var(--surface-raised)" />
          <stop offset="100%" stopColor="var(--surface-inset)" />
        </linearGradient>
      </defs>
      <path
        d={`M${borderW},${Math.round(height * 0.15)} L${borderW},${Math.round(height * 0.42)} C${borderW},${Math.round(height * 0.78)} ${Math.round(width * 0.32)},${height - borderW} ${Math.round(width * 0.5)},${height - borderW} C${Math.round(width * 0.68)},${height - borderW} ${width - borderW},${Math.round(height * 0.78)} ${width - borderW},${Math.round(height * 0.42)} L${width - borderW},${Math.round(height * 0.15)} Z`}
        fill="url(#shield-grad-${initials})"
        stroke="var(--border)"
        strokeWidth={borderW}
      />
      <text
        x={width / 2}
        y={height / 2}
        textAnchor="middle"
        dominantBaseline="central"
        fill="var(--foreground)"
        fontWeight={700}
        fontFamily="system-ui, -apple-system, sans-serif"
        fontSize={fontSize}
      >
        {initials}
      </text>
    </svg>
  )
}

/* ------------------------------------------------------------------ */
/* TeamLogo                                                            */
/* ------------------------------------------------------------------ */

export function TeamLogo({ src, teamName, teamId, size = 32, className }: TeamLogoProps) {
  const [tier, setTier] = React.useState<1 | 2 | 3>(src ? 1 : teamId ? 2 : 3)

  React.useEffect(() => {
    setTier(src ? 1 : teamId ? 2 : 3)
  }, [src, teamId])

  const initials = React.useMemo(() => buildInitials(teamName), [teamName])

  const onError = React.useCallback(() => {
    setTier(prev => (prev === 1 && teamId ? 2 : 3))
  }, [teamId])

  const onCdnError = React.useCallback(() => {
    setTier(3)
  }, [])

  // Tier 1: direct URL from API
  if (tier === 1 && src) {
    return (
      <img
        src={src}
        alt={teamName}
        referrerPolicy="no-referrer"
        loading="lazy"
        onError={onError}
        className={cn('shrink-0 object-contain', className)}
        style={{ width: size, height: size }}
      />
    )
  }

  // Tier 2: CDN fallback (api-sports.io)
  if (tier === 2 && teamId) {
    const cdnUrl = cdnutf('', teamId)
    return (
      <img
        src={cdnUrl}
        alt={teamName}
        referrerPolicy="no-referrer"
        loading="lazy"
        onError={onCdnError}
        className={cn('shrink-0 object-contain', className)}
        style={{ width: size, height: size }}
      />
    )
  }

  // Tier 3: SVG shield
  return <ShieldFallback initials={initials} size={size} className={className} />
}
