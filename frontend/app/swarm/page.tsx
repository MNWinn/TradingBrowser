'use client'

import { useEffect, useMemo, useState } from 'react'
import { getMirofishDiagnostics, getSwarmPerformance, getSwarmResults, runSwarm } from '@/lib/api'

export default function SwarmPage() {
  const [ticker, setTicker] = useState('AAPL')
  const [running, setRunning] = useState(false)
  const [result, setResult] = useState<any>(null)
  const [performance, setPerformance] = useState<any[]>([])
  const [mirofishDiag, setMirofishDiag] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)

  const fmtTs = (v: string | null | undefined) => {
    if (!v) return '--'
    const d = new Date(v)
    return Number.isNaN(d.getTime()) ? String(v) : d.toLocaleString()
  }

  const refresh = async (symbol = ticker) => {
    const [r, p, d] = await Promise.all([
      getSwarmResults(symbol),
      getSwarmPerformance(),
      getMirofishDiagnostics({ ticker: symbol }),
    ])
    setResult(r)
    setPerformance(p.items || [])
    setMirofishDiag(d)
  }

  useEffect(() => {
    void refresh('AAPL')
  }, [])

  const handleRun = async () => {
    setRunning(true)
    setError(null)
    try {
      await runSwarm(ticker)
      await refresh(ticker)
    } catch (e: any) {
      setError(e?.message || 'Failed to run swarm')
    } finally {
      setRunning(false)
    }
  }

  const explainability = useMemo(() => {
    const rows = result?.results || []
    const votingRows = rows.filter((r: any) => !['risk', 'execution', 'learning'].includes(r.agent))
    const votes = { LONG: 0, SHORT: 0, WATCHLIST: 0, NO_TRADE: 0 }
    let weighted = 0
    for (const r of votingRows) {
      const rec = String(r.recommendation || '').toUpperCase() as keyof typeof votes
      if (rec in votes) votes[rec] += 1
      weighted += Number(r.confidence || 0)
    }

    const mirofish = rows.find((r: any) => r.agent === 'mirofish_context')
    const context = mirofish?.output?.context || null
    const providerMode = context?.provider_mode || 'unknown'

    return {
      votes,
      voterCount: votingRows.length,
      avgVoterConfidence: votingRows.length ? (weighted / votingRows.length) : 0,
      mirofish,
      context,
      providerMode,
    }
  }, [result])

  return (
    <main className="space-y-3">
      <section className="card p-4">
        <h2 className="text-2xl font-semibold mb-2">Swarm Agent Console</h2>
        <p className="text-sm text-slate-300">Per-agent outputs, consensus, latency, and reliability weighting.</p>
      </section>

      <section className="card p-3 flex items-center gap-2">
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value.toUpperCase())}
          className="px-2 py-1 text-sm w-32"
          placeholder="Ticker"
        />
        <button className="btn btn-primary" onClick={handleRun} disabled={running}>
          {running ? 'Running…' : 'Run Swarm'}
        </button>
        <button className="btn btn-muted" onClick={() => refresh(ticker)}>
          Refresh
        </button>
        {error && <span className="text-xs text-red-700">{error}</span>}
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="card p-3 lg:col-span-2">
          <h3 className="font-semibold mb-2">Latest Agent Runs ({result?.ticker || ticker})</h3>
          <div className="overflow-auto">
            <table className="w-full text-sm">
              <thead className="text-slate-300">
                <tr className="text-left border-b border-slate-700">
                  <th className="py-1">Agent</th>
                  <th className="py-1">Recommendation</th>
                  <th className="py-1">Confidence</th>
                </tr>
              </thead>
              <tbody>
                {(result?.results || []).map((r: any) => (
                  <tr key={r.agent} className="border-b border-slate-800/70">
                    <td className="py-1">{r.agent}</td>
                    <td className="py-1">{r.recommendation}</td>
                    <td className="py-1">{Math.round((r.confidence || 0) * 100)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!result?.results?.length && <div className="text-sm text-slate-400">No swarm run yet for this ticker.</div>}
          </div>
        </div>

        <div className="card p-3">
          <h3 className="font-semibold mb-2">Consensus</h3>
          <div className="text-sm text-slate-300 space-y-1">
            <div>Recommendation: {result?.consensus?.recommendation || '--'}</div>
            <div>Consensus Score: {Math.round((result?.consensus?.consensus_score || 0) * 100)}%</div>
            <div>Disagreement: {Math.round((result?.consensus?.disagreement_score || 0) * 100)}%</div>
            <div>Task ID: {result?.latest_task || '--'}</div>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div className="card p-3">
          <h3 className="font-semibold mb-2">Decision Explainability</h3>
          <div className="text-sm space-y-1">
            <div>Voters: {explainability.voterCount}</div>
            <div>Avg Voter Confidence: {Math.round(explainability.avgVoterConfidence * 100)}%</div>
            <div>LONG votes: {explainability.votes.LONG}</div>
            <div>WATCHLIST votes: {explainability.votes.WATCHLIST}</div>
            <div>NO_TRADE votes: {explainability.votes.NO_TRADE}</div>
            <div>SHORT votes: {explainability.votes.SHORT}</div>
          </div>
        </div>

        <div className="card p-3">
          <h3 className="font-semibold mb-2">MiroFish Proof</h3>
          {!explainability.mirofish ? (
            <div className="text-sm text-slate-400">No MiroFish contribution in latest run.</div>
          ) : (
            <div className="text-sm space-y-1">
              <div>Recommendation: {explainability.mirofish.recommendation}</div>
              <div>Confidence: {Math.round((explainability.mirofish.confidence || 0) * 100)}%</div>
              <div>Provider Mode: <span className="font-semibold">{explainability.providerMode}</span></div>
              <div>
                Proof Verdict:{' '}
                <span className={explainability.providerMode.startsWith('live') ? 'font-semibold text-emerald-700' : 'font-semibold text-red-700'}>
                  {explainability.providerMode.startsWith('live') ? 'LIVE MIROFISH' : 'FALLBACK (NOT LIVE)'}
                </span>
              </div>
              <div>Bias: {explainability.context?.directional_bias || '--'}</div>
              <div>Timestamp: {fmtTs(explainability.context?.timestamp)}</div>
              {explainability.context?.live_error && <div className="text-red-700">Live error: {explainability.context.live_error}</div>}
              <details>
                <summary className="cursor-pointer text-xs text-slate-400">Show raw MiroFish context</summary>
                <pre className="text-xs mt-2 overflow-auto max-h-40">{JSON.stringify(explainability.context, null, 2)}</pre>
              </details>
            </div>
          )}
        </div>
      </section>

      <section className="card p-3">
        <div className="flex items-center justify-between gap-2 mb-2">
          <h3 className="font-semibold">MiroFish Diagnostics (Deep Proof)</h3>
          <button className="btn btn-muted" onClick={() => void refresh(ticker)}>Re-run diagnostics</button>
        </div>
        {!mirofishDiag ? (
          <div className="text-sm text-slate-400">Diagnostics not loaded yet.</div>
        ) : (
          <div className="space-y-2">
            <div className="text-sm">
              Verdict:{' '}
              <span className={mirofishDiag?.verdict === 'LIVE' ? 'font-semibold text-emerald-700' : 'font-semibold text-red-700'}>
                {mirofishDiag?.verdict || 'UNKNOWN'}
              </span>{' '}
              · Provider Mode: <span className="font-semibold">{mirofishDiag?.provider_mode || '--'}</span>
              {' '}· Readiness: <span className="font-semibold">{mirofishDiag?.readiness_score ?? 0}%</span>
            </div>
            {mirofishDiag?.live_error && <div className="text-xs text-red-700">{mirofishDiag.live_error}</div>}
            {!!(mirofishDiag?.recommendations || []).length && (
              <ul className="text-xs list-disc pl-4 space-y-1">
                {(mirofishDiag.recommendations || []).map((r: string, idx: number) => <li key={idx}>{r}</li>)}
              </ul>
            )}
            <div className="overflow-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-left border-b border-slate-700">
                    <th className="py-1">Check</th>
                    <th className="py-1">OK</th>
                    <th className="py-1">Detail</th>
                  </tr>
                </thead>
                <tbody>
                  {(mirofishDiag?.checks || []).map((c: any) => (
                    <tr key={c.name} className="border-b border-slate-800/70">
                      <td className="py-1">{c.name}</td>
                      <td className="py-1">{c.ok ? 'yes' : 'no'}</td>
                      <td className="py-1 break-all">{c.detail}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <details>
              <summary className="cursor-pointer text-xs text-slate-400">Show sample predict payload</summary>
              <pre className="text-xs mt-2 overflow-auto max-h-48">{JSON.stringify(mirofishDiag?.sample_predict, null, 2)}</pre>
            </details>
          </div>
        )}
      </section>

      <section className="card p-3">
        <h3 className="font-semibold mb-2">Agent Reliability Table</h3>
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead className="text-slate-300">
              <tr className="text-left border-b border-slate-700">
                <th className="py-1">Agent</th>
                <th className="py-1">Reliability</th>
                <th className="py-1">Updated</th>
              </tr>
            </thead>
            <tbody>
              {performance.map((p) => (
                <tr key={p.agent_name} className="border-b border-slate-800/70">
                  <td className="py-1">{p.agent_name}</td>
                  <td className="py-1">{Math.round((p.reliability_score || 0) * 100)}%</td>
                  <td className="py-1">{fmtTs(p.updated_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!performance.length && <div className="text-sm text-slate-400">No reliability stats yet (seed via evaluation/training flows).</div>}
        </div>
      </section>
    </main>
  )
}
