'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import {
  getAgent,
  getAgentLogs,
  getAgentOutputs,
  type Agent,
  type AgentLog,
  type AgentOutput,
} from '@/lib/api'
import { AgentHealthBadge } from './AgentHealthBadge'

interface AgentDetailPanelProps {
  agentId: string | null
  refreshInterval?: number
}

type Tab = 'overview' | 'logs' | 'outputs' | 'performance'

export function AgentDetailPanel({
  agentId,
  refreshInterval = 3000,
}: AgentDetailPanelProps) {
  const [agent, setAgent] = useState<Agent | null>(null)
  const [logs, setLogs] = useState<AgentLog[]>([])
  const [outputs, setOutputs] = useState<AgentOutput[]>([])
  const [activeTab, setActiveTab] = useState<Tab>('overview')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const logsEndRef = useRef<HTMLDivElement>(null)

  const fetchAgentData = useCallback(async () => {
    if (!agentId) return

    setLoading(true)
    try {
      const [agentData, logsData, outputsData] = await Promise.all([
        getAgent(agentId),
        activeTab === 'logs' ? getAgentLogs(agentId) : Promise.resolve({ logs: [] }),
        activeTab === 'outputs' ? getAgentOutputs(agentId) : Promise.resolve({ outputs: [] }),
      ])

      setAgent(agentData)
      if (activeTab === 'logs') setLogs(logsData.logs || [])
      if (activeTab === 'outputs') setOutputs(outputsData.outputs || [])
      setError(null)
    } catch (e: any) {
      setError(e?.message || 'Failed to fetch agent data')
    } finally {
      setLoading(false)
    }
  }, [agentId, activeTab])

  useEffect(() => {
    if (!agentId) {
      setAgent(null)
      setLogs([])
      setOutputs([])
      return
    }

    void fetchAgentData()
    const interval = window.setInterval(fetchAgentData, refreshInterval)
    return () => window.clearInterval(interval)
  }, [fetchAgentData, agentId, refreshInterval])

  // Auto-scroll logs to bottom
  useEffect(() => {
    if (activeTab === 'logs' && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, activeTab])

  const getStatusColor = (status: Agent['status']) => {
    switch (status) {
      case 'running':
        return 'bg-emerald-100 text-emerald-800 border-emerald-200'
      case 'idle':
        return 'bg-neutral-100 text-neutral-700 border-neutral-200'
      case 'error':
        return 'bg-red-100 text-red-800 border-red-200'
      case 'paused':
        return 'bg-amber-100 text-amber-800 border-amber-200'
      default:
        return 'bg-neutral-100 text-neutral-600 border-neutral-200'
    }
  }

  const getLogLevelColor = (level: AgentLog['level']) => {
    switch (level) {
      case 'error':
        return 'text-red-700 bg-red-50'
      case 'warn':
        return 'text-amber-700 bg-amber-50'
      case 'debug':
        return 'text-neutral-500 bg-neutral-50'
      default:
        return 'text-neutral-700'
    }
  }

  if (!agentId) {
    return (
      <div className="card p-4 h-full min-h-[400px] flex items-center justify-center">
        <div className="text-center text-neutral-500">
          <div className="text-sm">Select an agent to view details</div>
        </div>
      </div>
    )
  }

  if (loading && !agent) {
    return (
      <div className="card p-4 h-full min-h-[400px] flex items-center justify-center">
        <div className="text-sm text-neutral-500">Loading agent details…</div>
      </div>
    )
  }

  if (error && !agent) {
    return (
      <div className="card p-4 h-full min-h-[400px] flex items-center justify-center">
        <div className="text-sm text-red-700">{error}</div>
      </div>
    )
  }

  if (!agent) {
    return (
      <div className="card p-4 h-full min-h-[400px] flex items-center justify-center">
        <div className="text-sm text-neutral-500">Agent not found</div>
      </div>
    )
  }

  return (
    <div className="card p-4 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-start justify-between mb-4 pb-4 border-b border-neutral-200">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <h3 className="font-semibold text-lg">{agent.name}</h3>
            <span
              className={`px-2 py-0.5 rounded text-xs font-medium border ${getStatusColor(
                agent.status
              )}`}
            >
              {agent.status}
            </span>
          </div>
          <div className="text-xs text-neutral-400">{agent.id}</div>
        </div>
        <AgentHealthBadge health={agent.health} showLabel size="lg" />
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-4 border-b border-neutral-200">
        {(['overview', 'logs', 'outputs', 'performance'] as Tab[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-3 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab
                ? 'border-black text-black'
                : 'border-transparent text-neutral-500 hover:text-neutral-700'
            }`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto min-h-[300px]">
        {activeTab === 'overview' && (
          <div className="space-y-4">
            {/* Current Task */}
            <div className="bg-neutral-50 rounded-lg p-3">
              <div className="text-xs font-medium text-neutral-500 uppercase mb-1">
                Current Task
              </div>
              <div className="text-sm">
                {agent.currentTask || 'No active task'}
              </div>
              {agent.taskStartedAt && (
                <div className="text-xs text-neutral-400 mt-1">
                  Started: {new Date(agent.taskStartedAt).toLocaleString()}
                </div>
              )}
            </div>

            {/* Ticker */}
            {agent.ticker && (
              <div className="bg-neutral-50 rounded-lg p-3">
                <div className="text-xs font-medium text-neutral-500 uppercase mb-1">
                  Active Ticker
                </div>
                <div className="text-lg font-semibold">{agent.ticker}</div>
              </div>
            )}

            {/* Metadata */}
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-neutral-50 rounded-lg p-3">
                <div className="text-xs font-medium text-neutral-500 uppercase mb-1">
                  Type
                </div>
                <div className="text-sm">{agent.type || 'Unknown'}</div>
              </div>
              <div className="bg-neutral-50 rounded-lg p-3">
                <div className="text-xs font-medium text-neutral-500 uppercase mb-1">
                  Version
                </div>
                <div className="text-sm">{agent.version || 'N/A'}</div>
              </div>
            </div>

            {/* Health Details */}
            <div className="bg-neutral-50 rounded-lg p-3">
              <div className="text-xs font-medium text-neutral-500 uppercase mb-2">
                Health Details
              </div>
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-neutral-600">Uptime</span>
                  <span>{agent.health?.uptime || '--'}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-neutral-600">Success Rate</span>
                  <span>{agent.health?.successRate ? `${Math.round(agent.health.successRate * 100)}%` : '--'}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-neutral-600">Last Error</span>
                  <span className="text-neutral-400">
                    {agent.health?.lastErrorAt
                      ? new Date(agent.health.lastErrorAt).toLocaleString()
                      : 'None'}
                  </span>
                </div>
              </div>
            </div>

            {/* Timestamps */}
            <div className="text-xs text-neutral-400 space-y-1">
              <div>Created: {agent.createdAt ? new Date(agent.createdAt).toLocaleString() : '--'}</div>
              <div>Last Activity: {agent.lastActivityAt ? new Date(agent.lastActivityAt).toLocaleString() : '--'}</div>
            </div>
          </div>
        )}

        {activeTab === 'logs' && (
          <div className="space-y-2">
            {logs.length === 0 ? (
              <div className="text-center py-8 text-neutral-500 text-sm">
                No logs available
              </div>
            ) : (
              <div className="space-y-1 font-mono text-xs">
                {logs.map((log, idx) => (
                  <div
                    key={idx}
                    className={`p-2 rounded ${getLogLevelColor(log.level)}`}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-neutral-400">
                        {new Date(log.timestamp).toLocaleTimeString()}
                      </span>
                      <span
                        className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-bold ${
                          log.level === 'error'
                            ? 'bg-red-200 text-red-800'
                            : log.level === 'warn'
                            ? 'bg-amber-200 text-amber-800'
                            : log.level === 'debug'
                            ? 'bg-neutral-200 text-neutral-700'
                            : 'bg-neutral-200 text-neutral-700'
                        }`}
                      >
                        {log.level}
                      </span>
                    </div>
                    <div className="whitespace-pre-wrap break-words">{log.message}</div>
                    {log.metadata && (
                      <details className="mt-1">
                        <summary className="cursor-pointer text-neutral-400 hover:text-neutral-600">
                          Metadata
                        </summary>
                        <pre className="mt-1 p-2 bg-white/50 rounded overflow-auto max-h-40">
                          {JSON.stringify(log.metadata, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                ))}
                <div ref={logsEndRef} />
              </div>
            )}
          </div>
        )}

        {activeTab === 'outputs' && (
          <div className="space-y-3">
            {outputs.length === 0 ? (
              <div className="text-center py-8 text-neutral-500 text-sm">
                No outputs available
              </div>
            ) : (
              outputs.map((output, idx) => (
                <div key={idx} className="bg-neutral-50 rounded-lg p-3">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs font-medium text-neutral-500">
                      {new Date(output.timestamp).toLocaleString()}
                    </span>
                    {output.type && (
                      <span className="px-2 py-0.5 bg-neutral-200 rounded text-xs">
                        {output.type}
                      </span>
                    )}
                  </div>
                  <pre className="text-xs overflow-auto max-h-60 bg-white p-2 rounded border border-neutral-200">
                    {JSON.stringify(output.data, null, 2)}
                  </pre>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'performance' && (
          <div className="space-y-4">
            {agent.performance ? (
              <>
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-neutral-50 rounded-lg p-3">
                    <div className="text-xs font-medium text-neutral-500 uppercase mb-1">
                      Tasks Completed
                    </div>
                    <div className="text-2xl font-semibold">
                      {agent.performance.tasksCompleted || 0}
                    </div>
                  </div>
                  <div className="bg-neutral-50 rounded-lg p-3">
                    <div className="text-xs font-medium text-neutral-500 uppercase mb-1">
                      Tasks Failed
                    </div>
                    <div className="text-2xl font-semibold">
                      {agent.performance.tasksFailed || 0}
                    </div>
                  </div>
                </div>

                <div className="bg-neutral-50 rounded-lg p-3">
                  <div className="text-xs font-medium text-neutral-500 uppercase mb-2">
                    Average Task Duration
                  </div>
                  <div className="text-lg">
                    {agent.performance.avgTaskDuration
                      ? `${Math.round(agent.performance.avgTaskDuration)}ms`
                      : '--'}
                  </div>
                </div>

                {agent.performance.metrics && (
                  <div className="bg-neutral-50 rounded-lg p-3">
                    <div className="text-xs font-medium text-neutral-500 uppercase mb-2">
                      Custom Metrics
                    </div>
                    <pre className="text-xs overflow-auto max-h-40 bg-white p-2 rounded border border-neutral-200">
                      {JSON.stringify(agent.performance.metrics, null, 2)}
                    </pre>
                  </div>
                )}
              </>
            ) : (
              <div className="text-center py-8 text-neutral-500 text-sm">
                No performance data available
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
