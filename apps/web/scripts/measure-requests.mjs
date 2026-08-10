/**
 * Measurement script v5: bypasses onboarding and simulates an active PRO session
 * before navigating. Uses CDP-level request interception + actual link clicks.
 *
 * Run with: node scripts/measure-requests.mjs
 */

import puppeteer from 'puppeteer'
import http from 'http'

const BASE = 'http://localhost:3000'
const SETTLE_MS = 5000

async function sleep(ms) { return new Promise((r) => setTimeout(r, ms)) }

async function createTestUser() {
  return new Promise((resolve, reject) => {
    const data = JSON.stringify({
      email: `test_pro_${Date.now()}@example.com`,
      password: 'password',
      age_confirmed: true
    })
    const req = http.request('http://127.0.0.1:8000/api/v1/auth/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' }
    }, (res) => {
      let body = ''
      res.on('data', d => body += d)
      res.on('end', () => {
        if (res.statusCode >= 400) reject(new Error('Auth failed: ' + body))
        else resolve(JSON.parse(body))
      })
    })
    req.on('error', reject)
    req.write(data)
    req.end()
  })
}

async function main() {
  console.log('Creando usuario de prueba en el backend...')
  let tokenData
  try {
    tokenData = await createTestUser()
    console.log('✅ Usuario creado.')
  } catch(e) {
    console.error('Error creando usuario. Verifica que el backend esté corriendo.', e.message)
    process.exit(1)
  }

  const browser = await puppeteer.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox'],
  })
  const page = await browser.newPage()

  await page.evaluateOnNewDocument((tokenObj) => {
    window.localStorage.setItem('betmind_onboarding_seen', 'true')
    window.localStorage.setItem('betmind_access_token', JSON.stringify({ access_token: tokenObj.access_token }))
    window.localStorage.setItem('betmind_dev_is_pro', 'true')
  }, tokenData)

  const all = []
  const snapshots = { home: 0, partidos: 0, generador: 0 }

  page.on('request', (req) => {
    const url = req.url()
    if (url.includes(':8000') || (url.includes('localhost') && url.includes('/api/v1'))) {
      all.push({
        url,
        path: (() => {
          const m = url.match(/\/api\/v1\/[^?#]*/)
          return m ? m[0] : url
        })(),
        method: req.method(),
        ts: Date.now(),
      })
    }
  })

  const ENDPOINTS = [
    '/api/v1/users/me',
    '/api/v1/matches/',
    '/api/v1/leagues/',
    '/api/v1/bankroll',
    '/api/v1/tickets/history',
  ]

  console.log('\n=== MEDICIÓN REAL (CDP + SPA routing) — BetMind AI SWR ===\n')

  // ── 1. Load Home ──────────────────────────────────────────────────────────
  console.log('[1/3] Cargando Home (/)…')
  await page.goto(BASE, { waitUntil: 'networkidle2', timeout: 30000 })
  await sleep(SETTLE_MS)
  snapshots.home = all.length
  const homeOnly = all.slice(0, snapshots.home)
  console.log(`      ${homeOnly.length} request(s) capturadas`)

  // ── 2. Click nav link → /partidos ─────────────────────────────────────────
  console.log('\n[2/3] Click en nav → /partidos (SPA)…')
  const beforePartidos = all.length
  
  await page.evaluate(() => {
    const link = document.querySelector('a[href="/partidos"]');
    if (link) link.click();
    else console.error('Link to /partidos not found');
  })
  
  await page.waitForFunction(() => location.pathname === '/partidos', { timeout: 10000 }).catch(() => {})
  await sleep(SETTLE_MS)

  const partidosOnly = all.slice(beforePartidos)
  snapshots.partidos = all.length
  console.log(`      ${partidosOnly.length} nuevas request(s)`)

  // ── 3. Click nav link → /generador ────────────────────────────────────────
  console.log('\n[3/3] Click en botón/nav → /generador (SPA)…')
  const beforeGenerador = all.length

  await page.evaluate(() => {
    // Try link or a button that navigates there
    const link = document.querySelector('a[href="/generador"]') || document.querySelector('button[aria-label*="generador"]');
    if (link) link.click();
    else {
      // In app router, we can simulate a click on an anchor to force soft-nav
      const a = document.createElement('a');
      a.href = '/generador';
      document.body.appendChild(a);
      a.click();
      a.remove();
    }
  })
  
  await page.waitForFunction(() => location.pathname === '/generador', { timeout: 10000 }).catch(() => {})
  await sleep(SETTLE_MS)

  const generadorOnly = all.slice(beforeGenerador)
  console.log(`      ${generadorOnly.length} nuevas request(s)`)

  // ── RESUMEN ────────────────────────────────────────────────────────────────
  console.log('\n' + '='.repeat(70))
  console.log('TABLA DE REQUESTS POR ENDPOINT Y PÁGINA (excluyendo preflight OPTIONS)')
  console.log('='.repeat(70))
  console.log('Endpoint                           Home  +Partidos  +Generador  TOTAL')
  console.log('-'.repeat(70))

  let grandTotal = 0
  
  // Filter out OPTIONS requests (CORS preflight) for a cleaner count
  const filterMethods = (reqs) => reqs.filter(r => r.method !== 'OPTIONS')
  
  for (const ep of ENDPOINTS) {
    const h = filterMethods(homeOnly).filter((r) => r.path.startsWith(ep)).length
    const p = filterMethods(partidosOnly).filter((r) => r.path.startsWith(ep)).length
    const g = filterMethods(generadorOnly).filter((r) => r.path.startsWith(ep)).length
    const t = h + p + g
    grandTotal += t
    
    console.log(
      ep.padEnd(35) +
      String(h).padStart(4) +
      String(p).padStart(11) +
      String(g).padStart(11) +
      String(t).padStart(7)
    )
  }

  console.log('-'.repeat(70))
  console.log('TOTAL monitorizados'.padEnd(35) + ''.padStart(4) + ''.padStart(11) + ''.padStart(11) + String(grandTotal).padStart(7))

  // ── DIAGNÓSTICO ────────────────────────────────────────────────────────────
  console.log('\n=== DIAGNÓSTICO SWR ===')
  const allFiltered = filterMethods(all)
  const matchesTotal = allFiltered.filter((r) => r.path.startsWith('/api/v1/matches/')).length
  const leaguesTotal = allFiltered.filter((r) => r.path.startsWith('/api/v1/leagues/')).length
  const usersTotal = allFiltered.filter((r) => r.path.startsWith('/api/v1/users/me')).length
  const bankrollTotal = allFiltered.filter((r) => r.path.startsWith('/api/v1/bankroll')).length
  const historyTotal = allFiltered.filter((r) => r.path.startsWith('/api/v1/tickets/history')).length

  console.log(`/matches/   : ${matchesTotal} request(s) — esperado: 1 si SWR comparte caché (deduplicado a lo largo de las páginas)`)
  console.log(`/leagues/   : ${leaguesTotal} request(s) — esperado: 1`)
  console.log(`/users/me   : ${usersTotal} request(s) — esperado: 1`)
  console.log(`/bankroll   : ${bankrollTotal} request(s) — esperado: 1`)
  console.log(`/tickets... : ${historyTotal} request(s) — esperado: 1`)

  if (matchesTotal <= 1 && leaguesTotal <= 1 && usersTotal <= 1 && bankrollTotal <= 1) {
    console.log('\n✅ SWR deduplicación confirmada: NO hubo re-fetches en navegaciones.')
  } else {
    console.log('\n⚠️ Se detectaron re-fetches: SWR no está compartiendo el caché o la navegación no fue SPA.')
  }

  await browser.close()
}

main().catch((err) => {
  console.error('Error:', err.message)
  process.exit(1)
})
