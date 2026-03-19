'use client'

import { useState, useMemo } from 'react'
import { 
  Play, 
  Pause, 
  Square, 
  RotateCcw, 
  Settings, 
  Users,
  ChevronDown,
  ChevronRight,
  Filter,
  CheckSquare,
  Square as SquareIcon,
  Zap,
  Layers,
  BarChart3,
  Target,
  Radio
} from 'lucide-react'
import type { Agent } from '@/lib/api'

interface FleetControlProps {
  agents: Agent[]
  onOperation: (operation: string, agentNames: string[]) => void
}

interface AgentGroup {
  name: string
  agents: Agent[]
  status: {
    running: number
    idle: number
    paused: number
    error: number
  }
}

export function FleetControl({ agents, onOperation }: FleetControlProps) {
  const [selectedAgents, setSelectedAgents] = useState<Set<string>>(new Set())
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(new Set())
  const [filter, setFilter] = useState('')
  const [showBatchPanel, setShowBatchPanel] = useState(false)

  // Group agents by prefix (e.g., "market_structure" -> "market")
  const agentGroups = useMemo(() => {
    const groups: Record<string, AgentGroup> = {}
    
    agents.forEach((agent) => {
      const prefix = agent.name.split('_')[0] || 'other'
      if (!groups[prefix]) {
        groups[prefix] = {
          name: prefix,
          agents: [],
          status: { running: 0, idle: 0, paused: 0, error: 0 },
        }
      }
      groups[prefix].agents.push(agent)
      
      // Count status
      if (agent.status === 'running') groups[prefix].status.running++
      else if (agent.status === 'idle') groups[prefix].status.idle++
      else if (agent.status === 'paused') groups[prefix].status.paused++
      else if (agent.status === 'error') groups[prefix].status.error++
    })
    
    return Object.values(groups).sort((a, b) => a.name.localeCompare(b.name))
  }, [agents])

  // Filter agents
  const filteredGroups = useMemo(() => {
    if (!filter) return agentGroups
    
    return agentGroups.map((group) => ({
      ...group,
      agents: group.agents.filter(
        (a) =>
          a.name.toLowerCase().includes(filter.toLowerCase()) ||
          a.ticker?.toLowerCase().includes(filter.toLowerCase())
      ),
    })).filter((group) => group.agents.length > 0)
  }, [agentGroups, filter])

  // Selection helpers
  const toggleAgentSelection = (agentName: string) => {
    const newSelected = new Set(selectedAgents)
    if (newSelected.has(agentName)) {
      newSelected.delete(agentName)
    } else {
      newSelected.add(agentName)
    }
    setSelectedAgents(newSelected)
  }

  const toggleGroupSelection = (group: AgentGroup) => {
    const newSelected = new Set(selectedAgents)
    const allSelected = group.agents.every((a) => newSelected.has(a.name))
    
    if (allSelected) {
      // Deselect all in group
      group.agents.forEach((a) => newSelected.delete(a.name))
    } else {
      // Select all in group
      group.agents.forEach((a) => newSelected.add(a.name))
    }
    
    setSelectedAgents(newSelected)
  }

  const selectAll = () => {
    setSelectedAgents(new Set(agents.map((a) => a.name)))
  }

  const deselectAll = () => {
    setSelectedAgents(new Set())
  }

  const toggleGroupExpanded = (groupName: string) => {
    const newExpanded = new Set(expandedGroups)
    if (newExpanded.has(groupName)) {
      newExpanded.delete(groupName)
    } else {
      newExpanded.add(groupName)
    }
    setExpandedGroups(newExpanded)
  }

  // Get status color
  const getStatusColor = (status: Agent['status']) => {
    switch (status) {
      case 'running': return 'bg-emerald-500'
      case 'idle': return 'bg-neutral-400'
      case 'paused': return 'bg-amber-500'
      case 'error': return 'bg-red-500'
      default: return 'bg-neutral-300'
    }
  }

  // Get group health
  const getGroupHealth = (group: AgentGroup) => {
    const total = group.agents.length
    if (total === 0) return { color: 'bg-neutral-200', percentage: 0 }
    
    const healthy = group.status.running + group.status.idle
    const percentage = (healthy / total) * 100
    
    if (percentage >= 80) return { color: 'bg-emerald-500', percentage }
    if (percentage >= 50) return { color: 'bg-amber-500', percentage }
    return { color: 'bg-red-500', percentage }
  }

  const selectedAgentNames = Array.from(selectedAgents)
  const selectedCount = selectedAgents.size

  return (
    <div className="card p-4 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-blue-100 rounded-lg">
            <Layers className="w-5 h-5 text-blue-600" />
          </div>
          <div>
            <h2 className="font-semibold text-lg">Fleet Control</h2>
            <p className="text-sm text-neutral-500">
              {agents.length} agents · {selectedCount} selected
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowBatchPanel(!showBatchPanel)}
            className={`flex items-center gap-2 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
              showBatchPanel 
                ? 'bg-blue-100 text-blue-700' 
                : 'bg-neutral-100 text-neutral-700 hover:bg-neutral-200'
            }`}
          >
            <Zap className="w-4 h-4" />
            Batch Operations
            {selectedCount > 0 && (
              <span className="px-1.5 py-0.5 bg-blue-600 text-white text-xs rounded-full">
                {selectedCount}
              </span>
            )}
          </button>
        </div>
      </div>

      {/* Batch Operations Panel */}
      {showBatchPanel && (
        <div className="bg-neutral-50 rounded-lg p-4 border border-neutral-200">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm font-medium text-neutral-700">Actions:</span>
            
            <button
              onClick={() => onOperation('start', selectedAgentNames)}
              disabled={selectedCount === 0}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-100 text-emerald-700 rounded-lg text-sm font-medium hover:bg-emerald-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Play className="w-3.5 h-3.5" />
              Start
            </button>
            
            <button
              onClick={() => onOperation('stop', selectedAgentNames)}
              disabled={selectedCount === 0}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-red-100 text-red-700 rounded-lg text-sm font-medium hover:bg-red-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Square className="w-3.5 h-3.5" />
              Stop
            </button>
            
            <button
              onClick={() => onOperation('pause', selectedAgentNames)}
              disabled={selectedCount === 0}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-amber-100 text-amber-700 rounded-lg text-sm font-medium hover:bg-amber-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <Pause className="w-3.5 h-3.5" />
              Pause
            </button>
            
            <button
              onClick={() => onOperation('restart', selectedAgentNames)}
              disabled={selectedCount === 0}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-blue-100 text-blue-700 rounded-lg text-sm font-medium hover:bg-blue-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Restart
            </button>

            <div className="h-6 w-px bg-neutral-300 mx-1" />

            <button
              onClick={selectAll}
              className="text-sm text-neutral-600 hover:text-neutral-900"
            >
              Select All
            </button>
            <button
              onClick={deselectAll}
              className="text-sm text-neutral-600 hover:text-neutral-900"
            >
              Deselect All
            </button>
          </div>

          {selectedCount > 0 && (
            <div className="mt-3 pt-3 border-t border-neutral-200">
              <p className="text-sm text-neutral-600">
                Selected agents: {selectedAgentNames.slice(0, 5).join(', ')}
                {selectedCount > 5 && ` and ${selectedCount - 5} more`}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Filter */}
      <div className="flex items-center gap-3">
        <div className="relative flex-1">
          <Filter className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-neutral-400" />
          <input
            type="text"
            placeholder="Filter agents..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border border-neutral-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
        </div>
      </div>

      {/* Agent Groups */}
      <div className="space-y-2">
        {filteredGroups.map((group) => {
          const isExpanded = expandedGroups.has(group.name)
          const groupHealth = getGroupHealth(group)
          const allSelected = group.agents.every((a) => selectedAgents.has(a.name))
          const someSelected = group.agents.some((a) => selectedAgents.has(a.name)) && !allSelected

          return (
            <div key={group.name} className="border border-neutral-200 rounded-lg overflow-hidden">
              {/* Group Header */}
              <div 
                className="flex items-center gap-3 p-3 bg-neutral-50 hover:bg-neutral-100 cursor-pointer transition-colors"
                onClick={() => toggleGroupExpanded(group.name)}
              >
                {isExpanded ? (
                  <ChevronDown className="w-4 h-4 text-neutral-500" />
                ) : (
                  <ChevronRight className="w-4 h-4 text-neutral-500" />
                )}

                {showBatchPanel && (
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      toggleGroupSelection(group)
                    }}
                    className="text-neutral-500 hover:text-blue-600"
                  >
                    {allSelected ? (
                      <CheckSquare className="w-4 h-4 text-blue-600" />
                    ) : someSelected ? (
                      <div className="w-4 h-4 border-2 border-blue-600 bg-blue-100 rounded flex items-center justify-center">
                        <div className="w-2 h-0.5 bg-blue-600" />
                      </div>
                    ) : (
                      <SquareIcon className="w-4 h-4" />
                    )}
                  </button>
                )}

                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium capitalize">{group.name}</span>
                    <span className="text-xs text-neutral-500">({group.agents.length} agents)</span>
                  </div>
                </div>

                {/* Status Summary */}
                <div className="flex items-center gap-3 text-xs">
                  {group.status.running > 0 && (
                    <span className="flex items-center gap-1 text-emerald-600">
                      <div className="w-2 h-2 rounded-full bg-emerald-500" />
                      {group.status.running}
                    </span>
                  )}
                  {group.status.idle > 0 && (
                    <span className="flex items-center gap-1 text-neutral-600">
                      <div className="w-2 h-2 rounded-full bg-neutral-400" />
                      {group.status.idle}
                    </span>
                  )}
                  {group.status.paused > 0 && (
                    <span className="flex items-center gap-1 text-amber-600">
                      <div className="w-2 h-2 rounded-full bg-amber-500" />
                      {group.status.paused}
                    </span>
                  )}
                  {group.status.error > 0 && (
                    <span className="flex items-center gap-1 text-red-600">
                      <div className="w-2 h-2 rounded-full bg-red-500" />
                      {group.status.error}
                    </span>
                  )}
                </div>

                {/* Health Bar */}
                <div className="w-24 h-2 bg-neutral-200 rounded-full overflow-hidden">
                  <div 
                    className={`h-full ${groupHealth.color} transition-all`}
                    style={{ width: `${groupHealth.percentage}%` }}
                  />
                </div>
              </div>

              {/* Group Agents */}
              {isExpanded && (
                <div className="divide-y divide-neutral-100">
                  {group.agents.map((agent) => (
                    <div
                      key={agent.id}
                      className="flex items-center gap-3 p-3 hover:bg-neutral-50 transition-colors"
                    >
                      {showBatchPanel && (
                        <button
                          onClick={() => toggleAgentSelection(agent.name)}
                          className="text-neutral-500 hover:text-blue-600"
                        >
                          {selectedAgents.has(agent.name) ? (
                            <CheckSquare className="w-4 h-4 text-blue-600" />
                          ) : (
                            <SquareIcon className="w-4 h-4" />
                          )}
                        </button>
                      )}

                      <div className={`w-2.5 h-2.5 rounded-full ${getStatusColor(agent.status)}`} />

                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="font-medium text-sm truncate">{agent.name}</span>
                          {agent.ticker && (
                            <span className="px-1.5 py-0.5 bg-neutral-100 rounded text-xs">
                              {agent.ticker}
                            </span>
                          )}
                        </div>
                        {agent.currentTask && (
                          <div className="text-xs text-neutral-500 truncate">
                            {agent.currentTask}
                          </div>
                        )}
                      </div>

                      <div className="flex items-center gap-2">
                        <span className={`text-xs capitalize ${
                          agent.status === 'running' ? 'text-emerald-600' :
                          agent.status === 'error' ? 'text-red-600' :
                          agent.status === 'paused' ? 'text-amber-600' :
                          'text-neutral-600'
                        }`}>
                          {agent.status}
                        </span>

                        {!showBatchPanel && (
                          <div className="flex items-center gap-1">
                            {agent.status === 'running' ? (
                              <button
                                onClick={() => onOperation('pause', [agent.name])}
                                className="p-1.5 hover:bg-amber-100 rounded transition-colors"
                                title="Pause"
                              >
                                <Pause className="w-3.5 h-3.5 text-amber-600" />
                              </button>
                            ) : (
                              <button
                                onClick={() => onOperation('start', [agent.name])}
                                className="p-1.5 hover:bg-emerald-100 rounded transition-colors"
                                title="Start"
                              >
                                <Play className="w-3.5 h-3.5 text-emerald-600" />
                              </button>
                            )}
                            <button
                              onClick={() => onOperation('restart', [agent.name])}
                              className="p-1.5 hover:bg-blue-100 rounded transition-colors"
                              title="Restart"
                            >
                              <RotateCcw className="w-3.5 h-3.5 text-blue-600" />
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )
        })}

        {filteredGroups.length === 0 && (
          <div className="text-center py-8 text-neutral-500">
            No agents match your filter
          </div>
        )}
      </div>

      {/* Fleet Overview Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-4 border-t border-neutral-200">
        <div className="flex items-center gap-2 p-3 bg-emerald-50 rounded-lg">
          <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center">
            <Play className="w-4 h-4 text-emerald-600" />
          </div>
          <div>
            <div className="text-lg font-bold text-emerald-700">
              {agents.filter((a) => a.status === 'running').length}
            </div>
            <div className="text-xs text-emerald-600">Running</div>
          </div>
        </div>

        <div className="flex items-center gap-2 p-3 bg-neutral-50 rounded-lg">
          <div className="w-8 h-8 rounded-full bg-neutral-100 flex items-center justify-center">
            <Target className="w-4 h-4 text-neutral-600" />
          </div>
          <div>
            <div className="text-lg font-bold text-neutral-700">
              {agents.filter((a) => a.status === 'idle').length}
            </div>
            <div className="text-xs text-neutral-600">Idle</div>
          </div>
        </div>

        <div className="flex items-center gap-2 p-3 bg-amber-50 rounded-lg">
          <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center">
            <Pause className="w-4 h-4 text-amber-600" />
          </div>
          <div>
            <div className="text-lg font-bold text-amber-700">
              {agents.filter((a) => a.status === 'paused').length}
            </div>
            <div className="text-xs text-amber-600">Paused</div>
          </div>
        </div>

        <div className="flex items-center gap-2 p-3 bg-red-50 rounded-lg">
          <div className="w-8 h-8 rounded-full bg-red-100 flex items-center justify-center">
            <Radio className="w-4 h-4 text-red-600" />
          </div>
          <div>
            <div className="text-lg font-bold text-red-700">
              {agents.filter((a) => a.status === 'error').length}
            </div>
            <div className="text-xs text-red-600">Error</div>
          </div>
        </div>
      </div>
    </div>
  )
}
