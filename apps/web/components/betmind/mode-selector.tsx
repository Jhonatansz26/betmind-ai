'use client'

import { MODE_META, type Mode } from '@/lib/betmind'
import { cn } from '@/lib/utils'

const MODES: Mode[] = ['EDGE', 'VALUE', 'BOLD']

interface ModeSelectorProps {
  value: Mode
  onChange: (mode: Mode) => void
}

export function ModeSelector({ value, onChange }: ModeSelectorProps) {
  return (
    <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Ticket mode">
      {MODES.map((mode) => {
        const meta = MODE_META[mode]
        const active = value === mode
        return (
          <button
            key={mode}
            type="button"
            role="radio"
            aria-checked={active}
            onClick={() => onChange(mode)}
            className={cn(
              'inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1.5 text-xs font-medium transition-colors',
              active
                ? cn(meta.border, meta.bg, meta.text)
                : 'border-border bg-background/40 text-muted-foreground hover:text-foreground',
            )}
          >
            <span aria-hidden>{meta.glyph}</span>
            {meta.label}
          </button>
        )
      })}
    </div>
  )
}
