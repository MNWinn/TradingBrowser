'use client'

import { useEffect, useMemo, useState, useCallback, useRef } from 'react'
import {
  getAgents,
  getAgent,
  getAgentLogs,
  getAgentOutputs,
  getFleetStatus,
  bulkAgentOperation,
  sendAgentMessage,
  applyConfigTemplate,
  createAgentWebSocket,
  type Agent,
  type AgentLog,
  type AgentOutput,
  type FleetStatus,
  type WebSocketMessage,
} from '@/lib/api'
import { FleetControl } from '@/components/agents/FleetControl'
import { AgentHealthBadge } from '@/components/agents/AgentHealthBadge'
import { 
  Play, 
  Pause, 
  Square, 
  RotateCcw, 
  Settings, 
  MessageSquare, 
  Activity,
  Zap,
  Users,
  TrendingUp,
  AlertCircle,
  CheckCircle2,
  XCircle,
  Search,
  RefreshCw,
  Cpu,
  Radio,
} from 'lucide-react'

interface AgentWithMetrics extends Agent {
  metrics?: {
    tasksCompleted: number
    tasksFailed: number
    avgLatency: number
    successRate: number
  }
  group?: string
}

function MetricCard({ 
  title, 
  value, 
  subtitle, 
  icon: Icon, 
  color = 'blue'
}: { 
  title: string
  value: string | number
  subtitle?: string
  icon: React.ElementType
  color?: 'blue' | 'green' | 'amber' | 'red' | 'purple'
}) {
  const colorClasses = {
    blue: 'bg-blue-50 border-blue-200 text-blue-900',
    green: 'bg-emerald-50 border-emerald-200 text-emerald-900',
    amber: 'bg-amber-50 border-amber-200 text-amber-900',
    red: 'bg-red-50 border-red-200 text-red-900',
    purple: 'bg-purple-50 border-purple-200 text-purple-900',
  }

  return (
    <div className={`card p-4 border ${colorClasses[color]}`}>
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium opacity-70">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {subtitle && <p className="text-xs opacity-60 mt-1">{subtitle}</p>}
        </div>
        <div className={`p-2 rounded-lg bg-white/50`}>
          <Icon className="w-5 h-5" />
        </div>
      </div>
    </div>
  )
}

function AgentStatusGrid({ 
  agents, 
  selectedAgentId, 
  onSelectAgent,
  onAction
}: { 
  agents: AgentWithMetrics[]
  selectedAgentId: string | null
  onSelectAgent: (id: string) => void
  onAction: (action: string, agentId: string) => void
}) {
  const getStatusIcon = (status: Agent['status']) => {
    switch (status) {
      case 'running': return <Activity className="w-4 h-4 text-emerald-500" />
      case 'idle': return <CheckCircle2 className="w-4 h-4 text-neutral-400" />
      case 'paused': return <Pause className="w-4 h-4 text-amber-500" />
      case 'error': return <AlertCircle className="w-4 h-4 text-red-500" />
      default: return <div className="w-4 h-4 rounded-full bg-neutral-300" />
    }
  }

  const getStatusColor = (status: Agent['status']) => {
    switch (status) {
      case 'running': return 'border-emerald-200 bg-emerald-50/50'
      case 'idle': return 'border-neutral-200 bg-neutral-50/50'
      case 'paused': return 'border-amber-200 bg-amber-50/50'
      case 'error': return 'border-red-200 bg-red-50/50'
      default: return 'border-neutral-200'
    }
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-3">
      {agents.map((agent) => (
        <div
          key={agent.id}
          onClick={() => onSelectAgent(agent.id)}
          className={`card p-4 cursor-pointer transition-all hover:shadow-md border-2 ${
            selectedAgentId === agent.id ? 'border-blue-500 shadow-md' : 'border-transparent'
          } ${getStatusColor(agent.status)}`}
        >
          <div className="flex items-start justify-between mb-3">
            <div className="flex items-center gap-2">
              {getStatusIcon(agent.status)}
              <span className="font-semibold text-sm truncate max-w-[120px]">{agent.name}</span>
            </div>
            <AgentHealthBadge health={agent.health} size="sm" />
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs">
              <span className="text-neutral-500">Status</span>
              <span className={`font-medium capitalize ${
                agent.status === 'running' ? 'text-emerald-600' :
                agent.status === 'error' ? 'text-red-600' :
                agent.status === 'paused' ? 'text-amber-600' :
                'text-neutral-600'
              }`}>{agent.status}</span>
            </div>

            {agent.ticker && (
              <div className="flex items-center justify-between text-xs">
                <span className="text-neutral-500">Ticker</span>
                <span className="px-2 py-0.5 bg-neutral-100 rounded font-medium">{agent.ticker}</span>
              </div>
            )}

            {agent.metrics && (
              <>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-neutral-500">Success Rate</span>
                  <span className="font-medium">{Math.round(agent.metrics.successRate * 100)}%</span>
                </div>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-neutral-500">Tasks</span>
                  <span className="font-medium">{agent.metrics.tasksCompleted}</span>
                </div>
              </>
            )}

            {agent.currentTask && (
              <div className="text-xs text-neutral-500 truncate mt-2 pt-2 border-t border-neutral-200">
                {agent.currentTask}
              </div>
            )}
          </div>

          <div className="flex items-center gap-1 mt-3 pt-3 border-t border-neutral-200/50">
            {agent.status === 'running' ? (
              <button
                onClick={(e) => { e.stopPropagation(); onAction('pause', agent.id) }}
                className="p-1.5 hover:bg-amber-100 rounded transition-colors"
                title="Pause"
              >
                <Pause className="w-3.5 h-3.5 text-amber-600" />
              </button>
            ) : (
              <button
                onClick={(e) => { e.stopPropagation(); onAction('start', agent.id) }}
                className="p-1.5 hover:bg-emerald-100 rounded transition-colors"
                title="Start"
              >
                <Play className="w-3.5 h-3.5 text-emerald-600" />
              </button>
            )}
            <button
              onClick={(e) => { e.stopPropagation(); onAction('restart', agent.id) }}
              className="p-1.5 hover:bg-blue-100 rounded transition-colors"
              title="Restart"
            >
              <RotateCcw className="w-3.5 h-3.5 text-blue-600" />
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); onAction('stop', agent.id) }}
              className="p-1.5 hover:bg-red-100 rounded transition-colors"
              title="Stop"
            >
              <Square className="w-3.5 h-3.5 text-red-600" />
            </button>
          </div>
        </div>
      ))}
    </div>
  )
}

function AgentDetailView({ 
  agentId, 
  onClose 
}: { 
  agentId: string
  onClose: () => void 
}) {
  const [agent, setAgent] = useState<Agent | null>(null)
  const [logs, setLogs] = useState<AgentLog[]>([])
  const [outputs, setOutputs] = useState<AgentOutput[]>([])
  const [activeTab, setActiveTab] = useState<'overview' | 'logs' | 'outputs' | 'config'>('overview')
  const [loading, setLoading] = useState(true)
  const logsEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const fetchData = async () => {
      setLoading(true)
      try {
        const [agentData, logsData, outputsData] = await Promise.all([
          getAgent(agentId),
          getAgentLogs(agentId, 50),
          getAgentOutputs(agentId, 20),
        ])
        setAgent(agentData)
        setLogs(logsData.logs || [])
        setOutputs(outputsData.outputs || [])
      } catch (e) {
        console.error('Failed to fetch agent details:', e)
      } finally {
        setLoading(false)
      }
    }

    fetchData()
    const interval = setInterval(fetchData, 5000)
    return () => clearInterval(interval)
  }, [agentId])

  useEffect(() => {
    if (activeTab === 'logs' && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, activeTab])

  if (loading || !agent) {
    return (
      <div className="card p-6">
        <div className="flex items-center justify-center h-64">
          <RefreshCw className="w-6 h-6 animate-spin text-neutral-400" />
        </div>
      </div>
    )
  }

  return (
    <div className="card p-6">
      <div className="flex items-start justify-between mb-6">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold">{agent.name}</h2>
            <AgentHealthBadge health={agent.health} showLabel size="md" />
          </div>
          <p className="text-sm text-neutral-500 mt-1">{agent.id}</p>
        </div>
        <button onClick={onClose} className="p-2 hover:bg-neutral-100 rounded-lg">
          <XCircle className="w-5 h-5" />
        </button>
      </div>

      <div className="flex gap-1 border-b border-neutral-200 mb-4">
        {(['overview', 'logs', 'outputs', 'config'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab
                ? 'border-blue-500 text-blue-600'
                : 'border-transparent text-neutral-500 hover:text-neutral-700'
            }`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      <div className="min-h-[300px]">
        {activeTab === 'overview' && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="bg-neutral-50 rounded-lg p-4">
                <div className="text-xs font-medium text-neutral-500 uppercase">Status</div>
                <div className="text-lg font-semibold capitalize mt-1">{agent.status}</div>
              </div>
              <div className="bg-neutral-50 rounded-lg p-4">
                <div className="text-xs font-medium text-neutral-500 uppercase">Type</div>
                <div className="text-lg font-semibold mt-1">{agent.type || 'Unknown'}</div>
              </div>
            </div>

            {agent.currentTask && (
              <div className="bg-blue-50 rounded-lg p-4">
                <div className="text-xs font-medium text-blue-600 uppercase">Current Task</div>
                <div className="text-sm mt-1">{agent.currentTask}</div>
                {agent.taskStartedAt && (
                  <div className="text-xs text-blue-400 mt-1">
                    Started: {new Date(agent.taskStartedAt).toLocaleString()}
                  </div>
                )}
              </div>
            )}

            {agent.ticker && (
              <div className="bg-neutral-50 rounded-lg p-4">
                <div className="text-xs font-medium text-neutral-500 uppercase">Active Ticker</div>
                <div className="text-2xl font-bold mt-1">{agent.ticker}</div>
              </div>
            )}

            {agent.performance && (
              <div className="bg-neutral-50 rounded-lg p-4">
                <div className="text-xs font-medium text-neutral-500 uppercase mb-3">Performance</div>
                <div className="grid grid-cols-3 gap-4">
                  <div>
                    <div className="text-2xl font-bold">{agent.performance.tasksCompleted || 0}</div>
                    <div className="text-xs text-neutral-500">Completed</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold">{agent.performance.tasksFailed || 0}</div>
                    <div className="text-xs text-neutral-500">Failed</div>
                  </div>
                  <div>
                    <div className="text-2xl font-bold">
                      {agent.performance.avgTaskDuration ? `${Math.round(agent.performance.avgTaskDuration)}ms` : '--'}
                    </div>
                    <div className="text-xs text-neutral-500">Avg Latency</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'logs' && (
          <div className="space-y-2 max-h-[400px] overflow-y-auto font-mono text-xs">
            {logs.length === 0 ? (
              <div className="text-center text-neutral-500 py-8">No logs available</div>
            ) : (
              logs.map((log, idx) => (
                <div
                  key={idx}
                  className={`p-3 rounded ${
                    log.level === 'error' ? 'bg-red-50 text-red-800' :
                    log.level === 'warn' ? 'bg-amber-50 text-amber-800' :
                    log.level === 'debug' ? 'bg-neutral-50 text-neutral-600' :
                    'bg-blue-50 text-blue-800'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-neutral-400">{new Date(log.timestamp).toLocaleTimeString()}</span>
                    <span className={`px-1.5 py-0.5 rounded text-[10px] uppercase font-bold ${
                      log.level === 'error' ? 'bg-red-200 text-red-800' :
                      log.level === 'warn' ? 'bg-amber-200 text-amber-800' :
                      log.level === 'debug' ? 'bg-neutral-200 text-neutral-700' :
                      'bg-blue-200 text-blue-800'
                    }`}>
                      {log.level}
                    </span>
                  </div>
                  <div>{log.message}</div>
                </div>
              ))
            )}
            <div ref={logsEndRef} />
          </div>
        )}

        {activeTab === 'outputs' && (
          <div className="space-y-3 max-h-[400px] overflow-y-auto">
            {outputs.length === 0 ? (
              <div className="text-center text-neutral-500 py-8">No outputs available</div>
            ) : (
              outputs.map((output, idx) => (
                <div key={idx} className="bg-neutral-50 rounded-lg p-4">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-xs text-neutral-500">
                      {new Date(output.timestamp).toLocaleString()}
                    </span>
                    {output.type && (
                      <span className="px-2 py-0.5 bg-neutral-200 rounded text-xs">{output.type}</span>
                    )}
                  </div>
                  <pre className="text-xs overflow-auto max-h-40 bg-white p-2 rounded border">
                    {JSON.stringify(output.data, null, 2)}
                  </pre>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === 'config' && (
          <div className="space-y-4">
            <div className="bg-neutral-50 rounded-lg p-4">
              <div className="text-xs font-medium text-neutral-500 uppercase mb-2">Configuration Templates</div>
              <div className="flex flex-wrap gap-2">
                {['conservative', 'aggressive', 'balanced', 'research', 'production'].map((template) => (
                  <button
                    key={template}
                    onClick={async () => {
                      try {
                        await applyConfigTemplate(template, [agent.name])
                        alert(`Applied ${template} template to ${agent.name}`)
                      } catch (e) {
                        alert('Failed to apply template')
                      }
                    }}
                    className="px-3 py-1.5 bg-white border border-neutral-200 rounded text-xs font-medium hover:bg-neutral-50 transition-colors"
                  >
                    {template.charAt(0).toUpperCase() + template.slice(1)}
                  </button>
                ))}
              </div>
            </div>

            <div className="bg-neutral-50 rounded-lg p-4">
              <div className="text-xs font-medium text-neutral-500 uppercase mb-2">Agent Metadata</div>
              <pre className="text-xs overflow-auto max-h-60 bg-white p-2 rounded border">
                {JSON.stringify(agent.metadata || {}, null, 2)}
              </pre>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function RealTimeActivity({ events }: { events: WebSocketMessage[] }) {
  const getEventIcon = (type: string) => {
    switch (type) {
      case 'agent_status_update': return <Activity className="w-4 h-4 text-blue-500" />
      case 'fleet_status_update': return <Users className="w-4 h-4 text-purple-500" />
      case 'market_event': return <TrendingUp className="w-4 h-4 text-emerald-500" />
      case 'signal': return <Zap className="w-4 h-4 text-amber-500" />
      case 'agent_message': return <MessageSquare className="w-4 h-4 text-indigo-500" />
      default: return <Radio className="w-4 h-4 text-neutral-400" />
    }
  }

  const getEventColor = (type: string) => {
    switch (type) {
      case 'agent_status_update': return 'border-blue-200 bg-blue-50/50'
      case 'fleet_status_update': return 'border-purple-200 bg-purple-50/50'
      case 'market_event': return 'border-emerald-200 bg-emerald-50/50'
      case 'signal': return 'border-amber-200 bg-amber-50/50'
      case 'agent_message': return 'border-indigo-200 bg-indigo-50/50'
      default: return 'border-neutral-200'
    }
  }

  return (
    <div className="space-y-2 max-h-[400px] overflow-y-auto">
      {events.length === 0 ? (
        <div className="text-center text-neutral-500 py-8 text-sm">No events yet</div>
      ) : (
        events.slice().reverse().map((event, idx) => (
          <div
            key={idx}
            className={`p-3 rounded-lg border ${getEventColor(event.type)} text-sm`}
          >
            <div className="flex items-start gap-3">
              {getEventIcon(event.type)}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium capitalize">{event.type.replace(/_/g, ' ')}</span>
                  <span className="text-xs text-neutral-400">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                <div className="text-neutral-600 mt-1 truncate">
                  {event.type === 'agent_status_update' && (
                    <span>{event.agent_name} → {event.status}</span>
                  )}
                  {event.type === 'signal' && (
                    <span>{event.signal?.ticker} {event.signal?.action} ({Math.round(event.signal?.confidence * 100)}%)</span>
                  )}
                  {event.type === 'market_event' && (
                    <span>{event.event_type}: {JSON.stringify(event.payload).slice(0, 50)}...</span>
                  )}
                  {event.type === 'agent_message' && (
                    <span>{event.message?.from_agent} → {event.message?.to_agent}: {event.message?.message_type}</span>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))
      )}
    </div>
  )
}

export default function AgentsPage() {
  const [agents, setAgents] = useState<AgentWithMetrics[]>([])
  const [fleetStatus, setFleetStatus] = useState<FleetStatus | null>(null)
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [wsEvents, setWsEvents] = useState<WebSocketMessage[]>([])
  const [wsConnected, setWsConnected] = useState(false)
  const wsRef = useRef<ReturnType<typeof createAgentWebSocket> | null>(null)

  useEffect(() => {
    wsRef.current = createAgentWebSocket(undefined, {
      onConnect: () => setWsConnected(true),
      onDisconnect: () => setWsConnected(false),
    })

    wsRef.current.connect()

    const unsubStatus = wsRef.current.subscribe('agent_status_update', (msg) => {
      setWsEvents((prev) => [...prev.slice(-49), msg])
      fetchAgents()
    })

    const unsubFleet = wsRef.current.subscribe('fleet_status_update', (msg) => {
      setWsEvents((prev) => [...prev.slice(-49), msg])
    })

    const unsubMarket = wsRef.current.subscribe('market_event', (msg) => {
      setWsEvents((prev) => [...prev.slice(-49), msg])
    })

    const unsubSignal = wsRef.current.subscribe('signal', (msg) => {
      setWsEvents((prev) => [...prev.slice(-49), msg])
    })

    const unsubMessage = wsRef.current.subscribe('agent_message', (msg) => {
      setWsEvents((prev) => [...prev.slice(-49), msg])
    })

    return () => {
      unsubStatus()
      unsubFleet()
      unsubMarket()
      unsubSignal()
      unsubMessage()
      wsRef.current?.disconnect()
    }
  }, [])

  const fetchAgents = useCallback(async () => {
    try {
      const [agentsData, fleetData] = await Promise.all([
        getAgents(),
        getFleetStatus(),
      ])

      const enhancedAgents = (agentsData.agents || []).map((agent: Agent) => ({
        ...agent,
        group: agent.name.split('_')[0] || 'other',
        metrics: agent.performance ? {
          tasksCompleted: agent.performance.tasksCompleted || 0,
          tasksFailed: agent.performance.tasksFailed || 0,
          avgLatency: agent.performance.avgTaskDuration || 0,
          successRate: agent.performance.tasksCompleted && (agent.performance.tasksCompleted + agent.performance.tasksFailed) > 0
            ? agent.performance.tasksCompleted / (agent.performance.tasksCompleted + agent.performance.tasksFailed)
            : 0,
        } : undefined,
      }))

      setAgents(enhancedAgents)
      setFleetStatus(fleetData)
    } catch (e) {
      console.error('Failed to fetch agents:', e)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchAgents()
    const interval = setInterval(fetchAgents, 10000)
    return () => clearInterval(interval)
  }, [fetchAgents])

  const filteredAgents = useMemo(() => {
    return agents.filter((agent) => {
      const matchesFilter = !filter || 
        agent.name.toLowerCase().includes(filter.toLowerCase()) ||
        agent.ticker?.toLowerCase().includes(filter.toLowerCase())
      
      const matchesStatus = statusFilter === 'all' || agent.status === statusFilter
      
      return matchesFilter && matchesStatus
    })
  }, [agents, filter, statusFilter])

  const handleAgentAction = async (action: string, agentId: string) => {
    try {
      const agent = agents.find((a) => a.id === agentId)
      if (!agent) return

      await bulkAgentOperation({
        agent_names: [agent.name],
        command: action as any,
      })

      fetchAgents()
    } catch (e) {
      console.error('Action failed:', e)
      alert(`Failed to ${action} agent`)
    }
  }

  const handleFleetOperation = async (operation: string, agentNames: string[]) => {
    try {
      await bulkAgentOperation({
        agent_names: agentNames,
        command: operation as any,
      })
      fetchAgents()
    } catch (e) {
      console.error('Fleet operation failed:', e)
      alert('Fleet operation failed')
    }
  }

  if (loading) {
    return (
      <main className="p-6">
        <div className="flex items-center justify-center h-96">
          <RefreshCw className="w-8 h-8 animate-spin text-neutral-400" />
        </div>
      </main>
    )
  }

  return (
    <main className="p-6 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Agent Fleet Management</h1>
          <p className="text-sm text-neutral-500 mt-1">
            Manage and monitor your trading agent fleet in real-time
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium ${
            wsConnected ? 'bg-emerald-100 text-emerald-700' : 'bg-red-100 text-red-700'
          }`}>
            <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-emerald-500 animate-pulse' : 'bg-red-500'}`} />
            {wsConnected ? 'Live' : 'Disconnected'}
          </div>
          <button
            onClick={fetchAgents}
            className="p-2 hover:bg-neutral-100 rounded-lg transition-colors"
          >
            <RefreshCw className="w-5 h-5" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Total Agents"
          value={fleetStatus?.total_agents || 0}
          subtitle={`${fleetStatus?.running || 0} running`}
          icon={Users}
          color="blue"
        />
        <MetricCard
          title="Fleet Health"
          value={`${Math.round((fleetStatus?.health_score || 0) * 100)}%`}
          subtitle={`${fleetStatus?.error || 0} agents in error`}
          icon={Activity}
          color="green"
        />
        <MetricCard
          title="Active Tasks"
          value={agents.filter((a) => a.status === 'running').length}
          subtitle={`${agents.filter((a) => a.status === 'idle').length} idle`}
          icon={Cpu}
          color="purple"
        />
        <MetricCard
          title="Signals Today"
          value={wsEvents.filter((e) => e.type === 'signal').length}
          subtitle="From WebSocket stream"
          icon={Zap}
          color="amber"
        />
      </div>

      <FleetControl
        agents={agents}
        onOperation={handleFleetOperation}
      />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
              <input
                type="text"
                placeholder="Search agents..."
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-neutral-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <select
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              className="px-3 py-2 border border-neutral-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value="all">All Status</option>
              <option value="running">Running</option>
              <option value="idle">Idle</option>
              <option value="paused">Paused</option>
              <option value="error">Error</option>
            </select>
          </div>

          <AgentStatusGrid
            agents={filteredAgents}
            selectedAgentId={selectedAgentId}
            onSelectAgent={setSelectedAgentId}
            onAction={handleAgentAction}
          />

          {filteredAgents.length === 0 && (
            <div className="text-center py-12 text-neutral-500">
              No agents match your filters
            </div>
          )}
        </div>

        <div className="space-y-4">
          {selectedAgentId ? (
            <AgentDetailView
              agentId={selectedAgentId}
              onClose={() => setSelectedAgentId(null)}
            />
          ) : (
            <div className="card p-6 text-center text-neutral-500">
              <div className="mb-3">
                <Users className="w-12 h-12 mx-auto text-neutral-300" />
              </div>
              <p>Select an agent to view details</p>
            </div>
          )}

          <div className="card p-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold flex items-center gap-2">
                <Radio className="w-4 h-4" />
                Real-time Activity
              </h3>
              <span className="text-xs text-neutral-400">{wsEvents.length} events</span>
            </div>
            <RealTimeActivity events={wsEvents} />
          </div>
        </div>
      </div>
    </main>
  )
}
