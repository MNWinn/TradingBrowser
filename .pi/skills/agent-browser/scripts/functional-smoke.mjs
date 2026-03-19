import { chromium } from 'playwright'

const baseUrl = process.env.AGENT_BROWSER_BASE_URL || 'http://localhost:3000'

const pages = [
  { route: '/dashboard', mustSee: ['Dashboard', 'Refresh'] },
  { route: '/workspace', mustSee: ['Workspace', 'Chart Workspace'] },
  { route: '/paper-console', mustSee: ['Paper Console', 'Order Builder'] },
  { route: '/swarm', mustSee: ['Swarm', 'Run Swarm'] },
  { route: '/settings', mustSee: ['Settings', 'MiroFish Integration'] },
  { route: '/compliance', mustSee: ['Compliance', 'Violation Queue'] },
]

const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } })

const failures = []

for (const p of pages) {
  const page = await context.newPage()
  const logs = []
  page.on('console', (msg) => {
    const t = msg.type()
    if (t === 'error') logs.push(`[console:${t}] ${msg.text()}`)
  })
  page.on('pageerror', (err) => logs.push(`[pageerror] ${err.message}`))

  await page.goto(`${baseUrl}${p.route}`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(800)
  const text = await page.textContent('body')

  for (const needle of p.mustSee) {
    if (!text?.includes(needle)) {
      failures.push(`${p.route}: missing text '${needle}'`)
    }
  }

  if (logs.length) {
    failures.push(`${p.route}: js errors\n${logs.join('\n')}`)
  }

  // Lightweight interaction checks
  if (p.route === '/dashboard') {
    const controls = page.getByText('View controls')
    if ((await controls.count()) > 0) {
      await controls.first().click()
      await page.waitForTimeout(250)
    }
  }

  if (p.route === '/compliance') {
    const refreshBtn = page.getByText('Refresh', { exact: true })
    if ((await refreshBtn.count()) > 0) {
      await refreshBtn.first().click()
      await page.waitForTimeout(300)
    }
  }

  await page.close()
  console.log(`checked ${p.route}`)
}

await browser.close()

if (failures.length) {
  console.error('Functional smoke failures:\n' + failures.join('\n---\n'))
  process.exit(1)
}

console.log('Functional smoke PASS')
