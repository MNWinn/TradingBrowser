import React, { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { 
  Activity, Brain, TrendingUp, Target, Shield, 
  Zap, BarChart3, Search, Cpu, Clock,
  Play, Pause, CheckCircle, AlertCircle
} from 'lucide-react';

interface Agent {
  id: string;
  name: string;
  status: 'running' | 'analyzing' | 'completed' | 'idle' | 'error';
  ticker: string;
  lastActivity: string;
  currentTask: string;
  recommendation?: string;
  confidence?: number;
  icon: React.ReactNode;
  color: string;
}

const AGENTS: Agent[] = [
  {
    id: '1',
    name: 'MiroFish AI',
    status: 'running',
    ticker: 'SPY',
    lastActivity: '2s ago',
    currentTask: 'Deep multi-timeframe analysis',
    recommendation: 'BULLISH',
    confidence: 0.74,
    icon: <Brain className="w-5 h-5" />,
    color: 'bg-purple-500'
  },
  {
    id: '2',
    name: 'Technical Analysis',
    status: 'analyzing',
    ticker: 'QQQ',
    lastActivity: '5s ago',
    currentTask: 'Calculating RSI, MACD, VWAP',
    recommendation: 'NEUTRAL',
    confidence: 0.52,
    icon: <BarChart3 className="w-5 h-5" />,
    color: 'bg-blue-500'
  },
  {
    id: '3',
    name: 'Market Scanner',
    status: 'running',
    ticker: 'AAPL',
    lastActivity: '8s ago',
    currentTask: 'Scanning for volume spikes',
    recommendation: 'BULLISH',
    confidence: 0.68,
    icon: <Search className="w-5 h-5" />,
    color: 'bg-green-500'
  },
  {
    id: '4',
    name: 'Pattern Recognition',
    status: 'analyzing',
    ticker: 'MSFT',
    lastActivity: '12s ago',
    currentTask: 'Detecting H&S, triangles',
    recommendation: 'WATCHLIST',
    confidence: 0.45,
    icon: <Target className="w-5 h-5" />,
    color: 'bg-yellow-500'
  },
  {
    id: '5',
    name: 'Momentum Agent',
    status: 'running',
    ticker: 'NVDA',
    lastActivity: '3s ago',
    currentTask: 'Analyzing price acceleration',
    recommendation: 'BEARISH',
    confidence: 0.61,
    icon: <Zap className="w-5 h-5" />,
    color: 'bg-red-500'
  },
  {
    id: '6',
    name: 'Support/Resistance',
    status: 'analyzing',
    ticker: 'TSLA',
    lastActivity: '15s ago',
    currentTask: 'Mapping key levels',
    recommendation: 'BULLISH',
    confidence: 0.71,
    icon: <Shield className="w-5 h-5" />,
    color: 'bg-indigo-500'
  },
  {
    id: '7',
    name: 'Volume Profile',
    status: 'running',
    ticker: 'GOOGL',
    lastActivity: '7s ago',
    currentTask: 'Calculating POC and value area',
    recommendation: 'NEUTRAL',
    confidence: 0.49,
    icon: <BarChart3 className="w-5 h-5" />,
    color: 'bg-teal-500'
  },
  {
    id: '8',
    name: 'Regime Detection',
    status: 'analyzing',
    ticker: 'SPY',
    lastActivity: '1s ago',
    currentTask: 'Classifying market regime',
    recommendation: 'TRENDING_UP',
    confidence: 0.82,
    icon: <TrendingUp className="w-5 h-5" />,
    color: 'bg-orange-500'
  }
];

const STATUS_ICONS = {
  running: <Play className="w-4 h-4 text-green-400" />,
  analyzing: <Activity className="w-4 h-4 text-yellow-400 animate-pulse" />,
  completed: <CheckCircle className="w-4 h-4 text-blue-400" />,
  idle: <Pause className="w-4 h-4 text-gray-400" />,
  error: <AlertCircle className="w-4 h-4 text-red-400" />
};

const STATUS_COLORS = {
  running: 'border-green-500/30 bg-green-500/10',
  analyzing: 'border-yellow-500/30 bg-yellow-500/10',
  completed: 'border-blue-500/30 bg-blue-500/10',
  idle: 'border-gray-500/30 bg-gray-500/10',
  error: 'border-red-500/30 bg-red-500/10'
};

export function AgentMonitor() {
  const [agents, setAgents] = useState<Agent[]>(AGENTS);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);

  useEffect(() => {
    // Simulate real-time updates
    const interval = setInterval(() => {
      setAgents(prev => prev.map(agent => ({
        ...agent,
        lastActivity: Math.floor(Math.random() * 15) + 's ago',
        confidence: Math.min(0.95, Math.max(0.40, agent.confidence + (Math.random() - 0.5) * 0.05))
      })));
      setLastUpdate(new Date());
    }, 3000);

    return () => clearInterval(interval);
  }, []);

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Cpu className="w-6 h-6 text-cyan-400" />
            Agent Monitor
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            Real-time research activity across 8 agents
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Clock className="w-4 h-4" />
          Last update: {lastUpdate.toLocaleTimeString()}
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid grid-cols-4 gap-4">
        <Card className="p-4 bg-slate-900/50 border-slate-700">
          <div className="text-2xl font-bold text-cyan-400">{agents.length}</div>
          <div className="text-xs text-slate-500">Active Agents</div>
        </Card>
        <Card className="p-4 bg-slate-900/50 border-slate-700">
          <div className="text-2xl font-bold text-green-400">
            {agents.filter(a => a.status === 'running').length}
          </div>
          <div className="text-xs text-slate-500">Running</div>
        </Card>
        <Card className="p-4 bg-slate-900/50 border-slate-700">
          <div className="text-2xl font-bold text-yellow-400">
            {agents.filter(a => a.status === 'analyzing').length}
          </div>
          <div className="text-xs text-slate-500">Analyzing</div>
        </Card>
        <Card className="p-4 bg-slate-900/50 border-slate-700">
          <div className="text-2xl font-bold text-purple-400">
            {(agents.reduce((acc, a) => acc + (a.confidence || 0), 0) / agents.length * 100).toFixed(0)}%
          </div>
          <div className="text-xs text-slate-500">Avg Confidence</div>
        </Card>
      </div>

      {/* Agent Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {agents.map((agent) => (
          <Card
            key={agent.id}
            className={`p-4 cursor-pointer transition-all hover:scale-[1.02] ${STATUS_COLORS[agent.status]} border`}
            onClick={() => setSelectedAgent(agent)}
          >
            {/* Header */}
            <div className="flex items-start justify-between mb-3">
              <div className={`p-2 rounded-lg ${agent.color} text-white`}>
                {agent.icon}
              </div>
              {STATUS_ICONS[agent.status]}
            </div>

            {/* Agent Info */}
            <h3 className="font-medium text-white text-sm mb-1">{agent.name}</h3>
            <div className="flex items-center gap-2 mb-2">
              <Badge variant="outline" className="text-xs bg-slate-800 border-slate-600">
                {agent.ticker}
              </Badge>
              <span className="text-xs text-slate-500">{agent.lastActivity}</span>
            </div>

            {/* Task */}
            <p className="text-xs text-slate-400 mb-3 line-clamp-2">
              {agent.currentTask}
            </p>

            {/* Signal */}
            {agent.recommendation && (
              <div className="flex items-center justify-between">
                <span className={`text-xs font-medium ${
                  agent.recommendation.includes('BULLISH') ? 'text-green-400' :
                  agent.recommendation.includes('BEARISH') ? 'text-red-400' :
                  'text-yellow-400'
                }`}>
                  {agent.recommendation}
                </span>
                <div className="flex items-center gap-1">
                  <div className="w-16 h-1.5 bg-slate-700 rounded-full overflow-hidden">
                    <div 
                      className={`h-full rounded-full ${
                        (agent.confidence || 0) > 0.7 ? 'bg-green-500' :
                        (agent.confidence || 0) > 0.5 ? 'bg-yellow-500' : 'bg-red-500'
                      }`}
                      style={{ width: `${(agent.confidence || 0) * 100}%` }}
                    />
                  </div>
                  <span className="text-xs text-slate-500">
                    {(agent.confidence || 0) * 100}%
                  </span>
                </div>
              </div>
            )}
          </Card>
        ))}
      </div>

      {/* Selected Agent Detail */}
      {selectedAgent && (
        <Card className="p-6 bg-slate-900/80 border-slate-700">
          <div className="flex items-start justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className={`p-3 rounded-lg ${selectedAgent.color} text-white`}>
                {selectedAgent.icon}
              </div>
              <div>
                <h2 className="text-xl font-bold text-white">{selectedAgent.name}</h2>
                <div className="flex items-center gap-2 mt-1">
                  <Badge className={selectedAgent.status === 'running' ? 'bg-green-500' : 'bg-yellow-500'}>
                    {selectedAgent.status}
                  </Badge>
                  <span className="text-sm text-slate-400">on {selectedAgent.ticker}</span>
                </div>
              </div>
            </div>
            <button 
              onClick={() => setSelectedAgent(null)}
              className="text-slate-400 hover:text-white"
            >
              ✕
            </button>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <div className="text-xs text-slate-500 mb-1">Current Task</div>
              <div className="text-sm text-white">{selectedAgent.currentTask}</div>
            </div>
            <div>
              <div className="text-xs text-slate-500 mb-1">Last Activity</div>
              <div className="text-sm text-white">{selectedAgent.lastActivity}</div>
            </div>
          </div>

          {selectedAgent.recommendation && (
            <div className="p-4 bg-slate-800/50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs text-slate-500">Signal</span>
                <span className={`text-sm font-bold ${
                  selectedAgent.recommendation.includes('BULLISH') ? 'text-green-400' :
                  selectedAgent.recommendation.includes('BEARISH') ? 'text-red-400' :
                  'text-yellow-400'
                }`}>
                  {selectedAgent.recommendation}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-500">Confidence</span>
                <span className="text-sm text-white">
                  {(selectedAgent.confidence || 0) * 100}%
                </span>
              </div>
            </div>
          )}
        </Card>
      )}

      {/* Live Activity Feed */}
      <Card className="p-4 bg-slate-900/50 border-slate-700">
        <h3 className="text-sm font-medium text-white mb-3 flex items-center gap-2">
          <Activity className="w-4 h-4 text-cyan-400" />
          Live Activity Feed
        </h3>
        <div className="space-y-2 max-h-40 overflow-y-auto">
          {agents.slice(0, 5).map((agent, i) => (
            <div key={i} className="flex items-center gap-3 text-sm">
              <span className="text-xs text-slate-500">{agent.lastActivity}</span>
              <span className="text-cyan-400">{agent.name}</span>
              <span className="text-slate-400">{agent.currentTask}</span>
              <span className={`text-xs ${
                agent.recommendation?.includes('BULLISH') ? 'text-green-400' :
                agent.recommendation?.includes('BEARISH') ? 'text-red-400' :
                'text-yellow-400'
              }`}>
                {agent.recommendation}
              </span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

export default AgentMonitor;
