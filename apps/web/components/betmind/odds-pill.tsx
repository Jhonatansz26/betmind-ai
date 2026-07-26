import { cn } from '@/lib/utils'

interface OddsPillProps {
  value: number
  className?: string
  size?: 'sm' | 'md'
}

/**
 * Betano-style odds pill: dark inset background, monospaced, right-anchored.
 * Used inside TicketLeg rows and any future market components.
 */
export function OddsPill({ value, size = 'sm', className }: OddsPillProps) {
  return (
    <span
      style={{ fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace' }}
      className={cn(
        'num shrink-0 rounded-md bg-slate-800/90 border border-slate-700/60 text-slate-100 font-mono font-semibold text-xs px-2.5 py-1 shadow-sm tabular-nums',
        size === 'md' && 'text-sm px-3 py-1.5',
        className,
      )}
    >
      {value.toFixed(2)}
    </span>
  )
}
