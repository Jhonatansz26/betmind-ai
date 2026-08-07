import type { Ticket } from './betmind'
import { formatMarketName } from './formatMarketName'
import { formatEV, formatOdds } from './formatters'

function ticketSummary(ticket: Ticket): string {
  const heroOdds = ticket.legs.reduce((total, leg) => total * leg.odds, 1)
  const legs = ticket.legs
    .map((leg, index) => `${index + 1}. ${leg.match} · ${formatMarketName(leg.market)} @${formatOdds(leg.odds)}`)
    .join('\n')
  return `${ticket.mode} · Cuota HERO @${formatOdds(heroOdds)}\n${legs}\n\nBetMind AI · ${window.location.href}`
}

function drawWrappedText(
  context: CanvasRenderingContext2D,
  text: string,
  x: number,
  y: number,
  maxWidth: number,
  lineHeight: number,
): number {
  const words = text.split(' ')
  let line = ''
  let currentY = y
  for (const word of words) {
    const candidate = line ? `${line} ${word}` : word
    if (context.measureText(candidate).width > maxWidth && line) {
      context.fillText(line, x, currentY)
      currentY += lineHeight
      line = word
    } else {
      line = candidate
    }
  }
  if (line) {
    context.fillText(line, x, currentY)
    currentY += lineHeight
  }
  return currentY
}

async function renderTicketImage(ticket: Ticket): Promise<Blob> {
  const width = 1200
  const rowHeight = 92
  const height = 280 + ticket.legs.length * rowHeight
  const canvas = document.createElement('canvas')
  canvas.width = width
  canvas.height = height
  const context = canvas.getContext('2d')
  if (!context) throw new Error('Canvas no disponible')

  context.fillStyle = '#0c1016'
  context.fillRect(0, 0, width, height)
  context.fillStyle = '#3de3a5'
  context.fillRect(0, 0, width, 8)
  context.fillStyle = '#f2f5f8'
  context.font = '700 34px ui-monospace, SFMono-Regular, Menlo, monospace'
  context.fillText('BETMIND AI', 56, 72)
  context.fillStyle = '#9aa6b2'
  context.font = '600 18px ui-monospace, SFMono-Regular, Menlo, monospace'
  context.fillText(`${ticket.mode} · LEDGER CUANTITATIVO`, 56, 106)

  const heroOdds = ticket.legs.reduce((total, leg) => total * leg.odds, 1)
  context.fillStyle = '#f2f5f8'
  context.font = '700 58px ui-monospace, SFMono-Regular, Menlo, monospace'
  context.fillText(`@${formatOdds(heroOdds)}`, width - 340, 92)
  context.fillStyle = '#3de3a5'
  context.font = '700 20px ui-monospace, SFMono-Regular, Menlo, monospace'
  context.fillText(`${formatEV(ticket.evAverage)} EV`, width - 338, 124)

  let y = 190
  ticket.legs.forEach((leg, index) => {
    context.strokeStyle = '#27303b'
    context.beginPath()
    context.moveTo(56, y - 28)
    context.lineTo(width - 56, y - 28)
    context.stroke()
    context.fillStyle = '#f2f5f8'
    context.font = '700 22px ui-monospace, SFMono-Regular, Menlo, monospace'
    context.fillText(`${index + 1}. ${formatMarketName(leg.market)}`, 56, y)
    context.fillStyle = '#9aa6b2'
    context.font = '500 18px ui-monospace, SFMono-Regular, Menlo, monospace'
    y = drawWrappedText(context, leg.match, 56, y + 30, width - 300, 24)
    context.fillStyle = '#3de3a5'
    context.font = '700 22px ui-monospace, SFMono-Regular, Menlo, monospace'
    context.fillText(`@${formatOdds(leg.odds)} · ${formatEV(leg.ev)} EV`, width - 330, y - 28)
    y += 42
  })

  context.fillStyle = '#657181'
  context.font = '500 16px ui-monospace, SFMono-Regular, Menlo, monospace'
  context.fillText('Probabilidades estimadas por modelo Poisson + IA.', 56, height - 34)

  return new Promise((resolve, reject) => {
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error('No se pudo generar la imagen'))), 'image/png')
  })
}

export async function shareOrDownloadTicket(ticket: Ticket): Promise<'shared' | 'downloaded' | 'cancelled'> {
  const blob = await renderTicketImage(ticket)
  const filename = `betmind-${ticket.mode.toLowerCase()}-${Date.now()}.png`
  const file = new File([blob], filename, { type: 'image/png' })
  const summary = ticketSummary(ticket)

  if (navigator.share) {
    try {
      const shareFiles = navigator.canShare?.({ files: [file] })
      await navigator.share({
        title: 'BetMind AI · Boleto cuantitativo',
        text: summary,
        url: window.location.href,
        ...(shareFiles ? { files: [file] } : {}),
      })
      return 'shared'
    } catch (error) {
      if (error instanceof DOMException && error.name === 'AbortError') return 'cancelled'
    }
  }

  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
  return 'downloaded'
}
