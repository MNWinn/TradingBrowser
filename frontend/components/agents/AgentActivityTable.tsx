'use client'

import { useEffect, useState, useCallback } from 'react'
import { getAgents, type Agent } from '@/lib/api'
import { AgentHealthBadge } from './AgentHealthBadge'

interface AgentActivityTableProps {
  onSelectAgent?: (agentId: string) => void
  selectedAgentId?: string | null
  refreshInterval?: number
}

export function AgentActivityTable({
  onSelectAgent,
  selectedAgentId,
  refreshInterval = 5000,
}: AgentActivityTableProps) {
  const [agents, setAgents] = useState<Agent[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)

  const fetchAgents = useCallback(async () => {
    try {
      const data = await getAgents()
      setAgents(data.agents || [])
      setLastUpdated(new Date())
      setError(null)
    } catch (e: any) {
      setError(e?.message || 'Failed to fetch agents')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchAgents()
    const interval = window.setInterval(fetchAgents, refreshInterval)
    return () => window.clearInterval(interval)
  }, [fetchAgents, refreshInterval])

  const getStatusColor = (status: Agent['status']) => {
    switch (status) {
      case 'running':
        return 'text-emerald-700 font-medium'
      case 'idle':
        return 'text-neutral-600'
      case 'error':
        return 'text-red-700 font-medium'
      case 'paused':
        return 'text-amber-700'
      default:
        return 'text-neutral-500'
    }
  }

  const formatDuration = (startedAt?: string) => {
    if (!startedAt) return '--'
    const start = new Date(startedAt)
    const now = new Date()
    const diff = Math.floor((now.getTime() - start.getTime()) / 1000)
    if (diff < 60) return `${diff}s`
    if (diff < 3600) return `${Math.floor(diff / 60)}m`
    return `${Math.floor(diff / 3600)}h ${Math.floor((diff % 3600) / 60)}m`
  }

  if (loading && agents.length === 0) {
    return (
      <div className="card p-4">
        <div className="flex items-center justify-center py-8">
          <div className="text-sm text-neutral-500">Loading agents…</div>
        </div>
      </div>
    )
  }

  if (error && agents.length === 0) {
    return (
      <div className="card p-4">
        <div className="flex items-center justify-center py-8">
          <div className="text-sm text-red-700">{error}</div>
        </div>
      </div>
    )
  }

  return (
    <div className="card p-4">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="font-semibold text-lg">Agent Activity</h3>
          <p className="text-sm text-neutral-500">
            {agents.length} agent{agents.length !== 1 ? 's' : ''} · 
            {lastUpdated ? ` Updated ${lastUpdated.toLocaleTimeString()}` : ''}
          </p>
        </div>
        <button onClick={fetchAgents} className="btn btn-muted text-xs">
          Refresh
        </button>
      </div>

      <div className="overflow-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left border-b border-neutral-200">
              <th className="py-2 px-2 font-medium text-neutral-600">Agent</th>
              <th className="py-2 px-2 font-medium text-neutral-600">Status</th>
              <th className="py-2 px-2 font-medium text-neutral-600">Health</th>
              <th className="py-2 px-2 font-medium text-neutral-600">Current Task</th>
              <th className="py-2 px-2 font-medium text-neutral-600">Ticker</th>
              <th className="py-2 px-2 font-medium text-neutral-600">Duration</th>
              <th className="py-2 px-2 font-medium text-neutral-600">Last Activity</th>
            </tr>
          </thead>
          <tbody>
            {agents.map((agent) => (
              <tr
                key={agent.id}
                className={`border-b border-neutral-100 cursor-pointer transition-colors ${
                  selectedAgentId === agent.id
                    ? 'bg-neutral-100'
                    : 'hover:bg-neutral-50'
                }`}
                onClick={() => onSelectAgent?.(agent.id)}
              >
                <td className="py-2 px-2">
                  <div className="font-medium">{agent.name}</div>
                  <div className="text-xs text-neutral-400">{agent.id}</div>
                </td>
                <td className="py-2 px-2">
                  <span className={getStatusColor(agent.status)}>
                    {agent.status}
                  </span>
                </td>
                <td className="py-2 px-2">
                  <AgentHealthBadge health={agent.health} />
                </td>
                <td className="py-2 px-2">
                  <div className="max-w-[200px] truncate" title={agent.currentTask || '--'}>
                    {agent.currentTask || '--'}
                  </div>
                </td>
                <td className="py-2 px-2">
                  {agent.ticker ? (
                    <span className="px-2 py-0.5 bg-neutral-100 rounded text-xs font-medium">
                      {agent.ticker}
                    </span>
                  ) : (
                    '--'
                  )}
                </td>
                <td className="py-2 px-2 text-neutral-600">
                  {formatDuration(agent.taskStartedAt)}
                </td>
                <td className="py-2 px-2 text-neutral-500 text-xs">
                  {agent.lastActivityAt
                    ? new Date(agent.lastActivityAt).toLocaleTimeString()
                    : '--'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>

        {agents.length === 0 && (
          <div className="text-center py-8 text-neutral-500">
            No agents found
          </div>
        )}
      </div>
    </div>
  )
}
