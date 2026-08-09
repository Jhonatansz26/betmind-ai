'use client'

/**
 * useProStatus — thin wrapper around useIsPro() for backward compatibility.
 * All existing consumers of useProStatus() continue to work without changes.
 */
export { useIsPro as useProStatus } from '@/lib/subscription'
