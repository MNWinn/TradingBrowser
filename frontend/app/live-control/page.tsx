'use client'

import { useEffect, useState } from 'react'
import { getExecutionMode, getLiveReadiness, getReadinessHistory, getReadinessSummary, runAllReadinessDiagnostics, updateExecutionMode } from '@/lib/api'

export default function LiveControlPage() {
  const [mode, setMode] = useState<'research' | 'paper' | 'live'>('research')
  const [liveEnabled, setLiveEnabled] = useState(false)
  const [forceEnable, setForceEnable] = useState(false)
  const [readiness, setReadiness] = useState<any>(null)
  const [msg, setMsg] = useState('')
  const [isRunningDiagnostics, setIsRunningDiagnostics] = useState(false)
  const [lastCheckedAt, setLastCheckedAt] = useState<string | null>(null)
  const [readinessHistory, setReadinessHistory] = useState<any[]>([])
  const [readinessSummary, setReadinessSummary] = useState<any>(null)
  const [snapshotError, setSnapshotError] = useState<string | null>(null)

  const refresh = async () => {
    try {
      setSnapshotError(null)
      const [res, ready, trend, summary] = await Promise.all([
        getExecutionMode(),
        getLiveReadiness(),
        getReadinessHistory(20),
        getReadinessSummary(200),
      ])
      setMode(res.mode)
      setLiveEnabled(Boolean(res.live_trading_enabled))
      setReadiness(ready)
      setReadinessHistory(trend?.snapshots || [])
      setReadinessSummary(summary)
      setLastCheckedAt(trend?.latest?.created_at || new Date().toISOString())
    } catch (e: any) {
      setSnapshotError(e?.message || 'Failed to load latest readiness snapshot')
      setReadiness(null)
    }
  }

  const runAllDiagnostics = async () => {
    setIsRunningDiagnostics(true)
    setMsg('')
    setSnapshotError(null)
    try {
      const snapshot = await runAllReadinessDiagnostics()
      setReadiness(snapshot)
      const [trend, summary] = await Promise.all([getReadinessHistory(20), getReadinessSummary(200)])
      setReadinessHistory(trend?.snapshots || [])
      setReadinessSummary(summary)
      setLastCheckedAt(trend?.latest?.created_at || new Date().toISOString())
      setMsg(snapshot?.ready ? 'All readiness diagnostics passed' : 'Readiness diagnostics reported blockers')
    } catch (e: any) {
      const errorMsg = e?.message || 'Failed to run readiness diagnostics'
      setSnapshotError(errorMsg)
      setMsg(errorMsg)
    } finally {
      setIsRunningDiagnostics(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const save = async () => {
    try {
      const payload: any = { mode, live_trading_enabled: liveEnabled, changed_by: 'demo-user' }
      if (mode === 'live' && liveEnabled) {
        payload.confirmation = 'ENABLE_LIVE_TRADING'
        payload.force_enable_live = forceEnable
      }
      await updateExecutionMode(payload)
      setMsg('Execution mode updated successfully')
      await refresh()
    } catch (e: any) {
      setMsg(e.message || 'Failed to update mode')
    }
  }

  return (
    <main className="space-y-3 max-w-2xl">
      <section className="card p-4">
        <h1 className="font-semibold mb-3">Live Trading Control Center</h1>
        <div className="space-y-3 text-sm">
          <label className="block">
            <span className="text-slate-300">Mode</span>
            <select value={mode} onChange={(e) => setMode(e.target.value as any)} className="mt-1 w-full px-2 py-1">
              <option value="research">Research</option>
              <option value="paper">Paper</option>
              <option value="live">Live</option>
            </select>
          </label>

          <label className="flex items-center gap-2">
            <input type="checkbox" checked={liveEnabled} onChange={(e) => setLiveEnabled(e.target.checked)} />
            <span>Live trading enabled (explicit gate)</span>
          </label>

          <label className="flex items-center gap-2">
            <input type="checkbox" checked={forceEnable} onChange={(e) => setForceEnable(e.target.checked)} />
            <span>Force enable live (override readiness gates)</span>
          </label>

          <button onClick={save} className="btn btn-primary">Save Mode Policy</button>
          <button onClick={() => void runAllDiagnostics()} className="btn btn-muted ml-2" disabled={isRunningDiagnostics}>
            {isRunningDiagnostics ? 'Running Diagnostics…' : 'Run All Readiness Diagnostics'}
          </button>

          {msg && <p className="text-xs text-slate-300">{msg}</p>}
        </div>
      </section>

      <section className="card p-4">
        <h2 className="font-semibold mb-2">Go Live Gate</h2>
        {!readiness && !snapshotError ? (
          <div className="text-sm text-slate-400">Loading readiness checks…</div>
        ) : snapshotError ? (
          <div className="space-y-2 text-sm">
            <div className="font-medium">Latest Snapshot</div>
            <div className="text-red-700">Failed to load readiness snapshot</div>
            <div className="text-slate-400 text-xs">{snapshotError}</div>
            <div className="text-xs">Last Attempt: {lastCheckedAt ? new Date(lastCheckedAt).toLocaleString() : '--'}</div>
          </div>
        ) : (
          <div className="space-y-3 text-sm">
            <div>
              Readiness Status:{' '}
              <span className="status-emphasis font-semibold">
                {readiness.ready ? 'PASS' : 'FAIL'}
              </span>
            </div>
            <div>MiroFish Verdict: {readiness?.mirofish?.verdict || '--'} ({readiness?.mirofish?.provider_mode || '--'})</div>
            <div>MiroFish Readiness Score: {readiness?.mirofish?.readiness_score ?? '--'}%</div>
            <div>Compliance Overdue Open: {readiness?.compliance_overdue_open ?? '--'}</div>

            <div className="border border-slate-700 rounded p-3 space-y-2">
              <div className="font-medium">Latest Snapshot</div>
              <div>Timestamp: {lastCheckedAt ? new Date(lastCheckedAt).toLocaleString() : '--'}</div>
              <div>
                Snapshot Status:{' '}
                <span className="status-emphasis font-semibold">
                  {typeof readiness?.ready === 'boolean' ? (readiness.ready ? 'PASS' : 'FAIL') : 'UNKNOWN'}
                </span>
              </div>
              <div>Diagnostics: MiroFish {readiness?.mirofish?.verdict || '--'}, Score {readiness?.mirofish?.readiness_score ?? '--'}%</div>
              <div>
                Trend Hint:{' '}
                {typeof readiness?.mirofish?.readiness_score === 'number'
                  ? readiness.mirofish.readiness_score >= 80
                    ? 'Stable/Healthy'
                    : readiness.mirofish.readiness_score >= 60
                      ? 'Watchlist'
                      : 'Deteriorating'
                  : 'Insufficient data'}
              </div>
              <div>
                Snapshot Count: {readinessHistory.length}
                {readinessHistory.length > 0 && (
                  <span>
                    {' '}· Pass Rate (20): {Math.round((readinessHistory.filter((s: any) => s.ready).length / readinessHistory.length) * 100)}%
                  </span>
                )}
              </div>
              {readinessSummary && (
                <div>
                  Trend Window (200): {readinessSummary.pass_count ?? 0} pass / {readinessSummary.total ?? 0} total
                  {' '}({Math.round(((readinessSummary.pass_rate || 0) as number) * 100)}%)
                </div>
              )}
              {!!(readiness?.reasons || []).length && (
                <div>
                  <div className="text-xs font-medium">Key blockers</div>
                  <ul className="text-xs list-disc pl-4">
                    {(readiness.reasons || []).slice(0, 3).map((r: string, idx: number) => <li key={idx}>{r}</li>)}
                  </ul>
                </div>
              )}
              {!!(readiness?.mirofish?.recommendations || []).length && (
                <div>
                  <div className="text-xs font-medium">Top recommendations</div>
                  <ul className="text-xs list-disc pl-4">
                    {(readiness.mirofish.recommendations || []).slice(0, 3).map((r: string, idx: number) => <li key={idx}>{r}</li>)}
                  </ul>
                </div>
              )}
              {!readiness?.reasons?.length && !readiness?.mirofish?.recommendations?.length && (
                <div className="text-xs text-slate-400">No detailed diagnostic notes in latest snapshot.</div>
              )}
            </div>
          </div>
        )}
      </section>
    </main>
  )
}
