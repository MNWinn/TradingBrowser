'use client'

import { useState } from 'react'
import { runStrategyBacktest } from '@/lib/api'

export default function StrategyLabPage() {
  const [name, setName] = useState('Momentum + MiroFish Bias')
  const [ticker, setTicker] = useState('AAPL')
  const [timeframe, setTimeframe] = useState('5m')
  const [lookback, setLookback] = useState(120)
  const [riskPct, setRiskPct] = useState(1)
  const [result, setResult] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const run = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await runStrategyBacktest({
        name,
        ticker,
        timeframe,
        lookback,
        risk_pct: riskPct,
      })
      setResult(data)
    } catch (e: any) {
      setError(e.message || 'Backtest failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="space-y-3">
      <section className="card p-4">
        <h1 className="text-xl font-semibold mb-1">Strategy Lab</h1>
        <p className="text-sm text-slate-300">Define strategy parameters, run quick backtests, compare risk/return profile.</p>
      </section>

      <section className="card p-4 grid grid-cols-1 md:grid-cols-6 gap-2 text-sm">
        <input value={name} onChange={(e) => setName(e.target.value)} className="bg-slate-900 border border-slate-700 rounded px-2 py-1 md:col-span-2" placeholder="Strategy name" />
        <input value={ticker} onChange={(e) => setTicker(e.target.value.toUpperCase())} className="bg-slate-900 border border-slate-700 rounded px-2 py-1" placeholder="Ticker" />
        <select value={timeframe} onChange={(e) => setTimeframe(e.target.value)} className="bg-slate-900 border border-slate-700 rounded px-2 py-1">
          <option>1m</option>
          <option>5m</option>
          <option>15m</option>
          <option>1h</option>
        </select>
        <input type="number" value={lookback} onChange={(e) => setLookback(Number(e.target.value))} className="bg-slate-900 border border-slate-700 rounded px-2 py-1" placeholder="Lookback bars" />
        <input type="number" value={riskPct} onChange={(e) => setRiskPct(Number(e.target.value))} className="bg-slate-900 border border-slate-700 rounded px-2 py-1" placeholder="Risk %" />
        <button onClick={run} disabled={loading} className="px-3 py-1 rounded bg-emerald-700 hover:bg-emerald-600 disabled:opacity-60">
          {loading ? 'Running…' : 'Run Backtest'}
        </button>
      </section>

      {error && <section className="card p-3 text-sm text-rose-300">{error}</section>}

      {result && (
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-3">
          <div className="card p-4 lg:col-span-2">
            <h2 className="font-semibold mb-2">Equity Curve ({result.strategy})</h2>
            <div className="h-52 w-full rounded border border-slate-800 bg-slate-950/60 p-3 flex items-end gap-2">
              {(result.equity_curve || []).map((v: number, i: number, arr: number[]) => {
                const min = Math.min(...arr)
                const max = Math.max(...arr)
                const pct = max === min ? 50 : ((v - min) / (max - min)) * 100
                return <div key={i} title={`${v}`} className="flex-1 bg-sky-600/70 rounded-t" style={{ height: `${Math.max(8, pct)}%` }} />
              })}
            </div>
          </div>
          <div className="card p-4">
            <h2 className="font-semibold mb-2">Metrics</h2>
            <ul className="text-sm text-slate-300 space-y-1">
              <li>Win Rate: {Math.round((result.win_rate || 0) * 100)}%</li>
              <li>Drawdown: {Math.round((result.drawdown || 0) * 100)}%</li>
              <li>Expectancy: {Number(result.expectancy || 0).toFixed(2)}</li>
              <li>Final Equity: {(result.equity_curve || []).slice(-1)[0] ?? '--'}</li>
            </ul>
          </div>
        </section>
      )}
    </main>
  )
}
