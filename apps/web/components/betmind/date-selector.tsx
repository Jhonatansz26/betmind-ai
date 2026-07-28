'use client'

import * as React from 'react'

import { cn } from '@/lib/utils'

export type DateFilter = 'today' | 'tomorrow' | 'all'

const OPTIONS: { value: DateFilter; label: string }[] = [
  { value: 'today', label: 'Hoy' },
  { value: 'tomorrow', label: 'Mañana' },
  { value: 'all', label: 'Ver Todos' },
]

interface DateSelectorProps {
  value: DateFilter
  onChange: (value: DateFilter) => void
  className?: string
}

export function DateSelector({ value, onChange, className }: DateSelectorProps) {
  return (
    <div className={cn('inline-flex rounded-lg border border-border bg-muted/60 p-0.5', className)}>
      {OPTIONS.map((opt) => (
        <button
          key={opt.value}
          type="button"
          onClick={() => onChange(opt.value)}
          className={cn(
            'rounded-md px-3 py-1.5 text-xs font-medium transition-colors',
            value === opt.value
              ? 'bg-background text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

export function formatDateTitle(filter: DateFilter, today: Date): { title: string; subtitle: string } {
  const fmt = new Intl.DateTimeFormat('es-CO', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'America/Bogota',
  })

  if (filter === 'today') {
    return { title: 'Hoy', subtitle: fmt.format(today) }
  }
  if (filter === 'tomorrow') {
    const tomorrow = new Date(today)
    tomorrow.setDate(tomorrow.getDate() + 1)
    return { title: 'Mañana', subtitle: fmt.format(tomorrow) }
  }
  return { title: 'Todos los Partidos', subtitle: fmt.format(today) }
}
