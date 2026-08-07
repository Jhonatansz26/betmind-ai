'use client'

import { CalendarDays } from 'lucide-react'

import { cn } from '@/lib/utils'

export type DateFilter = 'today' | 'tomorrow' | 'all'

interface DateSelectorProps {
  value: DateFilter
  onChange: (value: DateFilter) => void
}

const OPTIONS: Array<{ id: DateFilter; label: string }> = [
  { id: 'today', label: 'Hoy' },
  { id: 'tomorrow', label: 'Mañana' },
  { id: 'all', label: 'Todas' },
]

function cotDate(date: Date) {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'America/Bogota',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date)
}

export function formatDateKey(filter: DateFilter, date = new Date()) {
  if (filter === 'all') return undefined
  const next = new Date(date)
  if (filter === 'tomorrow') next.setUTCDate(next.getUTCDate() + 1)
  return cotDate(next)
}

export function formatDateTitle(filter: DateFilter, date = new Date()) {
  if (filter === 'all') {
    return { title: 'Todas las oportunidades', subtitle: 'Ventana completa de partidos disponibles' }
  }

  const target = new Date(date)
  if (filter === 'tomorrow') target.setUTCDate(target.getUTCDate() + 1)

  return {
    title: filter === 'today' ? 'Hoy' : 'Mañana',
    subtitle: new Intl.DateTimeFormat('es-CO', {
      weekday: 'long',
      day: 'numeric',
      month: 'long',
      timeZone: 'America/Bogota',
    }).format(target),
  }
}

export function DateSelector({ value, onChange }: DateSelectorProps) {
  return (
    <div className="inline-flex items-center gap-1 rounded-lg border border-border/70 bg-surface/70 p-1" role="group" aria-label="Ventana temporal">
      <CalendarDays className="ml-2 size-4 text-subtle" aria-hidden="true" />
      {OPTIONS.map((option) => (
        <button
          key={option.id}
          type="button"
          aria-pressed={value === option.id}
          onClick={() => onChange(option.id)}
          className={cn(
            'rounded-md px-3 py-1.5 text-xs font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-primary/60',
            value === option.id
              ? 'bg-surface-raised text-foreground shadow-sm'
              : 'text-muted-foreground hover:text-foreground',
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  )
}
