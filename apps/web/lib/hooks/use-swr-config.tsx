'use client'

import { SWRConfig } from 'swr'
import type { ReactNode } from 'react'

/**
 * Global SWR configuration provider.
 *
 * Key defaults:
 * - dedupingInterval 30s  → two components mounting at the same time share
 *   a single in-flight request AND the result is reused for 30 seconds.
 * - revalidateOnFocus false → avoids re-fetching every time the user alt-tabs.
 * - revalidateOnReconnect true → still updates when the user comes back online.
 * - errorRetryCount 2 → don't hammer a down server.
 */
export function SWRProvider({ children }: { children: ReactNode }) {
  return (
    <SWRConfig
      value={{
        dedupingInterval: 30_000,
        revalidateOnFocus: false,
        revalidateOnReconnect: true,
        errorRetryCount: 2,
        // Provide a no-op fetcher as default so hooks that pass their own
        // fetcher function are not affected.
        // Individual hooks define their own fetcher — this is just a safety net.
      }}
    >
      {children}
    </SWRConfig>
  )
}
