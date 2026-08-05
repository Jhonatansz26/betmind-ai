'use client'

import * as React from 'react'

import { cn } from '@/lib/utils'

export type DateFilter = 'yesterday' | 'today' | 'tomorrow' | 'all'

const OPTIONS: { value: DateFilter; label: string }[] = [
  { value: 'yesterday', label: 'Ayer' },
  { value: 'today', label: 'Hoy' },
  { value: 'tomorrow', label: 'Mañana' },
  { value: 'all', label: 'Todas' },
]

interface DateSelectorProps {
  value: DateFilter
  onChange: (value: DateFilter) => void
  className?: string
}

export function DateSelector({ value, onChange, className }: DateSelectorProps) {
  const dateInfo = formatDateTitle(value, new Date())

  return (
    <div
      role="radiogroup"
      aria-label="Filtrar por fecha"
      className={cn('flex items-center justify-between gap-2 rounded-lg border border-border/60 bg-surface/30 p-1 text-xs', className)}
    >
      {OPTIONS.map((opt) => (
        <button
          key={opt.value}
          type="button"
          role="radio"
          aria-checked={value === opt.value}
          onClick={() => onChange(opt.value)}
          className={cn(
            'rounded-md px-3 py-1.5 text-xs transition-colors',
            value === opt.value
              ? 'border border-primary/30 bg-primary/15 font-semibold text-primary shadow-sm'
              : 'text-muted-foreground hover:bg-surface/50 hover:text-foreground',
          )}
        >
          {opt.label}
        </button>
      ))}
      <span className="ml-auto hidden items-baseline gap-1.5 border-l border-border/50 pl-2 font-mono tabular-nums sm:flex">
        <span className="text-xs font-bold text-foreground">{dateInfo.subtitle.split(' · ')[0]}</span>
        <span className="text-[10px] text-muted-foreground">{dateInfo.subtitle.split(' · ')[1]}</span>
      </span>
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

  const date = new Date(today)
  if (filter === 'yesterday') date.setDate(date.getDate() - 1)
  if (filter === 'tomorrow') date.setDate(date.getDate() + 1)

  const iso = new Intl.DateTimeFormat('en-CA', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    timeZone: 'America/Bogota',
  }).format(date)

  if (filter === 'all') return { title: 'Todos los Partidos', subtitle: `${iso} · ${fmt.format(today)}` }
  const title = filter === 'yesterday' ? 'Ayer' : filter === 'tomorrow' ? 'Mañana' : 'Hoy'
  return { title, subtitle: `${iso} · ${fmt.format(date)}` }
}

export function formatDateKey(filter: DateFilter, today: Date): string | undefined {
  if (filter === 'all') return undefined
  return formatDateTitle(filter, today).subtitle.split(' · ')[0]
}
