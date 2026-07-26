import { cn } from '@/lib/utils'

interface EVBadgeProps {
  /** Expected value as a decimal fraction, e.g. 0.071 for +7.1% */
  value: number
  size?: 'sm' | 'md' | 'lg'
  label?: string
  className?: string
}

export function EVBadge({ value, size = 'sm', label, className }: EVBadgeProps) {
  const positive = value > 0
  const neutral = Math.abs(value) < 0.005

  return (
    <span
      className={cn(
        'num inline-flex items-center gap-1 rounded-md border font-medium',
        size === 'sm' && 'px-1.5 py-0.5 text-[11px]',
        size === 'md' && 'px-2 py-1 text-xs',
        size === 'lg' && 'px-3 py-1.5 text-sm',
        neutral
          ? 'border-border bg-muted/60 text-muted-foreground'
          : positive
            ? 'border-positive/30 bg-gradient-to-b from-positive/20 to-positive/5 text-positive'
            : 'border-negative/30 bg-gradient-to-b from-negative/15 to-negative/5 text-negative',
        className,
      )}
    >
      {label ? <span className="text-[10px] tracking-wide opacity-70">{label}</span> : null}
      {`${positive ? '+' : ''}${(value * 100).toFixed(1)}%`}
    </span>
  )
}
