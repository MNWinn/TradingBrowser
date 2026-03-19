'use client'

import { useEffect, useMemo, useState } from 'react'
import {
  bulkUpdateComplianceViolations,
  exportComplianceCsv,
  getComplianceAnalytics,
  getComplianceSummary,
  getComplianceViolationTimeline,
  getComplianceViolations,
  updateComplianceViolation,
} from '@/lib/api'

type StatusFilter = 'all' | 'open' | 'acknowledged' | 'waived' | 'remediated'
type SeverityFilter = 'all' | 'low' | 'medium' | 'high' | 'critical'
type SortFilter = 'newest' | 'oldest' | 'severity'

export default function CompliancePage() {
  const [status, setStatus] = useState<StatusFilter>('all')
  const [severity, setSeverity] = useState<SeverityFilter>('all')
  const [sort, setSort] = useState<SortFilter>('severity')
  const [symbol, setSymbol] = useState('')
  const [assigneeFilter, setAssigneeFilter] = useState('')
  const [mineOnly, setMineOnly] = useState(false)

  const [summary, setSummary] = useState<any>(null)
  const [analytics, setAnalytics] = useState<any>(null)
  const [items, setItems] = useState<any[]>([])
  const [notesById, setNotesById] = useState<Record<number, string>>({})
  const [assigneeById, setAssigneeById] = useState<Record<number, string>>({})
  const [selectedIds, setSelectedIds] = useState<number[]>([])
  const [timelineById, setTimelineById] = useState<Record<number, any[]>>({})
  const [timelineLoadingId, setTimelineLoadingId] = useState<number | null>(null)
  const [busy, setBusy] = useState<number | null>(null)
  const [bulkBusy, setBulkBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const filters = useMemo(
    () => ({
      status: status === 'all' ? undefined : status,
      severity: severity === 'all' ? undefined : severity,
      symbol: symbol.trim() || undefined,
      assignee: mineOnly ? 'compliance-console' : assigneeFilter.trim() || undefined,
      sort,
    }),
    [status, severity, symbol, assigneeFilter, mineOnly, sort],
  )

  const load = async () => {
    setError(null)
    try {
      const [s, a, v] = await Promise.all([
        getComplianceSummary(),
        getComplianceAnalytics(),
        getComplianceViolations(filters, 150),
      ])
      setSummary(s)
      setAnalytics(a)
      const nextItems = v.items || []
      setItems(nextItems)
      setSelectedIds((prev) => prev.filter((id) => nextItems.some((it: any) => it.id === id)))
      setAssigneeById((prev) => {
        const next = { ...prev }
        for (const it of nextItems) {
          if (next[it.id] === undefined) next[it.id] = it.assignee || ''
        }
        return next
      })
    } catch (e: any) {
      setError(e?.message || 'Failed to load compliance queue')
    }
  }

  useEffect(() => {
    void load()
  }, [filters])

  const mutate = async (id: number, nextStatus: 'acknowledged' | 'waived' | 'remediated') => {
    setBusy(id)
    setError(null)
    try {
      await updateComplianceViolation(id, {
        status: nextStatus,
        acknowledged_by: 'compliance-console',
        assignee: assigneeById[id] || undefined,
        resolution_notes: notesById[id] || undefined,
      })
      await load()
    } catch (e: any) {
      setError(e?.message || 'Failed to update violation')
    } finally {
      setBusy(null)
    }
  }

  const bulkMutate = async (nextStatus: 'acknowledged' | 'waived' | 'remediated') => {
    if (!selectedIds.length) return
    setBulkBusy(true)
    setError(null)
    try {
      await bulkUpdateComplianceViolations({
        ids: selectedIds,
        status: nextStatus,
        acknowledged_by: 'compliance-console',
      })
      await load()
    } catch (e: any) {
      setError(e?.message || 'Failed to bulk update violations')
    } finally {
      setBulkBusy(false)
    }
  }

  const assignOwner = async (v: any) => {
    setBusy(v.id)
    setError(null)
    try {
      await updateComplianceViolation(v.id, {
        status: v.status,
        acknowledged_by: 'compliance-console',
        assignee: assigneeById[v.id] || undefined,
        resolution_notes: notesById[v.id] || undefined,
      })
      await load()
    } catch (e: any) {
      setError(e?.message || 'Failed to assign owner')
    } finally {
      setBusy(null)
    }
  }

  const toggleTimeline = async (id: number) => {
    if (timelineById[id]) {
      setTimelineById((prev) => {
        const next = { ...prev }
        delete next[id]
        return next
      })
      return
    }

    setTimelineLoadingId(id)
    setError(null)
    try {
      const data = await getComplianceViolationTimeline(id, 100)
      setTimelineById((prev) => ({ ...prev, [id]: data.items || [] }))
    } catch (e: any) {
      setError(e?.message || 'Failed to load timeline')
    } finally {
      setTimelineLoadingId(null)
    }
  }

  const toggleSelected = (id: number) => {
    setSelectedIds((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]))
  }

  const ageLabel = (ageSeconds: number) => {
    if (ageSeconds >= 86400) return `${Math.floor(ageSeconds / 86400)}d`
    if (ageSeconds >= 3600) return `${Math.floor(ageSeconds / 3600)}h`
    if (ageSeconds >= 60) return `${Math.floor(ageSeconds / 60)}m`
    return `${ageSeconds}s`
  }

  const slaSeconds = (sev: string) => {
    if (sev === 'critical') return 15 * 60
    if (sev === 'high') return 60 * 60
    if (sev === 'medium') return 4 * 60 * 60
    return 24 * 60 * 60
  }

  const slaState = (sev: string, ageSeconds: number) => {
    const budget = slaSeconds(sev)
    if (ageSeconds > budget) return 'breach'
    if (ageSeconds > budget * 0.75) return 'at-risk'
    return 'ok'
  }

  const downloadCsv = async () => {
    try {
      const csv = await exportComplianceCsv(filters)
      const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
      const url = window.URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = 'compliance_violations.csv'
      link.click()
      window.URL.revokeObjectURL(url)
    } catch (e: any) {
      setError(e?.message || 'CSV export failed')
    }
  }

  return (
    <main className="space-y-3">
      <section className="card p-4">
        <h1 className="text-xl font-semibold mb-1">Compliance Violation Queue</h1>
        <p className="text-sm text-slate-400">Disposition and track pre-trade compliance exceptions.</p>
      </section>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <div className="card p-3 text-sm">Open: <span className="font-semibold">{summary?.open || 0}</span></div>
        <div className="card p-3 text-sm">Acknowledged: <span className="font-semibold">{summary?.acknowledged || 0}</span></div>
        <div className="card p-3 text-sm">Waived: <span className="font-semibold">{summary?.waived || 0}</span></div>
        <div className="card p-3 text-sm">Remediated: <span className="font-semibold">{summary?.remediated || 0}</span></div>
      </section>

      <section className="grid grid-cols-2 md:grid-cols-4 gap-2">
        <div className="card p-3 text-sm">MTTR: <span className="font-semibold">{Number(analytics?.mttr_hours || 0).toFixed(2)}h</span></div>
        <div className="card p-3 text-sm">SLA Overdue Open: <span className="font-semibold">{analytics?.sla_overdue_open || 0}</span></div>
        <div className="card p-3 text-sm">Severe Open: <span className="font-semibold">{analytics?.severe_open || 0}</span></div>
        <div className="card p-3 text-sm">Critical Total: <span className="font-semibold">{analytics?.by_severity?.critical || 0}</span></div>
      </section>

      <section className="card p-3 flex flex-wrap gap-2 items-center">
        <select value={status} onChange={(e) => setStatus(e.target.value as StatusFilter)} className="px-2 py-1 text-sm">
          <option value="all">All status</option>
          <option value="open">Open</option>
          <option value="acknowledged">Acknowledged</option>
          <option value="waived">Waived</option>
          <option value="remediated">Remediated</option>
        </select>

        <select value={severity} onChange={(e) => setSeverity(e.target.value as SeverityFilter)} className="px-2 py-1 text-sm">
          <option value="all">All severity</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>

        <select value={sort} onChange={(e) => setSort(e.target.value as SortFilter)} className="px-2 py-1 text-sm">
          <option value="severity">Sort: severity</option>
          <option value="newest">Sort: newest</option>
          <option value="oldest">Sort: oldest</option>
        </select>

        <input
          value={symbol}
          onChange={(e) => setSymbol(e.target.value.toUpperCase())}
          className="px-2 py-1 text-sm"
          placeholder="Symbol"
        />

        <input
          value={assigneeFilter}
          onChange={(e) => setAssigneeFilter(e.target.value)}
          className="px-2 py-1 text-sm"
          placeholder="Assignee"
          disabled={mineOnly}
        />

        <label className="text-xs flex items-center gap-1 px-2">
          <input type="checkbox" checked={mineOnly} onChange={(e) => setMineOnly(e.target.checked)} />
          Mine only
        </label>

        <button onClick={() => void load()} className="btn btn-primary">Refresh</button>
        <button onClick={() => void downloadCsv()} className="btn btn-muted">Export CSV</button>
      </section>

      <section className="card p-3 flex flex-wrap gap-2 items-center">
        <span className="text-xs text-slate-400">Selected: {selectedIds.length}</span>
        <button disabled={bulkBusy || !selectedIds.length} onClick={() => void bulkMutate('acknowledged')} className="btn btn-muted">Bulk Acknowledge</button>
        <button disabled={bulkBusy || !selectedIds.length} onClick={() => void bulkMutate('waived')} className="btn btn-muted">Bulk Waive</button>
        <button disabled={bulkBusy || !selectedIds.length} onClick={() => void bulkMutate('remediated')} className="btn btn-primary">Bulk Remediate</button>
      </section>

      {error && <section className="card p-3 text-sm text-red-700">{error}</section>}

      <section className="card p-3 space-y-2">
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={items.length > 0 && selectedIds.length === items.length}
            onChange={(e) => setSelectedIds(e.target.checked ? items.map((x) => x.id) : [])}
          />
          <span className="text-xs text-slate-400">Select all visible</span>
        </div>

        {!items.length && <div className="text-sm text-slate-400">No violations for current filters.</div>}

        {items.map((v) => {
          const sla = slaState(v.severity, v.age_seconds || 0)
          const slaClass =
            sla === 'breach'
              ? 'border-red-600 bg-red-50'
              : sla === 'at-risk'
                ? 'border-amber-500 bg-amber-50'
                : 'border-slate-700'

          return (
            <div key={v.id} className={`rounded border p-3 space-y-2 ${slaClass}`}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-start gap-2">
                  <input type="checkbox" checked={selectedIds.includes(v.id)} onChange={() => toggleSelected(v.id)} />
                  <div>
                    <div className="text-sm font-semibold">#{v.id} · {v.rule_code}</div>
                    <div className="text-xs text-slate-400">
                      {v.policy_name} · {v.symbol || '--'} · {v.severity} · {v.status} · owner {v.assignee || '--'}
                    </div>
                  </div>
                </div>
                <div className="text-xs text-slate-400 text-right">
                  <div>{v.created_at}</div>
                  <div>Age: {ageLabel(v.age_seconds || 0)} · SLA {sla}</div>
                </div>
              </div>

              <div className="text-xs text-slate-400 break-all">
                {v.details?.hard_reasons?.join(', ') || v.details?.adapter_reason || JSON.stringify(v.details)}
              </div>

              <input
                value={notesById[v.id] || ''}
                onChange={(e) => setNotesById((prev) => ({ ...prev, [v.id]: e.target.value }))}
                className="w-full px-2 py-1 text-sm"
                placeholder="Resolution notes"
              />

              <div className="flex flex-wrap items-center gap-2">
                <input
                  value={assigneeById[v.id] || ''}
                  onChange={(e) => setAssigneeById((prev) => ({ ...prev, [v.id]: e.target.value }))}
                  className="px-2 py-1 text-sm"
                  placeholder="Owner / assignee"
                />
                <button disabled={busy === v.id} onClick={() => void assignOwner(v)} className="btn btn-muted">Save Owner</button>
              </div>

              <div className="flex flex-wrap gap-2">
                <a href={`/journal?symbol=${encodeURIComponent(v.symbol || '')}`} className="btn btn-muted">Journal</a>
                <button onClick={() => void toggleTimeline(v.id)} className="btn btn-muted">
                  {timelineById[v.id] ? 'Hide Timeline' : 'Show Timeline'}
                </button>
                <button
                  disabled={busy === v.id}
                  onClick={() => void mutate(v.id, 'acknowledged')}
                  className="btn btn-muted"
                >
                  Acknowledge
                </button>
                <button
                  disabled={busy === v.id}
                  onClick={() => void mutate(v.id, 'waived')}
                  className="btn btn-muted"
                >
                  Waive
                </button>
                <button
                  disabled={busy === v.id}
                  onClick={() => void mutate(v.id, 'remediated')}
                  className="btn btn-primary"
                >
                  Remediate
                </button>
              </div>

              {timelineLoadingId === v.id && <div className="text-xs text-slate-400">Loading timeline...</div>}
              {timelineById[v.id] && (
                <div className="rounded border border-slate-700 p-2 space-y-1">
                  {(timelineById[v.id] || []).map((ev: any, idx: number) => (
                    <div key={`${ev.created_at}-${idx}`} className="text-xs flex justify-between gap-2">
                      <span className="font-medium">{ev.event_type}</span>
                      <span className="text-slate-400">{ev.actor || 'system'} · {ev.created_at}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </section>
    </main>
  )
}
