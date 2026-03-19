'use client'

import Link from 'next/link'
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  addWatchlistTicker,
  getComplianceAnalytics,
  getComplianceSummary,
  getComplianceViolations,
  getExecutionAnalytics,
  getMirofishDeepSwarm,
  getMirofishPredict,
  getMirofishStatus,
  getQuote,
  getSignal,
  getSwarmFocus,
  getSwarmResults,
  getWatchlist,
  getReadinessSummary,
  listJournal,
  removeWatchlistTicker,
  runDailyEvaluation,
  runStrategyBacktest,
  runSwarm,
  runSwarmFocusNow,
  runTrainingJob,
  submitOrder,
  updateComplianceViolation,
  updateExecutionMode,
  updateSwarmFocus,
  validateExecution,
  runAllReadinessDiagnostics,
} from '@/lib/api'
import { useMarketStream } from '@/lib/useMarketStream'
import { Sidebar } from '@/components/Sidebar'
import { ChartPane } from '@/components/ChartPane'
import { ProbabilityDrawer } from '@/components/ProbabilityDrawer'
import { AgentFleetVisualizer } from '@/components/agents'

const USER_ID = 'demo'
const INDEX_TICKERS = ['SPY', 'QQQ', 'IWM']
const MOVER_TICKERS = ['AAPL', 'MSFT', 'NVDA', 'TSLA', 'AMD', 'META', 'AMZN']

type Section = 'overview' | 'workspace' | 'swarm' | 'paper' | 'strategy' | 'training' | 'settings'
type Toast = { id: number; type: 'ok' | 'err'; text: string }

type RefreshBySection = Record<Section, number>

const DEFAULT_REFRESH_MS: RefreshBySection = {
  overview: 8000,
  workspace: 8000,
  swarm: 8000,
  paper: 5000,
  strategy: 0,
  training: 0,
  settings: 15000,
}

function MetricCard({ label, value, hint, tone = 'default' }: { label: string; value: string; hint?: string; tone?: 'default' | 'good' | 'bad' | 'warn' }) {
  const toneClass = tone === 'good' ? 'text-emerald-300' : tone === 'bad' ? 'text-rose-300' : tone === 'warn' ? 'text-amber-300' : 'text-slate-100'
  return (
    <div className="card card-hover p-3">
      <div className="text-xs text-slate-400">{label}</div>
      <div className={`text-2xl font-semibold mt-1 ${toneClass}`}>{value}</div>
      {hint && <div className="text-xs text-slate-400 mt-1">{hint}</div>}
    </div>
  )
}

function JsonPanel({ title, value }: { title: string; value: any }) {
  return (
    <div className="card card-hover p-3">
      <h3 className="font-semibold mb-2">{title}</h3>
      {!value ? (
        <div className="text-sm text-slate-400">No data yet.</div>
      ) : (
        <pre className="text-xs bg-slate-950/70 border border-slate-800 rounded p-2 overflow-auto max-h-[280px]">{JSON.stringify(value, null, 2)}</pre>
      )}
    </div>
  )
}

function SkeletonGrid() {
  return (
    <section className="grid grid-cols-1 md:grid-cols-3 gap-3">
      {Array.from({ length: 3 }).map((_, i) => (
        <div key={i} className="card p-3 animate-pulse">
          <div className="h-4 w-32 bg-slate-700/60 rounded mb-3" />
          <div className="h-3 w-full bg-slate-700/40 rounded mb-2" />
          <div className="h-3 w-4/5 bg-slate-700/40 rounded mb-2" />
          <div className="h-3 w-2/3 bg-slate-700/40 rounded" />
        </div>
      ))}
    </section>
  )
}

export default function DashboardPage() {
  const tick = useMarketStream()
  const [menuOpen, setMenuOpen] = useState(false)
  const [active, setActive] = useState<Section>('overview')

  const [indices, setIndices] = useState<any[]>([])
  const [movers, setMovers] = useState<any[]>([])
  const [watchlist, setWatchlist] = useState<string[]>([])
  const [watchSignals, setWatchSignals] = useState<any[]>([])
  const [mirofishStatus, setMirofishStatus] = useState<any>(null)
  const [mirofishSnap, setMirofishSnap] = useState<any>(null)
  const [readinessSnap, setReadinessSnap] = useState<any>(null)
  const [readinessSummary, setReadinessSummary] = useState<any>(null)
  const [runningReadiness, setRunningReadiness] = useState(false)

  const [ticker, setTicker] = useState('AAPL')
  const [probability, setProbability] = useState<any>(null)
  const [signal, setSignal] = useState<any>(null)
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [analysisTimeframe, setAnalysisTimeframe] = useState('5m')

  const [swarmTicker, setSwarmTicker] = useState('AAPL')
  const [swarmResult, setSwarmResult] = useState<any>(null)
  const [deepSwarm, setDeepSwarm] = useState<any>(null)
  const [focusSwarm, setFocusSwarm] = useState<any>(null)
  const [focusInput, setFocusInput] = useState('AAPL,MSFT,NVDA')

  const [orderResult, setOrderResult] = useState<any>(null)
  const [orderCheck, setOrderCheck] = useState<any>(null)
  const [analytics, setAnalytics] = useState<any>(null)
  const [journal, setJournal] = useState<any[]>([])
  const [complianceSummary, setComplianceSummary] = useState<any>(null)
  const [complianceAnalytics, setComplianceAnalytics] = useState<any>(null)
  const [complianceViolations, setComplianceViolations] = useState<any[]>([])

  const [backtestResult, setBacktestResult] = useState<any>(null)
  const [trainingResult, setTrainingResult] = useState<any>(null)
  const [evalResult, setEvalResult] = useState<any>(null)

  const [loadingCore, setLoadingCore] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [density, setDensity] = useState<'cozy' | 'compact'>('cozy')
  const [showRawJson, setShowRawJson] = useState(false)
  const [autoRefresh, setAutoRefresh] = useState(true)
  const [refreshBySection, setRefreshBySection] = useState<RefreshBySection>(DEFAULT_REFRESH_MS)
  const [focusMode, setFocusMode] = useState(false)
  const [lastUpdated, setLastUpdated] = useState('—')
  const toastSeenRef = useRef<Record<string, number>>({})

  const BTN_PRIMARY = 'btn btn-primary'
  const BTN_SUCCESS = 'btn btn-success'
  const BTN_MUTED = 'btn btn-muted'

  const pushToast = useCallback((type: Toast['type'], text: string) => {
    const now = Date.now()
    const last = toastSeenRef.current[text] || 0
    if (now - last < 6000) return
    toastSeenRef.current[text] = now

    const id = now + Math.floor(Math.random() * 1000)
    setToasts((prev) => [...prev, { id, type, text }])
    window.setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 2400)
  }, [])

  const avgIndexMove = useMemo(() => {
    if (!indices.length) return 0
    return indices.reduce((acc, i) => acc + i.change_pct, 0) / indices.length
  }, [indices])

  const latestMode = useMemo(() => analytics?.mode_timeline?.[0]?.mode || 'research', [analytics])

  const loadCore = async () => {
    const [idx, mov, wl, mStatus, fSwarm] = await Promise.all([
      Promise.all(INDEX_TICKERS.map((t) => getQuote(t))),
      Promise.all(MOVER_TICKERS.map((t) => getQuote(t))),
      getWatchlist(USER_ID),
      getMirofishStatus(),
      getSwarmFocus(),
    ])

    const sortedMovers = mov.sort((a, b) => Math.abs(b.change_pct) - Math.abs(a.change_pct)).slice(0, 5)
    setIndices(idx)
    setMovers(sortedMovers)
    setMirofishStatus(mStatus)
    setFocusSwarm(fSwarm)
    if (Array.isArray(fSwarm?.tickers)) setFocusInput(fSwarm.tickers.join(','))

    const wlRaw: string[] = wl.items || []
    const wlTickers = wlRaw.map((x) => String(x || '').toUpperCase()).filter((x) => /^[A-Z.]{1,6}$/.test(x))
    setWatchlist(wlTickers)
    if (wlTickers.length && !wlTickers.includes(ticker)) setTicker(wlTickers[0])

    const sigs = wlTickers.length ? await Promise.all(wlTickers.slice(0, 4).map((t) => getSignal(t))) : []
    setWatchSignals(sigs)

    const sampleTicker = wlTickers[0] || 'AAPL'
    const mPred = await getMirofishPredict({ ticker: sampleTicker, timeframe: '5m' })
    setMirofishSnap(mPred)
  }

  const loadPaper = async () => {
    const [a, j, cs, ca, cv, rs] = await Promise.all([
      getExecutionAnalytics(100),
      listJournal(10),
      getComplianceSummary(),
      getComplianceAnalytics(),
      getComplianceViolations({ status: 'open', sort: 'severity' }, 8),
      getReadinessSummary(200),
    ])
    setAnalytics(a)
    setJournal(j.items || [])
    setComplianceSummary(cs)
    setComplianceAnalytics(ca)
    setComplianceViolations(cv.items || [])
    setReadinessSummary(rs)
  }

  const refreshNow = useCallback(async () => {
    try {
      setError(null)
      setLoadingCore(true)
      await Promise.all([loadCore(), loadPaper()])
      setLastUpdated(new Date().toLocaleTimeString())
    } catch (e: any) {
      const msg = e?.message || 'Failed to load dashboard'
      setError(msg)
      if (String(msg).toLowerCase().includes('failed to fetch')) {
        pushToast('err', 'Network/API temporarily unavailable')
      } else {
        pushToast('err', msg)
      }
    } finally {
      setLoadingCore(false)
    }
  }, [pushToast])

  const selectSection = useCallback((section: Section) => {
    setActive(section)
    if (typeof window !== 'undefined') window.localStorage.setItem('tb_active_section', section)
    setMenuOpen(false)
  }, [])

  useEffect(() => {
    const savedSection = typeof window !== 'undefined' ? (window.localStorage.getItem('tb_active_section') as Section | null) : null
    const savedTicker = typeof window !== 'undefined' ? window.localStorage.getItem('tb_ticker') : null
    const savedSwarmTicker = typeof window !== 'undefined' ? window.localStorage.getItem('tb_swarm_ticker') : null
    const savedTf = typeof window !== 'undefined' ? window.localStorage.getItem('tb_timeframe') : null
    const savedDensity = typeof window !== 'undefined' ? window.localStorage.getItem('tb_density') : null
    const savedJson = typeof window !== 'undefined' ? window.localStorage.getItem('tb_show_json') : null
    const savedAuto = typeof window !== 'undefined' ? window.localStorage.getItem('tb_auto_refresh') : null
    const savedRefreshMap = typeof window !== 'undefined' ? window.localStorage.getItem('tb_refresh_by_section') : null
    const savedFocus = typeof window !== 'undefined' ? window.localStorage.getItem('tb_focus_mode') : null

    if (savedSection) setActive(savedSection)
    if (savedTicker) setTicker(savedTicker)
    if (savedSwarmTicker) setSwarmTicker(savedSwarmTicker)
    if (savedTf) setAnalysisTimeframe(savedTf)
    if (savedDensity === 'compact' || savedDensity === 'cozy') setDensity(savedDensity)
    if (savedJson === '1') setShowRawJson(true)
    if (savedAuto === '0') setAutoRefresh(false)
    if (savedFocus === '1') setFocusMode(true)
    if (savedRefreshMap) {
      try {
        const parsed = JSON.parse(savedRefreshMap)
        setRefreshBySection({ ...DEFAULT_REFRESH_MS, ...parsed })
      } catch {
        // ignore malformed local storage
      }
    }

    const onKey = (e: KeyboardEvent) => {
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes((e.target as HTMLElement)?.tagName)) return
      const map: Record<string, Section> = {
        '1': 'overview',
        '2': 'workspace',
        '3': 'swarm',
        '4': 'paper',
        '5': 'strategy',
        '6': 'training',
        '7': 'settings',
      }
      const sec = map[e.key]
      if (sec) selectSection(sec)
    }
    window.addEventListener('keydown', onKey)

    void refreshNow()

    return () => {
      window.removeEventListener('keydown', onKey)
    }
  }, [refreshNow, selectSection])

  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem('tb_ticker', ticker)
  }, [ticker])

  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem('tb_swarm_ticker', swarmTicker)
  }, [swarmTicker])

  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem('tb_timeframe', analysisTimeframe)
  }, [analysisTimeframe])

  useEffect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem('tb_density', density)
    window.localStorage.setItem('tb_show_json', showRawJson ? '1' : '0')
    window.localStorage.setItem('tb_auto_refresh', autoRefresh ? '1' : '0')
    window.localStorage.setItem('tb_refresh_by_section', JSON.stringify(refreshBySection))
    window.localStorage.setItem('tb_focus_mode', focusMode ? '1' : '0')
  }, [density, showRawJson, autoRefresh, refreshBySection, focusMode])

  useEffect(() => {
    if (!autoRefresh) return
    const everyMs = refreshBySection[active]
    if (!everyMs || everyMs < 1000) return
    const id = window.setInterval(() => void refreshNow(), everyMs)
    return () => window.clearInterval(id)
  }, [active, autoRefresh, refreshBySection, refreshNow])

  const runAnalysis = async (timeframe: string) => {
    setAnalysisLoading(true)
    setAnalysisTimeframe(timeframe)
    try {
      const [p, s] = await Promise.all([getMirofishPredict({ ticker, timeframe }), getSignal(ticker)])
      setProbability({
        next_bar_direction_probability: { up: p.directional_bias === 'BULLISH' ? p.confidence : 1 - (p.confidence || 0.5) },
        target_before_stop_probability: 0.5,
        volatility_regime: 'medium',
        model_confidence: p.confidence || 0.5,
        recommendation: p.leaning,
        contributors: ['mirofish'],
        plain_english: p.scenario_summary,
      })
      setSignal(s)
      pushToast('ok', `Analysis updated for ${ticker}`)
    } catch (e: any) {
      pushToast('err', e.message || 'Analysis failed')
    } finally {
      setAnalysisLoading(false)
    }
  }

  const runSwarmNow = async () => {
    try {
      await runSwarm(swarmTicker)
      const r = await getSwarmResults(swarmTicker)
      setSwarmResult(r)
      pushToast('ok', `Swarm run complete for ${swarmTicker}`)
    } catch (e: any) {
      pushToast('err', e.message || 'Swarm failed')
    }
  }

  const runDeepSwarmNow = async () => {
    try {
      const deep = await getMirofishDeepSwarm({ ticker: swarmTicker })
      setDeepSwarm(deep)
      pushToast('ok', `Deep MiroFish swarm complete for ${swarmTicker}`)
    } catch (e: any) {
      pushToast('err', e.message || 'Deep swarm failed')
    }
  }

  const saveFocusConfig = async () => {
    try {
      const tickers = focusInput
        .split(',')
        .map((s) => s.trim().toUpperCase())
        .filter(Boolean)
      const next = await updateSwarmFocus({
        tickers,
        enabled: focusSwarm?.enabled ?? true,
        interval_sec: focusSwarm?.interval_sec ?? 240,
      })
      setFocusSwarm(next)
      pushToast('ok', 'Focus ticker set updated')
    } catch (e: any) {
      pushToast('err', e.message || 'Failed to update focus tickers')
    }
  }

  const runFocusCycleNow = async () => {
    try {
      await runSwarmFocusNow()
      const next = await getSwarmFocus()
      setFocusSwarm(next)
      pushToast('ok', 'Background deep cycle triggered')
    } catch (e: any) {
      pushToast('err', e.message || 'Failed to run focus cycle')
    }
  }

  const submitQuickOrder = async () => {
    try {
      const payload = {
        symbol: ticker,
        side: 'buy' as const,
        qty: 1,
        type: 'market' as const,
        stop_loss: 1,
        recommendation: { action: 'LONG', source: 'dashboard_unified' },
        rationale: { source: 'dashboard_unified' },
        idempotency_key: `dash-${Date.now()}`,
      }
      const [check, submitted] = await Promise.all([validateExecution(payload), submitOrder(payload)])
      setOrderCheck(check)
      setOrderResult(submitted)
      await loadPaper()
      pushToast('ok', 'Order submitted')
    } catch (e: any) {
      pushToast('err', e.message || 'Order submit failed')
    }
  }

  const runBacktestNow = async () => {
    try {
      const r = await runStrategyBacktest({
        name: 'Unified Dashboard Strategy',
        ticker,
        timeframe: analysisTimeframe,
        lookback: 120,
        risk_pct: 1,
      })
      setBacktestResult(r)
      pushToast('ok', 'Backtest complete')
    } catch (e: any) {
      pushToast('err', e.message || 'Backtest failed')
    }
  }

  const setPaperMode = async () => {
    try {
      await updateExecutionMode({ mode: 'paper', live_trading_enabled: false, changed_by: 'dashboard-user' })
      await loadPaper()
      pushToast('ok', 'Mode set to paper')
    } catch (e: any) {
      pushToast('err', e.message || 'Mode update failed')
    }
  }

  const runTrainingEval = async () => {
    try {
      const [tr, ev] = await Promise.all([runTrainingJob(), runDailyEvaluation()])
      setTrainingResult(tr)
      setEvalResult(ev)
      pushToast('ok', 'Training + daily evaluation triggered')
    } catch (e: any) {
      pushToast('err', e.message || 'Training/eval failed')
    }
  }

  const runReadinessDiagnosticsNow = async () => {
    setRunningReadiness(true)
    try {
      const snapshot = await runAllReadinessDiagnostics()
      setReadinessSnap(snapshot)
      const rs = await getReadinessSummary(200)
      setReadinessSummary(rs)
      pushToast('ok', `Readiness ${snapshot?.ready ? 'PASS' : 'FAIL'}`)
    } catch (e: any) {
      pushToast('err', e.message || 'Readiness diagnostics failed')
    } finally {
      setRunningReadiness(false)
    }
  }

  const acknowledgeViolation = async (violationId: number) => {
    try {
      await updateComplianceViolation(violationId, {
        status: 'acknowledged',
        acknowledged_by: 'dashboard-user',
      })
      await loadPaper()
      pushToast('ok', 'Violation acknowledged')
    } catch (e: any) {
      pushToast('err', e.message || 'Failed to acknowledge violation')
    }
  }

  const setActiveRefreshMs = (ms: number) => {
    setRefreshBySection((prev) => ({ ...prev, [active]: ms }))
  }

  const activeRefreshMs = refreshBySection[active] || 0
  const deepSection = active === 'workspace' || active === 'swarm' || active === 'paper'
  const controlsCollapsed = focusMode && deepSection

  const sections: { id: Section; label: string }[] = [
    { id: 'overview', label: 'Overview' },
    { id: 'workspace', label: 'Workspace' },
    { id: 'swarm', label: 'Swarm' },
    { id: 'paper', label: 'Paper' },
    { id: 'strategy', label: 'Strategy' },
    { id: 'training', label: 'Training' },
    { id: 'settings', label: 'Settings' },
  ]

  return (
    <main className={`${density === 'compact' ? 'tb-compact space-y-2' : 'tb-cozy space-y-3'} max-w-[1800px] mx-auto`}>
      <div className="fixed top-3 right-3 z-50 space-y-2">
        {toasts.map((t) => (
          <div key={t.id} className="px-3 py-2 rounded border border-neutral-300 bg-white text-sm shadow-sm">
            {t.text}
          </div>
        ))}
      </div>

      <section className="flex justify-end">
        <button onClick={() => setMenuOpen((v) => !v)} className={`${BTN_MUTED} md:hidden`}>Menu</button>
      </section>

      {!controlsCollapsed ? (
        <>
          <section className="card p-2 flex items-center justify-between text-xs gap-3">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-slate-400">Last updated: {lastUpdated}</span>
              {error && <span className="text-red-700">API unavailable</span>}
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => void refreshNow()} className={BTN_PRIMARY}>Refresh</button>
              <details>
                <summary className="btn btn-muted cursor-pointer">View controls</summary>
                <div className="mt-2 p-2 border border-slate-700 rounded flex flex-wrap items-center gap-2 bg-white">
                  <button onClick={() => setDensity((d) => (d === 'cozy' ? 'compact' : 'cozy'))} className={BTN_MUTED}>
                    Density: {density}
                  </button>
                  <button onClick={() => setShowRawJson((v) => !v)} className={BTN_MUTED}>
                    JSON: {showRawJson ? 'on' : 'off'}
                  </button>
                  <button onClick={() => setAutoRefresh((v) => !v)} className={BTN_MUTED}>
                    Auto-refresh: {autoRefresh ? 'on' : 'off'}
                  </button>
                  <button onClick={() => setFocusMode((v) => !v)} className={BTN_MUTED}>
                    Focus mode: {focusMode ? 'on' : 'off'}
                  </button>
                  <label className="px-2 py-1 rounded border border-slate-700">
                    Interval:
                    <select
                      value={activeRefreshMs}
                      onChange={(e) => setActiveRefreshMs(Number(e.target.value))}
                      className="ml-2 rounded px-1 py-0.5"
                    >
                      <option value={0}>manual</option>
                      <option value={3000}>3s</option>
                      <option value={5000}>5s</option>
                      <option value={8000}>8s</option>
                      <option value={12000}>12s</option>
                      <option value={20000}>20s</option>
                    </select>
                  </label>
                </div>
              </details>
            </div>
          </section>

          <section className="card p-2 flex flex-wrap items-center gap-2 text-xs">
            <button onClick={() => void runAnalysis(analysisTimeframe)} className={BTN_MUTED}>Analyze</button>
            <button onClick={() => void runSwarmNow()} className={BTN_MUTED}>Run Swarm</button>
            <button onClick={() => void submitQuickOrder()} className={BTN_MUTED}>Quick Order</button>
            <button onClick={() => void runBacktestNow()} className={BTN_MUTED}>Backtest</button>
            <button onClick={() => void runTrainingEval()} className={BTN_MUTED}>Train + Eval</button>
            <span className="text-neutral-500 ml-auto">
              Mode {latestMode.toUpperCase()} · {ticker} · Bias {mirofishSnap?.directional_bias || '--'} ({Math.round((mirofishSnap?.confidence || 0) * 100)}%) · Compliance Open {complianceSummary?.open || 0} / Overdue {complianceAnalytics?.sla_overdue_open || 0}
            </span>
          </section>

          {(complianceAnalytics?.sla_overdue_open || 0) > 0 && (
            <section className="card p-2 text-xs status-alert">
              Alert: {complianceAnalytics?.sla_overdue_open || 0} compliance violations are past SLA and need triage.
            </section>
          )}

          <section className="card p-2 flex flex-col md:flex-row md:items-center md:justify-between gap-2 text-xs">
            <div>
              <div className="font-semibold">Readiness Diagnostics</div>
              <div className="text-slate-400">Run go-live checks from dashboard or open full live-control.</div>
              {readinessSnap && (
                <div className="mt-1 text-slate-300">
                  Gate: <span className={readinessSnap?.ready ? 'status-pass' : 'status-fail'}>{readinessSnap?.ready ? 'PASS' : 'FAIL'}</span>
                  {readinessSnap?.checked_at ? ` · ${new Date(readinessSnap.checked_at).toLocaleString()}` : ''}
                </div>
              )}
              {readinessSummary && (
                <div className="mt-1 text-slate-400">
                  Trend (200): {readinessSummary.pass_count || 0}/{readinessSummary.total || 0} pass ({Math.round((readinessSummary.pass_rate || 0) * 100)}%)
                </div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <button onClick={() => void runReadinessDiagnosticsNow()} className={BTN_MUTED} disabled={runningReadiness}>
                {runningReadiness ? 'Running…' : 'Run All Readiness Diagnostics'}
              </button>
              <Link href="/live-control" className={BTN_MUTED}>Open Live Control</Link>
            </div>
          </section>

          <details className="card p-2">
            <summary className="cursor-pointer text-xs text-slate-400">Sections ({active})</summary>
            <nav className="mt-2 flex flex-wrap gap-2">
              {sections.map((s, idx) => (
                <button
                  key={s.id}
                  onClick={() => selectSection(s.id)}
                  title={`[${idx + 1}] ${s.label}`}
                  className={`btn ${active === s.id ? 'btn-primary' : 'btn-muted'}`}
                >
                  {idx + 1}. {s.label}
                </button>
              ))}
            </nav>
          </details>

          {menuOpen && (
            <nav className="card p-2 flex flex-wrap gap-2 md:hidden">
              {sections.map((s, idx) => (
                <button
                  key={s.id}
                  onClick={() => selectSection(s.id)}
                  className={`btn ${active === s.id ? 'btn-primary' : 'btn-muted'}`}
                >
                  {idx + 1}. {s.label}
                </button>
              ))}
            </nav>
          )}
        </>
      ) : (
        <section className="card p-2 flex items-center justify-between text-xs">
          <div className="text-slate-300">Focus mode active · {active}</div>
          <div className="flex items-center gap-2">
            <button onClick={() => setFocusMode(false)} className={BTN_MUTED}>Exit focus</button>
            <button onClick={() => void refreshNow()} className={BTN_PRIMARY}>Refresh</button>
          </div>
        </section>
      )}


      {active === 'overview' && (
        loadingCore ? <SkeletonGrid /> : (
          <section className="space-y-3 section-transition">
            <AgentFleetVisualizer />
            <section className="grid grid-cols-1 md:grid-cols-4 gap-3">
              <MetricCard label="Avg Index Move" value={`${avgIndexMove.toFixed(2)}%`} tone={Math.abs(avgIndexMove) > 1 ? 'warn' : 'default'} />
              <MetricCard
                label="Live Tick"
                value={tick ? `${tick.ticker} ${tick.price}` : 'Waiting…'}
                hint={tick ? `source: ${tick.source || 'unknown'}${tick.simulated ? ' (simulated)' : ''}` : undefined}
                tone={tick?.simulated ? 'warn' : 'default'}
              />
              <MetricCard label="Realized PnL" value={`$${Number(analytics?.summary?.realized_pnl || 0).toFixed(2)}`} tone={(analytics?.summary?.realized_pnl || 0) >= 0 ? 'good' : 'bad'} />
              <MetricCard label="Open Exposure" value={`$${Number(analytics?.summary?.open_exposure || 0).toFixed(2)}`} tone={(analytics?.summary?.open_exposure || 0) > 5000 ? 'warn' : 'default'} />
            </section>
            <section className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="card card-hover p-3">
                <h3 className="font-semibold mb-2">Major Indices</h3>
                {indices.map((i) => <div key={i.ticker} className="text-sm flex justify-between"><span>{i.ticker}</span><span>{i.price.toFixed(2)} ({i.change_pct.toFixed(2)}%)</span></div>)}
              </div>
              <div className="card card-hover p-3">
                <h3 className="font-semibold mb-2">Top Movers</h3>
                {movers.map((m) => <div key={m.ticker} className="text-sm flex justify-between"><span>{m.ticker}</span><span>{m.change_pct.toFixed(2)}%</span></div>)}
              </div>
              <div className="card card-hover p-3">
                <h3 className="font-semibold mb-2">Watchlist Signals</h3>
                {!watchSignals.length && <div className="text-sm text-slate-400">No signals yet.</div>}
                {watchSignals.map((s) => <div key={s.ticker} className="text-sm flex justify-between"><span>{s.ticker}</span><span>{s.action} ({Math.round((s.confidence || 0) * 100)}%)</span></div>)}
              </div>
            </section>
          </section>
        )
      )}

      {active === 'workspace' && (
        <section className="flex flex-col xl:flex-row gap-3 section-transition">
          <Sidebar
            tickers={watchlist}
            activeTicker={ticker}
            onSelect={setTicker}
            onAdd={async (t) => {
              const clean = (t || '').trim().toUpperCase()
              if (!/^[A-Z.]{1,6}$/.test(clean)) {
                pushToast('err', 'Ticker format invalid (use 1-6 letters)')
                return
              }
              const res = await addWatchlistTicker(USER_ID, clean)
              setWatchlist(res.items || [])
              pushToast('ok', `${clean} added to watchlist`)
            }}
            onRemove={async (t) => {
              const res = await removeWatchlistTicker(USER_ID, t)
              setWatchlist(res.items || [])
              if (ticker === t && res.items?.length) setTicker(res.items[0])
              pushToast('ok', `${t} removed from watchlist`)
            }}
          />
          <ChartPane ticker={ticker} onInspect={runAnalysis} />
          <ProbabilityDrawer probability={probability} signal={signal} loading={analysisLoading} timeframe={analysisTimeframe} />
        </section>
      )}

      {active === 'swarm' && (
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-3 section-transition">
          <div className="card card-hover p-3 lg:col-span-2">
            <h3 className="font-semibold mb-2">Swarm Run</h3>
            <div className="flex gap-2 mb-2 flex-wrap">
              <input value={swarmTicker} onChange={(e) => setSwarmTicker(e.target.value.toUpperCase())} className="bg-slate-900 border border-slate-700 rounded px-2 py-1" />
              <button onClick={runSwarmNow} className={BTN_PRIMARY}>Run Classic</button>
              <button onClick={runDeepSwarmNow} className={BTN_SUCCESS}>Run Deep MiroFish</button>
            </div>
            {showRawJson ? (
              <pre className="text-xs bg-slate-950/70 border border-slate-800 rounded p-2 overflow-auto max-h-[420px]">{JSON.stringify(swarmResult, null, 2)}</pre>
            ) : (
              <div className="text-sm text-slate-300">Run details hidden. Toggle <span className="font-semibold">JSON on</span> to inspect payload.</div>
            )}
          </div>
          <div className="card card-hover p-3">
            <h3 className="font-semibold mb-2">Quick Context</h3>
            <div className="text-sm">Ticker: {swarmTicker}</div>
            <div className="text-sm">MiroFish Bias: {mirofishSnap?.directional_bias || '--'}</div>
            <div className="text-sm">Consensus: {swarmResult?.consensus?.recommendation || '--'}</div>
            {deepSwarm && (
              <>
                <div className="mt-2 text-sm">Deep Bias: <span className="font-semibold">{deepSwarm.overall_bias}</span></div>
                <div className="text-sm">Deep Conf: {Math.round((deepSwarm.overall_confidence || 0) * 100)}%</div>
                <div className="text-sm">Alignment: {Math.round((deepSwarm.alignment_score || 0) * 100)}%</div>
              </>
            )}
          </div>
          {showRawJson && deepSwarm && (
            <div className="card card-hover p-3 lg:col-span-3">
              <h3 className="font-semibold mb-2">Deep Swarm Detail</h3>
              <pre className="text-xs bg-slate-950/70 border border-slate-800 rounded p-2 overflow-auto max-h-[320px]">{JSON.stringify(deepSwarm, null, 2)}</pre>
            </div>
          )}
        </section>
      )}

      {active === 'paper' && (
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-3 section-transition">
          <div className="card card-hover p-3 lg:col-span-2">
            <h3 className="font-semibold mb-2">Paper Execution</h3>
            <div className="flex flex-wrap gap-2 mb-2">
              <button onClick={submitQuickOrder} className={BTN_SUCCESS}>Submit Quick Order ({ticker})</button>
              <button onClick={setPaperMode} className={BTN_MUTED}>Set Paper Mode</button>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              {showRawJson ? (
                <>
                  <pre className="text-xs bg-slate-950/70 border border-slate-800 rounded p-2 overflow-auto max-h-[240px]">Validate: {JSON.stringify(orderCheck, null, 2)}</pre>
                  <pre className="text-xs bg-slate-950/70 border border-slate-800 rounded p-2 overflow-auto max-h-[240px]">Order: {JSON.stringify(orderResult, null, 2)}</pre>
                </>
              ) : (
                <div className="text-sm text-slate-300 md:col-span-2">Raw responses hidden. Enable JSON to inspect validate/order payloads.</div>
              )}
            </div>
          </div>
          <div className="card card-hover p-3 space-y-3">
            <div>
              <h3 className="font-semibold mb-2">Execution Analytics</h3>
              <div className="text-sm">Realized PnL: ${Number(analytics?.summary?.realized_pnl || 0).toFixed(2)}</div>
              <div className="text-sm">Open Exposure: ${Number(analytics?.summary?.open_exposure || 0).toFixed(2)}</div>
              <div className="text-sm">Fill Rate: {Math.round((analytics?.summary?.fill_rate || 0) * 100)}%</div>
              <div className="text-sm">Win Rate: {Math.round((analytics?.summary?.win_rate || 0) * 100)}%</div>
            </div>

            <div>
              <h3 className="font-semibold mb-2">Compliance Queue</h3>
              <div className="text-xs text-slate-400 mb-2">
                Open {complianceSummary?.open || 0} · Ack {complianceSummary?.acknowledged || 0} · Waived {complianceSummary?.waived || 0} · Remediated {complianceSummary?.remediated || 0}
              </div>
              {!complianceViolations.length && <div className="text-sm text-slate-400">No open compliance violations.</div>}
              <div className="space-y-2 max-h-[220px] overflow-auto">
                {complianceViolations.map((v) => (
                  <div key={v.id} className="border border-slate-700 rounded p-2">
                    <div className="text-xs font-semibold">#{v.id} · {v.rule_code}</div>
                    <div className="text-xs text-slate-400">{v.symbol || '--'} · {v.severity} · {v.status}</div>
                    <div className="text-xs mt-1 text-slate-400">{v.details?.hard_reasons?.join(', ') || v.details?.adapter_reason || v.policy_name}</div>
                    <button onClick={() => void acknowledgeViolation(v.id)} className={`${BTN_MUTED} mt-2`}>Acknowledge</button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      )}

      {active === 'strategy' && (
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-3 section-transition">
          <div className="card card-hover p-3">
            <h3 className="font-semibold mb-2">Strategy Lab Quick Run</h3>
            <button onClick={runBacktestNow} className={`${BTN_SUCCESS} mb-2`}>Run Backtest</button>
            <p className="text-xs text-slate-400">Uses active ticker and selected chart timeframe.</p>
          </div>
          <JsonPanel title="Backtest Result" value={showRawJson ? backtestResult : null} />
        </section>
      )}

      {active === 'training' && (
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-3 section-transition">
          <div className="card card-hover p-3">
            <h3 className="font-semibold mb-2">Training / Evaluation</h3>
            <button onClick={runTrainingEval} className={`${BTN_PRIMARY} mb-2`}>Run Training + Daily Eval</button>
            <p className="text-xs text-slate-400">Queues training worker task and runs daily calibration endpoint.</p>
          </div>
          <div className="space-y-3">
            <JsonPanel title="Training" value={showRawJson ? trainingResult : null} />
            <JsonPanel title="Evaluation" value={showRawJson ? evalResult : null} />
          </div>
        </section>
      )}

      {active === 'settings' && (
        <section className="grid grid-cols-1 lg:grid-cols-2 gap-3 section-transition">
          <div className="card card-hover p-3">
            <h3 className="font-semibold mb-2">MiroFish Integration</h3>
            <div className="text-sm">Configured: {String(mirofishStatus?.configured ?? false)}</div>
            <div className="text-sm">Mode: {mirofishStatus?.mode || '--'}</div>
            <div className="text-sm">Simulation: {mirofishSnap?.simulation_id || mirofishStatus?.simulation_id || '--'}</div>
            <div className="text-xs text-slate-400 mt-2 break-all">Summary: {mirofishSnap?.scenario_summary || '--'}</div>
          </div>
          <div className="card card-hover p-3">
            <h3 className="font-semibold mb-2">Focus Deep Swarm (runtime)</h3>
            <div className="text-xs text-slate-400 mb-2">Comma-separated tickers (editable at runtime, no restart required)</div>
            <input value={focusInput} onChange={(e) => setFocusInput(e.target.value.toUpperCase())} className="w-full bg-slate-900 border border-slate-700 rounded px-2 py-1 mb-2" />
            <div className="flex gap-2 mb-2 flex-wrap">
              <button className={BTN_PRIMARY} onClick={() => void saveFocusConfig()}>Save Focus</button>
              <button className={BTN_MUTED} onClick={() => void runFocusCycleNow()}>Run Deep Cycle Now</button>
            </div>
            <div className="text-xs text-slate-400">Enabled: {String(focusSwarm?.enabled ?? true)} · Interval: {focusSwarm?.interval_sec ?? 240}s · Runs: {focusSwarm?.runs ?? 0}</div>
            {focusSwarm?.results && (
              <div className="mt-2 space-y-1">
                {Object.entries(focusSwarm.results).slice(0, 6).map(([sym, r]: any) => (
                  <div key={sym} className="text-xs flex justify-between"><span>{sym}</span><span>{r?.overall_bias || '--'} · {Math.round((r?.overall_confidence || 0) * 100)}%</span></div>
                ))}
              </div>
            )}
          </div>
          <div className="card card-hover p-3 lg:col-span-2">
            <h3 className="font-semibold mb-2">Recent Journal</h3>
            {!journal.length && <div className="text-sm text-slate-400">No recent journal entries.</div>}
            {journal.map((j) => <div key={j.id} className="text-sm">#{j.id} {j.ticker} · {j?.tags?.state || 'submitted'}</div>)}
          </div>
        </section>
      )}

      <style jsx global>{`
        .tb-compact .card { border-radius: 10px; }
        .tb-compact .card.p-3 { padding: 0.55rem 0.65rem; }
        .tb-compact .card.p-2 { padding: 0.4rem 0.55rem; }
        .tb-compact .text-2xl { font-size: 1.25rem; line-height: 1.6rem; }
      `}</style>
    </main>
  )
}
