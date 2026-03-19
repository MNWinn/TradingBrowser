'use client'

import { useEffect, useState } from 'react'
import { getMirofishPredict, getMirofishStatus } from '@/lib/api'

export default function SettingsPage() {
  const [status, setStatus] = useState<any>(null)
  const [ticker, setTicker] = useState('AAPL')
  const [predict, setPredict] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    setError(null)
    try {
      const s = await getMirofishStatus()
      setStatus(s)
    } catch (e: any) {
      setError(e.message || 'Failed to load settings')
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const runPredict = async () => {
    setError(null)
    try {
      const p = await getMirofishPredict({ ticker })
      setPredict(p)
    } catch (e: any) {
      setError(e.message || 'Predict failed')
    }
  }

  return (
    <main className="space-y-3">
      <section className="card p-4">
        <h1 className="font-semibold mb-2">Settings / Integrations / Risk Controls</h1>
        <p className="text-sm text-slate-300">MiroFish provider status and quick integration check.</p>
      </section>

      <section className="card p-4 text-sm space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">MiroFish Integration</h2>
          <button onClick={refresh} className="btn btn-muted">Refresh</button>
        </div>

        {status ? (
          <div className="space-y-1 text-slate-300">
            <div>Configured: {String(status.configured)}</div>
            <div>Mode: {status.mode}</div>
            <div>Base URL: {status.base_url || '--'}</div>
            <div className="text-xs text-slate-400">{status.note}</div>
          </div>
        ) : (
          <div className="text-slate-400">Loading status…</div>
        )}

        <div className="flex gap-2 pt-2">
          <input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} className="px-2 py-1" />
          <button onClick={runPredict} className="btn btn-primary">Test Predict</button>
        </div>

        {predict && <pre className="bg-slate-950/70 border border-slate-800 rounded p-2 text-xs overflow-auto">{JSON.stringify(predict, null, 2)}</pre>}
        {error && <div className="text-rose-300 text-xs">{error}</div>}
      </section>
    </main>
  )
}
