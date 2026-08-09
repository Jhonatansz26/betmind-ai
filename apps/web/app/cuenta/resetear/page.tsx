'use client'

import * as React from 'react'
import { Suspense } from 'react'
import Link from 'next/link'
import { useSearchParams } from 'next/navigation'

import { resetPassword } from '@/lib/auth'

function ResetearPageContent() {
  const searchParams = useSearchParams()
  const token = searchParams.get('token')

  const [password, setPassword] = React.useState('')
  const [confirm, setConfirm] = React.useState('')
  const [error, setError] = React.useState<string | null>(null)
  const [success, setSuccess] = React.useState(false)
  const [loading, setLoading] = React.useState(false)

  // No token in URL — show invalid link message
  if (!token) {
    return (
      <div className="w-full max-w-sm">
        <div className="rounded-xl border border-border bg-card p-8 shadow-sm text-center">
          <p className="mb-4 text-sm font-medium text-foreground">
            Este link no es válido. Solicitá uno nuevo.
          </p>
          <Link
            href="/cuenta/olvide-password"
            className="text-sm font-semibold text-primary hover:underline"
          >
            Solicitar link de recuperación
          </Link>
        </div>
      </div>
    )
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setError(null)

    if (password.length < 8) {
      setError('La contraseña debe tener al menos 8 caracteres.')
      return
    }
    if (password !== confirm) {
      setError('Las contraseñas no coinciden.')
      return
    }

    setLoading(true)
    try {
      await resetPassword(token!, password)
      setSuccess(true)
    } catch (err) {
      // 400 from backend = token invalid or expired
      setError('Este link expiró o no es válido. Solicitá uno nuevo.')
      console.error('[reset-password]', err)
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <div className="w-full max-w-sm">
        <div className="rounded-xl border border-border bg-card p-8 shadow-sm text-center flex flex-col gap-4">
          <div
            role="status"
            className="rounded-lg border border-positive/30 bg-positive/10 px-4 py-3 text-sm font-medium text-positive"
          >
            Contraseña actualizada correctamente.
          </div>
          <Link
            href="/cuenta/login"
            className="flex w-full items-center justify-center rounded-lg bg-primary py-3 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90"
          >
            Ir al inicio de sesión
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="w-full max-w-sm">
      <div className="rounded-xl border border-border bg-card p-8 shadow-sm">
        <h1 className="mb-1 text-xl font-bold tracking-tight text-foreground">Nueva contraseña</h1>
        <p className="mb-6 text-sm text-muted-foreground">
          Elegí una contraseña nueva para tu cuenta.
        </p>

        {error && (
          <div
            role="alert"
            className="mb-4 rounded-lg border border-negative/30 bg-negative/10 px-4 py-3 text-sm font-medium text-negative"
          >
            {error}{' '}
            {error.includes('expiró') && (
              <Link
                href="/cuenta/olvide-password"
                className="font-semibold underline underline-offset-2"
              >
                Solicitar uno nuevo
              </Link>
            )}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="reset-password"
              className="text-xs font-semibold text-muted-foreground uppercase tracking-wider"
            >
              Nueva contraseña <span className="font-normal normal-case text-muted-foreground/60">(mín. 8 caracteres)</span>
            </label>
            <input
              id="reset-password"
              type="password"
              autoComplete="new-password"
              required
              minLength={8}
              maxLength={128}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="rounded-lg border border-border bg-surface/40 px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
              placeholder="••••••••"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="reset-confirm"
              className="text-xs font-semibold text-muted-foreground uppercase tracking-wider"
            >
              Confirmar contraseña
            </label>
            <input
              id="reset-confirm"
              type="password"
              autoComplete="new-password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="rounded-lg border border-border bg-surface/40 px-3 py-2.5 text-sm text-foreground placeholder:text-muted-foreground/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
              placeholder="••••••••"
            />
          </div>

          <button
            type="submit"
            id="reset-submit"
            disabled={loading}
            className="mt-2 flex w-full items-center justify-center rounded-lg bg-primary py-3 text-sm font-semibold text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-50"
          >
            {loading ? 'Actualizando…' : 'Actualizar contraseña'}
          </button>
        </form>
      </div>
    </div>
  )
}

export default function ResetearPage() {
  return (
    <Suspense fallback={<div className="h-64 w-full max-w-sm rounded-xl border border-border bg-card skeleton" />}>
      <ResetearPageContent />
    </Suspense>
  )
}
