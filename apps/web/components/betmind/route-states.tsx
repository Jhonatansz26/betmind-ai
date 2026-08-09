import { AlertCircle, RefreshCw } from 'lucide-react'

export function RouteError({ onRetry, label = 'los datos' }: { onRetry: () => void; label?: string }) {
  return (
    <div role="alert" className="flex flex-col items-center justify-center rounded-2xl border border-negative/25 bg-negative/5 px-6 py-10 text-center">
      <AlertCircle size={20} className="text-negative" aria-hidden="true" />
      <h2 className="mt-3 text-base font-semibold text-foreground">No pudimos actualizar {label}</h2>
      <p className="mt-2 max-w-md text-sm leading-6 text-muted-foreground">La conexión con BetMind AI falló. Tus datos guardados no se han modificado.</p>
      <button type="button" onClick={onRetry} className="mt-5 inline-flex min-h-11 items-center gap-2 rounded-lg bg-primary px-4 text-sm font-semibold text-primary-foreground transition-opacity hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
        <RefreshCw size={15} aria-hidden="true" /> Reintentar
      </button>
    </div>
  )
}

export function RouteSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div aria-busy="true" className="flex flex-col gap-3">
      <span className="sr-only">Cargando datos…</span>
      {Array.from({ length: rows }, (_, index) => <div key={index} className="h-28 rounded-xl border border-border bg-card skeleton" />)}
    </div>
  )
}
