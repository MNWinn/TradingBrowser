'use client'

import { useEffect, useMemo, useState } from 'react'
import { getExecutionAnalytics, getExecutionMode, listJournal, submitOrder, submitOrderFill, validateExecution } from '@/lib/api'

function genKey(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

function Gauge({ label, value }: { label: string; value: number }) {
  const pct = Math.max(0, Math.min(1, value || 0))
  return (
    <div>
      <div className="text-xs text-slate-300 mb-1">{label}: {(pct * 100).toFixed(1)}%</div>
      <div className="h-2 rounded bg-slate-800 overflow-hidden">
        <div className={`h-full ${pct > 0.8 ? 'bg-rose-500' : pct > 0.6 ? 'bg-amber-500' : 'bg-emerald-500'}`} style={{ width: `${pct * 100}%` }} />
      </div>
    </div>
  )
}

export default function PaperConsolePage() {
  const [mode, setMode] = useState<any>(null)
  const [journal, setJournal] = useState<any[]>([])
  const [analytics, setAnalytics] = useState<any>(null)
  const [validateRes, setValidateRes] = useState<any>(null)
  const [submitRes, setSubmitRes] = useState<any>(null)
  const [fillRes, setFillRes] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  const [symbol, setSymbol] = useState('AAPL')
  const [side, setSide] = useState<'buy' | 'sell'>('buy')
  const [qty, setQty] = useState(5)

  const [fillOrderId, setFillOrderId] = useState('')
  const [fillPrice, setFillPrice] = useState(100)
  const [fillQty, setFillQty] = useState(5)
  const [fillPnl, setFillPnl] = useState(0)

  const latestOrderId = useMemo(
    () => submitRes?.id || submitRes?.broker_order_id || submitRes?.order_id || '',
    [submitRes],
  )

  const fmtTs = (v: string | null | undefined) => {
    if (!v) return '--'
    const d = new Date(v)
    return Number.isNaN(d.getTime()) ? String(v) : d.toLocaleString()
  }

  const refresh = async () => {
    const [m, j, a] = await Promise.all([getExecutionMode(), listJournal(20), getExecutionAnalytics(100)])
    setMode(m)
    setJournal(j.items || [])
    setAnalytics(a)
  }

  useEffect(() => {
    void refresh()
  }, [])

  useEffect(() => {
    if (latestOrderId && !fillOrderId) setFillOrderId(latestOrderId)
  }, [latestOrderId, fillOrderId])

  const orderPayload = {
    symbol,
    side,
    qty,
    type: 'market' as const,
    rationale: { source: 'paper-console-ui', note: 'manual test' },
    recommendation: { action: side === 'buy' ? 'LONG' : 'EXIT' },
  }

  const runValidate = async () => {
    setError(null)
    try {
      const data = await validateExecution(orderPayload)
      setValidateRes(data)
    } catch (e: any) {
      setError(e.message || 'Validate failed')
    }
  }

  const runSubmit = async () => {
    setError(null)
    try {
      const data = await submitOrder({ ...orderPayload, idempotency_key: genKey('order') })
      setSubmitRes(data)
      await refresh()
    } catch (e: any) {
      setError(e.message || 'Submit failed')
    }
  }

  const runFill = async () => {
    setError(null)
    try {
      const data = await submitOrderFill({
        broker_order_id: fillOrderId,
        state: 'filled',
        fill_price: fillPrice,
        fill_qty: fillQty,
        pnl: fillPnl,
        notes: 'manual fill from paper console',
        idempotency_key: genKey('fill'),
      })
      setFillRes(data)
      await refresh()
    } catch (e: any) {
      setError(e.message || 'Fill update failed')
    }
  }

  return (
    <main className="space-y-3">
      <section className="card p-4 flex justify-between items-center">
        <div>
          <h1 className="text-xl font-semibold mb-2">Paper Trading Console</h1>
          <div className="text-sm text-slate-300">Mode: {mode ? `${mode.mode} (live_enabled=${String(mode.live_trading_enabled)})` : 'Loading…'}</div>
        </div>
        <button onClick={refresh} className="btn btn-muted">Refresh Analytics</button>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-4 gap-3">
        <div className="card p-3">
          <div className="text-xs text-slate-400">Realized PnL</div>
          <div className={`text-2xl font-semibold ${(analytics?.summary?.realized_pnl || 0) >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>${Number(analytics?.summary?.realized_pnl || 0).toFixed(2)}</div>
        </div>
        <div className="card p-3">
          <div className="text-xs text-slate-400">Open Exposure</div>
          <div className="text-2xl font-semibold text-sky-300">${Number(analytics?.summary?.open_exposure || 0).toFixed(2)}</div>
        </div>
        <div className="card p-3">
          <div className="text-xs text-slate-400">Fill Rate</div>
          <div className="text-2xl font-semibold">{Math.round((analytics?.summary?.fill_rate || 0) * 100)}%</div>
        </div>
        <div className="card p-3">
          <div className="text-xs text-slate-400">Win Rate</div>
          <div className="text-2xl font-semibold">{Math.round((analytics?.summary?.win_rate || 0) * 100)}%</div>
        </div>
      </section>

      <section className="card p-4 space-y-3">
        <h2 className="font-semibold">Risk Utilization Gauges</h2>
        <Gauge label="Capital / Trade" value={analytics?.risk_utilization?.capital_per_trade_pct || 0} />
        <Gauge label="Daily Loss Budget" value={analytics?.risk_utilization?.daily_loss_pct || 0} />
        <Gauge label="Concurrent Positions" value={analytics?.risk_utilization?.concurrent_positions_pct || 0} />
      </section>

      <section className="card p-4 space-y-3">
        <h2 className="font-semibold">Order Builder</h2>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-2 text-sm">
          <input value={symbol} onChange={(e) => setSymbol(e.target.value.toUpperCase())} className="bg-slate-900 border border-slate-700 rounded px-2 py-1" />
          <select value={side} onChange={(e) => setSide(e.target.value as 'buy' | 'sell')} className="bg-slate-900 border border-slate-700 rounded px-2 py-1">
            <option value="buy">Buy</option>
            <option value="sell">Sell</option>
          </select>
          <input type="number" value={qty} onChange={(e) => setQty(Number(e.target.value))} className="bg-slate-900 border border-slate-700 rounded px-2 py-1" />
          <div className="flex gap-2">
            <button onClick={runValidate} className="btn btn-muted">Validate</button>
            <button onClick={runSubmit} className="btn btn-primary">Submit</button>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs">
          <pre className="bg-slate-950/70 border border-slate-800 rounded p-2 overflow-auto">Validate: {JSON.stringify(validateRes, null, 2)}</pre>
          <pre className="bg-slate-950/70 border border-slate-800 rounded p-2 overflow-auto">Submit: {JSON.stringify(submitRes, null, 2)}</pre>
        </div>
      </section>

      <section className="card p-4 space-y-3">
        <h2 className="font-semibold">Fill Update</h2>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-2 text-sm">
          <input value={fillOrderId} onChange={(e) => setFillOrderId(e.target.value)} placeholder="broker_order_id" className="bg-slate-900 border border-slate-700 rounded px-2 py-1" />
          <input type="number" value={fillPrice} onChange={(e) => setFillPrice(Number(e.target.value))} className="bg-slate-900 border border-slate-700 rounded px-2 py-1" />
          <input type="number" value={fillQty} onChange={(e) => setFillQty(Number(e.target.value))} className="bg-slate-900 border border-slate-700 rounded px-2 py-1" />
          <input type="number" value={fillPnl} onChange={(e) => setFillPnl(Number(e.target.value))} className="bg-slate-900 border border-slate-700 rounded px-2 py-1" />
          <button onClick={runFill} className="btn btn-primary">Send Fill</button>
        </div>
        <pre className="bg-slate-950/70 border border-slate-800 rounded p-2 text-xs overflow-auto">Fill: {JSON.stringify(fillRes, null, 2)}</pre>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div className="card p-4">
          <h2 className="font-semibold mb-2">Mode Change Timeline</h2>
          <div className="space-y-2 text-sm max-h-72 overflow-auto">
            {(analytics?.mode_timeline || []).map((m: any, idx: number) => (
              <div key={`${m.changed_at}-${idx}`} className="rounded border border-slate-700 p-2">
                <div className="font-medium">{m.mode} · live={String(m.live_enabled)}</div>
                <div className="text-xs text-slate-400">{m.changed_by || 'system'} · {fmtTs(m.changed_at)}</div>
              </div>
            ))}
          </div>
        </div>
        <div className="card p-4">
          <h2 className="font-semibold mb-2">Recent Execution Events</h2>
          <div className="space-y-2 text-sm max-h-72 overflow-auto">
            {(analytics?.recent_events || []).map((e: any, idx: number) => (
              <div key={`${e.created_at}-${idx}`} className="rounded border border-slate-700 p-2">
                <div className="font-medium">{e.event_type}</div>
                <div className="text-xs text-slate-400">{e.actor || 'system'} · {fmtTs(e.created_at)}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="card p-4">
        <h2 className="font-semibold mb-2">Recent Journal Entries</h2>
        <div className="space-y-2 text-sm">
          {journal.length === 0 && <p className="text-slate-400">No journal entries yet.</p>}
          {journal.map((i) => (
            <div key={i.id} className="rounded border border-slate-700 p-2">
              <div className="font-medium">#{i.id} {i.ticker} · {i.mode}</div>
              <div className="text-xs text-slate-400">{fmtTs(i.created_at)}</div>
              <div className="text-xs mt-1">state: {i?.tags?.state || 'submitted'} | broker: {i?.execution?.broker_order_id || '--'}</div>
            </div>
          ))}
        </div>
      </section>

      {error && <div className="card p-3 text-sm text-rose-300">{error}</div>}
    </main>
  )
}
