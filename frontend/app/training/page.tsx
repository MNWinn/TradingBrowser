'use client'

import { useEffect, useMemo, useState } from 'react'
import { getAuditLogs, runDailyEvaluation, runTrainingJob } from '@/lib/api'

export default function TrainingPage() {
  const [trainingRes, setTrainingRes] = useState<any>(null)
  const [evaluationRes, setEvaluationRes] = useState<any>(null)
  const [logs, setLogs] = useState<any[]>([])
  const [loadingTrain, setLoadingTrain] = useState(false)
  const [loadingEval, setLoadingEval] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refreshLogs = async () => {
    try {
      const data = await getAuditLogs(100)
      setLogs(data.items || [])
    } catch (e: any) {
      setError(e.message || 'Failed to load logs')
    }
  }

  useEffect(() => {
    void refreshLogs()
  }, [])

  const runTrain = async () => {
    setLoadingTrain(true)
    setError(null)
    try {
      const data = await runTrainingJob()
      setTrainingRes(data)
      await refreshLogs()
    } catch (e: any) {
      setError(e.message || 'Training run failed')
    } finally {
      setLoadingTrain(false)
    }
  }

  const runEval = async () => {
    setLoadingEval(true)
    setError(null)
    try {
      const data = await runDailyEvaluation()
      setEvaluationRes(data)
      await refreshLogs()
    } catch (e: any) {
      setError(e.message || 'Evaluation failed')
    } finally {
      setLoadingEval(false)
    }
  }

  const trainingLogs = useMemo(() => logs.filter((l) => ['DAILY_EVALUATION', 'SWARM_RUN', 'SIGNAL_GENERATED'].includes(l.event_type)), [logs])

  return (
    <main className="space-y-3">
      <section className="card p-4">
        <h1 className="text-xl font-semibold mb-1">Model Training & Evaluation</h1>
        <p className="text-sm text-slate-300">Queue training jobs, run daily recalibration, and inspect audit trail.</p>
      </section>

      <section className="card p-4 flex flex-wrap gap-2">
        <button onClick={runTrain} disabled={loadingTrain} className="btn btn-primary">
          {loadingTrain ? 'Queueing…' : 'Run Training'}
        </button>
        <button onClick={runEval} disabled={loadingEval} className="btn btn-muted">
          {loadingEval ? 'Evaluating…' : 'Run Daily Evaluation'}
        </button>
        <button onClick={refreshLogs} className="btn btn-muted">Refresh Logs</button>
      </section>

      {error && <section className="card p-3 text-sm text-rose-300">{error}</section>}

      <section className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        <div className="card p-4">
          <h2 className="font-semibold mb-2">Training Queue Result</h2>
          <pre className="bg-slate-950/70 border border-slate-800 rounded p-2 text-xs overflow-auto">{JSON.stringify(trainingRes, null, 2)}</pre>
        </div>
        <div className="card p-4">
          <h2 className="font-semibold mb-2">Evaluation Result</h2>
          <pre className="bg-slate-950/70 border border-slate-800 rounded p-2 text-xs overflow-auto">{JSON.stringify(evaluationRes, null, 2)}</pre>
        </div>
      </section>

      <section className="card p-4">
        <h2 className="font-semibold mb-2">Recent Learning / Evaluation Logs</h2>
        <div className="space-y-2 text-sm">
          {trainingLogs.length === 0 && <div className="text-slate-400">No related logs yet.</div>}
          {trainingLogs.map((l) => (
            <div key={l.id} className="rounded border border-slate-700 p-2">
              <div className="flex justify-between">
                <span className="font-medium">{l.event_type}</span>
                <span className="text-xs text-slate-400">{l.created_at}</span>
              </div>
              <pre className="text-xs text-slate-300 mt-1 overflow-auto">{JSON.stringify(l.payload, null, 2)}</pre>
            </div>
          ))}
        </div>
      </section>
    </main>
  )
}
