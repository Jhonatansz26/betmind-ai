'use client'

import * as React from 'react'
import { CameraIcon, UploadIcon } from 'lucide-react'
import { cn } from '@/lib/utils'

export function ScannerEmptyState() {
  const [isDragOver, setIsDragOver] = React.useState(false)

  function handleDragOver(e: React.DragEvent) {
    e.preventDefault()
    setIsDragOver(true)
  }

  function handleDragLeave(e: React.DragEvent) {
    e.preventDefault()
    setIsDragOver(false)
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault()
    setIsDragOver(false)
    // File analysis is not wired yet; keep the drop interaction quiet.
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    if (e.target.files?.length) e.target.value = ''
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3">
        <h2 className="font-serif text-2xl italic text-foreground">Escáner de Boletos</h2>
        <p className="max-w-2xl text-pretty text-sm leading-relaxed text-muted-foreground">
          Sube una captura de tu boleto de apuestas para analizarlo con IA.
        </p>
      </div>

      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={cn(
          'flex flex-col items-center justify-center gap-4 rounded-xl border-2 border-dashed p-12 text-center transition-colors',
          isDragOver
            ? 'border-primary bg-primary/5'
            : 'border-border hover:border-primary/50 hover:bg-muted/30',
        )}
      >
        <div className="flex size-16 items-center justify-center rounded-full bg-primary/10">
          <CameraIcon className="size-8 text-primary" />
        </div>

        <div className="flex flex-col gap-2">
          <p className="text-sm font-medium text-foreground">
            Arrastra o sube una captura de tu boleto para analizarlo con IA
          </p>
          <p className="text-xs text-muted-foreground">o</p>
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted">
            <UploadIcon className="size-4" />
            Seleccionar archivo
            <input
              type="file"
              accept="image/*"
              multiple
              className="sr-only"
              onChange={handleFileSelect}
            />
          </label>
        </div>

        <p className="mt-2 max-w-sm text-xs text-muted-foreground">
          Formatos soportados: PNG, JPG, WEBP. Tamaño máximo: 10MB.
        </p>
      </div>

      <div className="rounded-lg border border-border bg-card p-6">
        <h3 className="mb-3 text-sm font-medium text-foreground">Cómo funciona</h3>
        <ol className="flex flex-col gap-3 text-sm text-muted-foreground">
          <li className="flex gap-3">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
              1
            </span>
            <span>Sube una captura de tu boleto de apuestas (combinada, parlay, etc.)</span>
          </li>
          <li className="flex gap-3">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
              2
            </span>
            <span>Nuestro modelo de visión IA extrae todas las selecciones, cuotas y tipos de apuesta</span>
          </li>
          <li className="flex gap-3">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
              3
            </span>
            <span>Analizamos cada pata contra nuestro modelo Poisson y cálculos de VE</span>
          </li>
          <li className="flex gap-3">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
              4
            </span>
            <span>Obtén un reporte detallado con recomendaciones y evaluación de riesgo</span>
          </li>
        </ol>
      </div>
    </div>
  )
}
