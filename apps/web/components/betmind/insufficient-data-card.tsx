import { InfoIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

interface InsufficientDataCardProps {
  /** Nombre del módulo que no tiene datos. Ej: "Modelo de Goles", "Árbitro" */
  title?: string
  /** Mensaje descriptivo de por qué no hay datos */
  message?: string
  /** Versión compacta para uso inline (menos padding, sin centrado vertical) */
  compact?: boolean
  className?: string
}

/**
 * InsufficientDataCard
 *
 * Reemplaza secciones vacías con un estado informativo elegante.
 * Evita renderizar tarjetas llenas de ceros o gráficos vacíos.
 *
 * Uso típico:
 *   - Árbitro sin designar (strictness=0, yellows=0, fouls=0)
 *   - Gráfico Poisson sin lambdas (lambdaHome=0, lambdaAway=0)
 *   - Panel táctico sin pros/contras del backend
 */
export function InsufficientDataCard({
  title = 'Datos Insuficientes',
  message = 'No hay datos históricos suficientes para generar este análisis.',
  compact = false,
  className,
}: InsufficientDataCardProps) {
  return (
    <div
      className={cn(
        'flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border bg-surface-inset text-center',
        compact ? 'px-4 py-4' : 'px-6 py-8',
        className,
      )}
      role="status"
      aria-label={`${title}: datos insuficientes`}
    >
      <span
        className={cn(
          'flex items-center justify-center rounded-full bg-muted/60',
          compact ? 'size-7' : 'size-9',
        )}
        aria-hidden
      >
        <InfoIcon
          className={cn('text-subtle', compact ? 'size-3.5' : 'size-4.5')}
          strokeWidth={1.75}
        />
      </span>

      <div className="flex flex-col gap-0.5">
        <p
          className={cn(
            'font-medium text-foreground',
            compact ? 'text-[11px]' : 'text-xs',
          )}
        >
          {title}
        </p>
        <p
          className={cn(
            'text-subtle',
            compact ? 'text-[10px] leading-snug' : 'text-xs leading-snug',
          )}
        >
          {message}
        </p>
      </div>
    </div>
  )
}
