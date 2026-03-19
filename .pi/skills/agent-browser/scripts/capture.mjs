import fs from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright'

const label = process.argv[2] || 'current'
const outDir = path.resolve('.pi/skills/agent-browser/screenshots', label)
fs.mkdirSync(outDir, { recursive: true })

const pages = [
  ['/dashboard', 'dashboard.png'],
  ['/workspace', 'workspace.png'],
  ['/paper-console', 'paper-console.png'],
  ['/swarm', 'swarm.png'],
  ['/settings', 'settings.png'],
]

const baseUrl = process.env.AGENT_BROWSER_BASE_URL || 'http://localhost:3000'

const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1600, height: 1000 } })

for (const [route, file] of pages) {
  const page = await context.newPage()
  await page.goto(`${baseUrl}${route}`, { waitUntil: 'networkidle' })
  await page.waitForTimeout(1200)
  await page.screenshot({ path: path.join(outDir, file), fullPage: true })
  await page.close()
  console.log(`captured ${route} -> ${file}`)
}

await browser.close()
console.log(`done: ${outDir}`)
