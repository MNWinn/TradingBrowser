import { useEffect, useRef, useState } from 'react'

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'

const DEV_ADMIN_TOKEN = process.env.NEXT_PUBLIC_ADMIN_API_TOKEN || 'admin-dev-token'
const DEV_TRADER_TOKEN = process.env.NEXT_PUBLIC_TRADER_API_TOKEN || 'trader-dev-token'
const DEV_ANALYST_TOKEN = process.env.NEXT_PUBLIC_ANALYST_API_TOKEN || 'analyst-dev-token'

type Role = 'admin' | 'trader' | 'analyst'

function authHeaders(role?: Role): HeadersInit {
  if (!role) return {}
  const token = role === 'admin' ? DEV_ADMIN_TOKEN : role === 'trader' ? DEV_TRADER_TOKEN : DEV_ANALYST_TOKEN
  return { Authorization: `Bearer ${token}` }
}

async function asJson(res: Response) {
  const body = await res.json()
  if (!res.ok) {
    const detail = body?.detail
    const msg = typeof detail === 'string' ? detail : detail?.message || body?.message || 'Request failed'
    throw new Error(msg)
  }
  return body
}

export async function getSignal(ticker: string) {
  const res = await fetch(`${API_BASE}/signals/${ticker}`, { cache: 'no-store' })
  return asJson(res)
}

export async function getExecutionMode() {
  const res = await fetch(`${API_BASE}/execution/mode`, { cache: 'no-store' })
  return asJson(res)
}

export async function updateExecutionMode(payload: {
  mode: 'research' | 'paper' | 'live'
  live_trading_enabled: boolean
  confirmation?: string
  force_enable_live?: boolean
  changed_by?: string
}) {
  const res = await fetch(`${API_BASE}/execution/mode`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders('admin') },
    body: JSON.stringify(payload),
  })
  return asJson(res)
}

export async function getLiveReadiness() {
  const res = await fetch(`${API_BASE}/execution/live-readiness`, {
    cache: 'no-store',
    headers: { ...authHeaders('analyst') },
  })
  return asJson(res)
}

export async function getReadinessHistory(limit = 20) {
  const res = await fetch(`${API_BASE}/execution/live-readiness/history?limit=${limit}`, {
    cache: 'no-store',
    headers: { ...authHeaders('analyst') },
  })
  return asJson(res)
}

export async function getReadinessSummary(limit = 200) {
  const res = await fetch(`${API_BASE}/execution/live-readiness/summary?limit=${limit}`, {
    cache: 'no-store',
    headers: { ...authHeaders('analyst') },
  })
  return asJson(res)
}

export async function validateExecution(payload: {
  symbol: string
  side: 'buy' | 'sell'
  qty?: number
  notional?: number
  type?: 'market' | 'limit' | 'stop' | 'stop_limit'
  stop_loss?: number
  rationale?: Record<string, any>
  recommendation?: Record<string, any>
  idempotency_key?: string
}) {
  const res = await fetch(`${API_BASE}/execution/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return asJson(res)
}

export async function submitOrder(payload: {
  symbol: string
  side: 'buy' | 'sell'
  qty?: number
  notional?: number
  type?: 'market' | 'limit' | 'stop' | 'stop_limit'
  stop_loss?: number
  rationale?: Record<string, any>
  recommendation?: Record<string, any>
  idempotency_key?: string
}) {
  const res = await fetch(`${API_BASE}/execution/order`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders('trader') },
    body: JSON.stringify(payload),
  })
  return asJson(res)
}

export async function submitOrderFill(payload: {
  broker_order_id: string
  state?: 'filled' | 'partial' | 'closed' | 'cancelled' | 'rejected'
  fill_price?: number
  fill_qty?: number
  pnl?: number
  notes?: string
  idempotency_key?: string
}) {
  const res = await fetch(`${API_BASE}/execution/order/fill`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders('trader') },
    body: JSON.stringify(payload),
  })
  return asJson(res)
}

export async function getWatchlist(userId: string) {
  const res = await fetch(`${API_BASE}/watchlist/${userId}`, { cache: 'no-store' })
  return asJson(res)
}

export async function addWatchlistTicker(userId: string, ticker: string) {
  const res = await fetch(`${API_BASE}/watchlist/${userId}/${ticker}`, { method: 'POST' })
  return asJson(res)
}

export async function removeWatchlistTicker(userId: string, ticker: string) {
  const res = await fetch(`${API_BASE}/watchlist/${userId}/${ticker}`, { method: 'DELETE' })
  return asJson(res)
}

export async function getQuote(ticker: string) {
  const res = await fetch(`${API_BASE}/market/quote/${ticker}`, { cache: 'no-store' })
  return asJson(res)
}

export async function getBars(ticker: string, timeframe = '5m', limit = 120) {
  const res = await fetch(`${API_BASE}/market/bars/${ticker}?timeframe=${timeframe}&limit=${limit}`, { cache: 'no-store' })
  return asJson(res)
}

export async function getProbability(ticker: string, timeframe = '5m') {
  const res = await fetch(`${API_BASE}/chart/probability/${ticker}?timeframe=${timeframe}`, { cache: 'no-store' })
  return asJson(res)
}

export async function runSwarm(ticker: string) {
  const res = await fetch(`${API_BASE}/swarm/run/${ticker}`, { method: 'POST' })
  return asJson(res)
}

export async function getSwarmResults(ticker: string) {
  const res = await fetch(`${API_BASE}/swarm/results/${ticker}`, { cache: 'no-store' })
  return asJson(res)
}

export async function getSwarmPerformance() {
  const res = await fetch(`${API_BASE}/swarm/performance`, { cache: 'no-store' })
  return asJson(res)
}

export async function listJournal(limit = 100) {
  const res = await fetch(`${API_BASE}/journal?limit=${limit}`, { cache: 'no-store' })
  return asJson(res)
}

export async function updateJournalOutcome(entryId: number, payload: {
  state: string
  fill_price?: number
  fill_qty?: number
  pnl?: number
  notes?: string
}) {
  const res = await fetch(`${API_BASE}/journal/${entryId}/outcome`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders('trader') },
    body: JSON.stringify(payload),
  })
  return asJson(res)
}

export async function getMirofishStatus() {
  const res = await fetch(`${API_BASE}/mirofish/status`, { cache: 'no-store' })
  return asJson(res)
}

export async function getMirofishPredict(payload: Record<string, any>) {
  const res = await fetch(`${API_BASE}/mirofish/predict`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return asJson(res)
}

export async function getMirofishDeepSwarm(payload: Record<string, any>) {
  const res = await fetch(`${API_BASE}/mirofish/deep-swarm`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return asJson(res)
}

export async function getMirofishDiagnostics(payload: Record<string, any>) {
  const res = await fetch(`${API_BASE}/mirofish/diagnostics`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return asJson(res)
}

export async function runAllReadinessDiagnostics() {
  const [readiness, mirofish] = await Promise.all([
    getLiveReadiness(),
    getMirofishDiagnostics({}),
  ])

  if (!readiness?.mirofish && mirofish) {
    return { ...readiness, mirofish }
  }

  return readiness
}

export async function getSwarmFocus() {
  const res = await fetch(`${API_BASE}/swarm/focus`)
  return asJson(res)
}

export async function updateSwarmFocus(payload: Record<string, any>) {
  const res = await fetch(`${API_BASE}/swarm/focus`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return asJson(res)
}

export async function runSwarmFocusNow() {
  const res = await fetch(`${API_BASE}/swarm/focus/run-cycle`, { method: 'POST' })
  return asJson(res)
}

export async function runStrategyBacktest(payload: Record<string, any>) {
  const res = await fetch(`${API_BASE}/strategies/backtest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
  return asJson(res)
}

export async function runTrainingJob() {
  const res = await fetch(`${API_BASE}/training/run`, {
    method: 'POST',
    headers: { ...authHeaders('admin') },
  })
  return asJson(res)
}

export async function runDailyEvaluation() {
  const res = await fetch(`${API_BASE}/evaluation/daily`, {
    method: 'POST',
  })
  return asJson(res)
}

export async function getExecutionAnalytics(limit = 100) {
  const res = await fetch(`${API_BASE}/execution/analytics?limit=${limit}`, {
    cache: 'no-store',
    headers: { ...authHeaders('analyst') },
  })
  return asJson(res)
}

export async function getAuditLogs(limit = 100) {
  const res = await fetch(`${API_BASE}/audit/logs?limit=${limit}`, { cache: 'no-store' })
  return asJson(res)
}

export async function getComplianceViolations(
  filters?: {
    status?: 'open' | 'acknowledged' | 'waived' | 'remediated'
    severity?: 'low' | 'medium' | 'high' | 'critical'
    symbol?: string
    policy_name?: string
    assignee?: string
    sort?: 'newest' | 'oldest' | 'severity'
  },
  limit = 100
) {
  const qs = new URLSearchParams()
  qs.set('limit', String(limit))
  if (filters?.status) qs.set('status', filters.status)
  if (filters?.severity) qs.set('severity', filters.severity)
  if (filters?.symbol) qs.set('symbol', filters.symbol.toUpperCase())
  if (filters?.policy_name) qs.set('policy_name', filters.policy_name)
  if (filters?.assignee) qs.set('assignee', filters.assignee)
  if (filters?.sort) qs.set('sort', filters.sort)

  const res = await fetch(`${API_BASE}/compliance/violations?${qs.toString()}`, {
    cache: 'no-store',
    headers: { ...authHeaders('analyst') },
  })
  return asJson(res)
}

export async function getComplianceSummary() {
  const res = await fetch(`${API_BASE}/compliance/summary`, {
    cache: 'no-store',
    headers: { ...authHeaders('analyst') },
  })
  return asJson(res)
}

export async function getComplianceAnalytics() {
  const res = await fetch(`${API_BASE}/compliance/analytics`, {
    cache: 'no-store',
    headers: { ...authHeaders('analyst') },
  })
  return asJson(res)
}

export async function updateComplianceViolation(
  violationId: number,
  payload: {
    status: 'open' | 'acknowledged' | 'waived' | 'remediated'
    acknowledged_by?: string
    assignee?: string
    resolution_notes?: string
  }
) {
  const res = await fetch(`${API_BASE}/compliance/violations/${violationId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders('trader') },
    body: JSON.stringify(payload),
  })
  return asJson(res)
}

export async function bulkUpdateComplianceViolations(payload: {
  ids: number[]
  status: 'open' | 'acknowledged' | 'waived' | 'remediated'
  acknowledged_by?: string
  assignee?: string
  resolution_notes?: string
}) {
  const res = await fetch(`${API_BASE}/compliance/violations-bulk`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders('trader') },
    body: JSON.stringify(payload),
  })
  return asJson(res)
}

export async function getComplianceViolationTimeline(violationId: number, limit = 100) {
  const res = await fetch(`${API_BASE}/compliance/violations/${violationId}/timeline?limit=${limit}`, {
    cache: 'no-store',
    headers: { ...authHeaders('analyst') },
  })
  return asJson(res)
}

export async function exportComplianceCsv(filters?: {
  status?: 'open' | 'acknowledged' | 'waived' | 'remediated'
  severity?: 'low' | 'medium' | 'high' | 'critical'
  symbol?: string
  policy_name?: string
  assignee?: string
  sort?: 'newest' | 'oldest' | 'severity'
}) {
  const qs = new URLSearchParams()
  if (filters?.status) qs.set('status', filters.status)
  if (filters?.severity) qs.set('severity', filters.severity)
  if (filters?.symbol) qs.set('symbol', filters.symbol.toUpperCase())
  if (filters?.policy_name) qs.set('policy_name', filters.policy_name)
  if (filters?.assignee) qs.set('assignee', filters.assignee)
  if (filters?.sort) qs.set('sort', filters.sort)

  const res = await fetch(`${API_BASE}/compliance/violations/export.csv?${qs.toString()}`, {
    cache: 'no-store',
    headers: { ...authHeaders('analyst') },
  })
  if (!res.ok) {
    const maybeJson = await res.json().catch(() => null)
    throw new Error(maybeJson?.detail || 'CSV export failed')
  }
  return res.text()
}

// ==================== Agent Types ====================

export interface AgentHealth {
  status?: 'healthy' | 'degraded' | 'unhealthy' | 'unknown'
  score?: number
  uptime?: string
  successRate?: number
  lastErrorAt?: string
  checks?: Array<{
    name: string
    ok: boolean
    detail?: string
  }>
}

export interface AgentPerformance {
  tasksCompleted?: number
  tasksFailed?: number
  avgTaskDuration?: number
  metrics?: Record<string, any>
}

export interface Agent {
  id: string
  name: string
  type?: string
  version?: string
  status: 'running' | 'idle' | 'error' | 'paused' | 'unknown'
  health?: AgentHealth
  currentTask?: string
  ticker?: string
  taskStartedAt?: string
  lastActivityAt?: string
  createdAt?: string
  performance?: AgentPerformance
  metadata?: Record<string, any>
}

export interface AgentLog {
  timestamp: string
  level: 'debug' | 'info' | 'warn' | 'error'
  message: string
  metadata?: Record<string, any>
}

export interface AgentOutput {
  timestamp: string
  type?: string
  data: any
}

// ==================== Agent API ====================

export async function getAgents(): Promise<{ agents: Agent[] }> {
  const res = await fetch(`${API_BASE}/agents`, {
    cache: 'no-store',
    headers: { ...authHeaders('analyst') },
  })
  return asJson(res)
}

export async function getAgent(id: string): Promise<Agent> {
  const res = await fetch(`${API_BASE}/agents/${id}`, {
    cache: 'no-store',
    headers: { ...authHeaders('analyst') },
  })
  return asJson(res)
}

export async function getAgentLogs(id: string, limit = 100): Promise<{ logs: AgentLog[] }> {
  const res = await fetch(`${API_BASE}/agents/${id}/logs?limit=${limit}`, {
    cache: 'no-store',
    headers: { ...authHeaders('analyst') },
  })
  return asJson(res)
}

export async function getAgentOutputs(id: string, limit = 50): Promise<{ outputs: AgentOutput[] }> {
  const res = await fetch(`${API_BASE}/agents/${id}/outputs?limit=${limit}`, {
    cache: 'no-store',
    headers: { ...authHeaders('analyst') },
  })
  return asJson(res)
}

// ==================== WebSocket Helper ====================

export interface WebSocketMessage {
  type: string
  payload: any
  timestamp: string
}

type WebSocketEventHandler = (message: WebSocketMessage) => void

export interface AgentWebSocketConnection {
  connect: () => void
  disconnect: () => void
  subscribe: (eventType: string, handler: WebSocketEventHandler) => () => void
  isConnected: () => boolean
}

export function createAgentWebSocket(
  agentId?: string,
  options?: {
    onConnect?: () => void
    onDisconnect?: () => void
    onError?: (error: Event) => void
    reconnectInterval?: number
    maxReconnectAttempts?: number
  }
): AgentWebSocketConnection {
  let ws: WebSocket | null = null
  let reconnectAttempts = 0
  let reconnectTimer: number | null = null
  const handlers = new Map<string, Set<WebSocketEventHandler>>()
  const allHandlers = new Set<WebSocketEventHandler>()

  const {
    onConnect,
    onDisconnect,
    onError,
    reconnectInterval = 3000,
    maxReconnectAttempts = 5,
  } = options || {}

  // Build WebSocket URL
  const getWsUrl = () => {
    const baseUrl = API_BASE.replace(/^http/, 'ws')
    return agentId ? `${baseUrl}/agents/${agentId}/ws` : `${baseUrl}/agents/ws`
  }

  const handleMessage = (event: MessageEvent) => {
    try {
      const message: WebSocketMessage = JSON.parse(event.data)
      
      // Notify type-specific handlers
      const typeHandlers = handlers.get(message.type)
      if (typeHandlers) {
        typeHandlers.forEach((handler) => {
          try {
            handler(message)
          } catch (e) {
            console.error('WebSocket handler error:', e)
          }
        })
      }
      
      // Notify all handlers
      allHandlers.forEach((handler) => {
        try {
          handler(message)
        } catch (e) {
          console.error('WebSocket handler error:', e)
        }
      })
    } catch (e) {
      console.error('Failed to parse WebSocket message:', e)
    }
  }

  const connect = () => {
    if (ws?.readyState === WebSocket.OPEN) return

    try {
      ws = new WebSocket(getWsUrl())

      ws.onopen = () => {
        reconnectAttempts = 0
        onConnect?.()
      }

      ws.onclose = () => {
        onDisconnect?.()
        
        // Attempt reconnection
        if (reconnectAttempts < maxReconnectAttempts) {
          reconnectAttempts++
          reconnectTimer = window.setTimeout(() => {
            console.log(`Reconnecting... attempt ${reconnectAttempts}`)
            connect()
          }, reconnectInterval)
        }
      }

      ws.onerror = (error) => {
        onError?.(error)
      }

      ws.onmessage = handleMessage
    } catch (e) {
      console.error('Failed to create WebSocket connection:', e)
      onError?.(e as Event)
    }
  }

  const disconnect = () => {
    if (reconnectTimer) {
      window.clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    reconnectAttempts = maxReconnectAttempts // Prevent reconnection
    ws?.close()
    ws = null
  }

  const subscribe = (eventType: string, handler: WebSocketEventHandler) => {
    if (!handlers.has(eventType)) {
      handlers.set(eventType, new Set())
    }
    handlers.get(eventType)!.add(handler)

    // Return unsubscribe function
    return () => {
      handlers.get(eventType)?.delete(handler)
    }
  }

  const isConnected = () => ws?.readyState === WebSocket.OPEN

  return {
    connect,
    disconnect,
    subscribe,
    isConnected,
  }
}

// Hook-friendly WebSocket hook factory
export function useAgentWebSocket(
  agentId?: string,
  eventTypes?: string[],
  onMessage?: (message: WebSocketMessage) => void
) {
  const [isConnected, setIsConnected] = useState(false)
  const connectionRef = useRef<AgentWebSocketConnection | null>(null)
  const unsubscribersRef = useRef<(() => void)[]>([])

  useEffect(() => {
    if (!agentId) return

    connectionRef.current = createAgentWebSocket(agentId, {
      onConnect: () => setIsConnected(true),
      onDisconnect: () => setIsConnected(false),
    })

    // Subscribe to specific event types
    if (eventTypes && onMessage) {
      eventTypes.forEach((eventType) => {
        const unsub = connectionRef.current!.subscribe(eventType, onMessage)
        unsubscribersRef.current.push(unsub)
      })
    }

    connectionRef.current.connect()

    return () => {
      unsubscribersRef.current.forEach((unsub) => unsub())
      unsubscribersRef.current = []
      connectionRef.current?.disconnect()
    }
  }, [agentId, eventTypes?.join(','), onMessage])

  return { isConnected, connection: connectionRef.current }
}
