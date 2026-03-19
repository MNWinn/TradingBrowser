'use client'

import { useEffect, useMemo, useState } from 'react'
import { listJournal, updateJournalOutcome } from '@/lib/api'

export default function JournalPage() {
  const [symbolFilter, setSymbolFilter] = useState('')
  const [items, setItems] = useState<any[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await listJournal(100)
      setItems(data.items || [])
    } catch (e: any) {
      setError(e.message || 'Failed to load journal')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (typeof window !== 'undefined') {
      const v = new URLSearchParams(window.location.search).get('symbol') || ''
      setSymbolFilter(v.toUpperCase())
    }
    void refresh()
  }, [])

  const visibleItems = useMemo(() => {
    if (!symbolFilter) return items
    return items.filter((i) => String(i?.ticker || '').toUpperCase() === symbolFilter)
  }, [items, symbolFilter])

  const markClosed = async (entry: any) => {
    try {
      await updateJournalOutcome(entry.id, {
        state: 'closed',
        fill_price: entry?.outcome?.fill_price ?? entry?.execution?.result?.filled_avg_price ?? null,
        fill_qty: entry?.outcome?.fill_qty ?? entry?.execution?.request?.qty ?? null,
        pnl: entry?.outcome?.pnl ?? 0,
        notes: 'Closed from journal UI',
      })
      await refresh()
    } catch (e: any) {
      setError(e.message || 'Failed to update outcome')
    }
  }

  return (
    <main className="card p-4">
      <div className="flex justify-between items-center mb-3">
        <h1 className="font-semibold">Trade Journal</h1>
        <button onClick={refresh} className="px-3 py-1 rounded bg-slate-700 text-sm">Refresh</button>
      </div>

      {symbolFilter && <div className="text-xs text-slate-400 mb-2">Filtered by symbol: {symbolFilter}</div>}

      {loading && <p className="text-sm text-slate-400">Loading…</p>}
      {error && <p className="text-sm text-rose-300 mb-2">{error}</p>}

      <div className="space-y-2 text-sm">
        {visibleItems.length === 0 && <p className="text-slate-400">No journal entries yet.</p>}
        {visibleItems.map((i) => (
          <div key={i.id} className="rounded border border-slate-700 p-3">
            <div className="flex justify-between items-center">
              <div className="font-medium">#{i.id} {i.ticker} · {i.mode}</div>
              <button onClick={() => markClosed(i)} className="px-2 py-1 rounded bg-sky-700 text-xs">Mark Closed</button>
            </div>
            <div className="text-xs text-slate-400">{i.created_at}</div>
            <div className="text-xs mt-1">state: {i?.tags?.state || 'submitted'}</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2 mt-2">
              <pre className="bg-slate-950/70 border border-slate-800 rounded p-2 overflow-auto">Execution: {JSON.stringify(i.execution, null, 2)}</pre>
              <pre className="bg-slate-950/70 border border-slate-800 rounded p-2 overflow-auto">Outcome: {JSON.stringify(i.outcome, null, 2)}</pre>
            </div>
          </div>
        ))}
      </div>
    </main>
  )
}
