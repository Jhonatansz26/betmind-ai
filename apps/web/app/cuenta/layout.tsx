import type { Metadata } from 'next'
import Link from 'next/link'

export const metadata: Metadata = {
  title: 'Cuenta — BetMind AI',
}

export default function CuentaLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col bg-background">
      {/* Minimal header — no dashboard nav */}
      <header className="flex h-16 shrink-0 items-center border-b border-border/60 px-6">
        <Link
          href="/"
          className="flex items-center gap-3 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 rounded-md"
          aria-label="BetMind AI, ir al inicio"
        >
          <div className="flex size-8 items-center justify-center rounded-md border border-positive/40 bg-positive/10 font-mono text-xs font-bold text-positive">
            BM
          </div>
          <span className="text-sm font-semibold tracking-tight text-foreground">BetMind AI</span>
        </Link>
      </header>

      {/* Page content */}
      <main className="flex flex-1 items-center justify-center px-4 py-12">
        {children}
      </main>

      <footer className="border-t border-border/40 px-6 py-4 text-center text-[11px] text-muted-foreground">
        BetMind no opera casas de apuestas. Es una herramienta de análisis estadístico.
      </footer>
    </div>
  )
}
