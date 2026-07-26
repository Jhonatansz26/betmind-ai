'use client'

import * as React from 'react'
import { cn } from '@/lib/utils'

interface ConfidenceBarProps {
  /** Score from 0 to 100 */
  score: number
  className?: string
  showLabel?: boolean
}

function colorForScore(score: number) {
  if (score > 70) return 'bg-positive'
  if (score >= 50) return 'bg-warning'
  return 'bg-negative'
}

function textColorForScore(score: number) {
  if (score > 70) return 'text-positive'
  if (score >= 50) return 'text-warning'
  return 'text-negative'
}

/**
 * Animated horizontal confidence bar — replaces the "72/100" numeric score.
 * Fills from 0 → score on mount with a smooth 600ms ease-out animation.
 */
export function ConfidenceBar({ score, className, showLabel = true }: ConfidenceBarProps) {
  const [width, setWidth] = React.useState(0)

  React.useEffect(() => {
    const id = window.requestAnimationFrame(() => {
      window.setTimeout(() => setWidth(score), 50)
    })
    return () => window.cancelAnimationFrame(id)
  }, [score])

  return (
    <div className={cn('flex flex-col gap-1', className)}>
      {showLabel && (
        <div className="flex items-baseline justify-between gap-1">
          <span className="text-[10px] font-medium tracking-wide text-subtle uppercase">
            Confianza
          </span>
          <span className={cn('num text-[11px] font-semibold', textColorForScore(score))}>
            {score}
            <span className="text-subtle font-normal">/100</span>
          </span>
        </div>
      )}
      <div className="h-[3px] w-full overflow-hidden rounded-full bg-border">
        <div
          className={cn('h-full rounded-full transition-[width] duration-[600ms] ease-out', colorForScore(score))}
          style={{ width: `${width}%` }}
          role="progressbar"
          aria-valuenow={score}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={`Confianza del modelo: ${score} de 100`}
        />
      </div>
    </div>
  )
}
