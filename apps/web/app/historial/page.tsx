import { Suspense } from 'react'

import { HistoryPage } from '@/components/betmind/history-page'

export default function HistoryRoute() {
  return <Suspense fallback={<div className="min-h-svh bg-background" />}><HistoryPage /></Suspense>
}
