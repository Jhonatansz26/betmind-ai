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
    const files = Array.from(e.dataTransfer.files)
    if (files.length > 0) {
      console.log('Dropped files:', files)
    }
  }

  function handleFileSelect(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || [])
    if (files.length > 0) {
      console.log('Selected files:', files)
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-3">
        <h2 className="font-serif text-2xl italic text-foreground">Ticket Scanner</h2>
        <p className="max-w-2xl text-pretty text-sm leading-relaxed text-muted-foreground">
          Upload a screenshot of your betting ticket to analyze it with AI vision.
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
            Drag and drop your ticket screenshot here
          </p>
          <p className="text-xs text-muted-foreground">or</p>
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-md border border-border bg-background px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-muted">
            <UploadIcon className="size-4" />
            Browse files
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
          Supported formats: PNG, JPG, WEBP. Maximum file size: 10MB.
        </p>
      </div>

      <div className="rounded-lg border border-border bg-card p-6">
        <h3 className="mb-3 text-sm font-medium text-foreground">How it works</h3>
        <ol className="flex flex-col gap-3 text-sm text-muted-foreground">
          <li className="flex gap-3">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
              1
            </span>
            <span>Upload a screenshot of your betting ticket (bet slip, parlay, etc.)</span>
          </li>
          <li className="flex gap-3">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
              2
            </span>
            <span>Our AI vision model extracts all selections, odds, and bet types</span>
          </li>
          <li className="flex gap-3">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
              3
            </span>
            <span>We analyze each leg against our Poisson model and EV calculations</span>
          </li>
          <li className="flex gap-3">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
              4
            </span>
            <span>Get a detailed report with recommendations and risk assessment</span>
          </li>
        </ol>
      </div>
    </div>
  )
}
