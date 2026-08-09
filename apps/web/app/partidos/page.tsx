import { Suspense } from 'react'

import { MatchesPage } from '@/components/betmind/matches-page'

export default function MatchesRoute() {
  return <Suspense fallback={<div className="min-h-svh bg-background" />}><MatchesPage /></Suspense>
}
