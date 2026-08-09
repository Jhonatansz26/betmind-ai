export function ResponsibleGamingFooter() {
  return (
    <footer className="border-t border-border px-4 py-6 text-center text-xs leading-5 text-subtle sm:px-6">
      <p>
        BetMind AI es una herramienta de análisis estadístico y no opera apuestas ni gestiona dinero. Si sientes que el juego afecta tu vida, tu trabajo o tus relaciones, busca ayuda profesional. Más información:{' '}
        <a href="https://www.coljuegos.gov.co" target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">
          coljuegos.gov.co
        </a>
      </p>
    </footer>
  )
}
