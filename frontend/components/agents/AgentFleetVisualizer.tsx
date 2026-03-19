import React, { useEffect, useState } from 'react';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Activity, TrendingUp, TrendingDown, Minus, Brain, Target, Shield, Zap } from 'lucide-react';

interface Agent {
  id: string;
  name: string;
  status: 'running' | 'idle' | 'analyzing' | 'completed';
  ticker: string;
  lastUpdate: string;
  recommendation?: string;
  confidence?: number;
}

const AGENT_ICONS: Record<string, React.ReactNode> = {
  'Technical Analysis': <TrendingUp className="w-5 h-5" />,
  'Regime Detection': <Target className="w-5 h-5" />,
  'MiroFish': <Brain className="w-5 h-5" />,
  'Market Scanner': <Activity className="w-5 h-5" />,
  'Pattern Recognition': <Zap className="w-5 h-5" />,
  'Momentum': <TrendingUp className="w-5 h-5" />,
  'Support/Resistance': <Shield className="w-5 h-5" />,
  'Volume Profile': <Activity className="w-5 h-5" />,
};

const STATUS_COLORS: Record<string, string> = {
  running: 'bg-green-500',
  idle: 'bg-gray-400',
  analyzing: 'bg-yellow-500 animate-pulse',
  completed: 'bg-blue-500',
};

const RECOMMENDATION_ICONS: Record<string, React.ReactNode> = {
  LONG: <TrendingUp className="w-4 h-4 text-green-500" />,
  SHORT: <TrendingDown className="w-4 h-4 text-red-500" />,
  NEUTRAL: <Minus className="w-4 h-4 text-gray-500" />,
  WATCHLIST: <Activity className="w-4 h-4 text-yellow-500" />,
};

export function AgentFleetVisualizer() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  useEffect(() => {
    const fetchAgents = async () => {
      try {
        const response = await fetch('/api/agents');
        if (response.ok) {
          const data = await response.json();
          setAgents(data.items || []);
          setLastUpdate(new Date());
        }
      } catch (error) {
        console.error('Failed to fetch agents:', error);
      }
    };

    fetchAgents();
    const interval = setInterval(fetchAgents, 5000);
    return () => clearInterval(interval);
  }, []);

  const runningAgents = agents.filter(a => a.status === 'running' || a.status === 'analyzing');
  const idleAgents = agents.filter(a => a.status === 'idle');

  return (
    <Card className="p-6 bg-gradient-to-br from-slate-900 to-slate-800 border-slate-700">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h2 className="text-2xl font-bold text-white flex items-center gap-2">
            <Activity className="w-6 h-6 text-cyan-400" />
            Agent Fleet
          </h2>
          <p className="text-slate-400 text-sm mt-1">
            {runningAgents.length} active agents studying market predictions
          </p>
        </div>
        <div className="flex items-center gap-2">
          <div className="flex items-center gap-1 text-xs text-slate-400">
            <div className="w-2 h-2 rounded-full bg-green-500 animate-pulse" />
            Live
          </div>
          <span className="text-xs text-slate-500">
            {lastUpdate.toLocaleTimeString()}
          </span>
        </div>
      </div>

      {/* Active Agents Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        {runningAgents.map((agent) => (
          <div
            key={agent.id}
            className="relative p-4 rounded-xl bg-slate-800/50 border border-slate-700 hover:border-cyan-500/50 transition-all group"
          >
            {/* Status Indicator */}
            <div className={`absolute top-3 right-3 w-2 h-2 rounded-full ${STATUS_COLORS[agent.status]}`} />
            
            {/* Agent Icon */}
            <div className="mb-3 text-cyan-400">
              {AGENT_ICONS[agent.name] || <Activity className="w-5 h-5" />}
            </div>
            
            {/* Agent Name */}
            <h3 className="text-sm font-medium text-white mb-1">
              {agent.name}
            </h3>
            
            {/* Ticker */}
            <div className="flex items-center gap-2 mb-2">
              <Badge variant="outline" className="text-xs bg-slate-900 border-slate-600 text-slate-300">
                {agent.ticker || 'SPY'}
              </Badge>
            </div>
            
            {/* Recommendation */}
            {agent.recommendation && (
              <div className="flex items-center gap-2 mt-2">
                {RECOMMENDATION_ICONS[agent.recommendation]}
                <span className={`text-xs font-medium ${
                  agent.recommendation === 'LONG' ? 'text-green-400' :
                  agent.recommendation === 'SHORT' ? 'text-red-400' :
                  'text-yellow-400'
                }`}>
                  {agent.recommendation}
                </span>
                {agent.confidence && (
                  <span className="text-xs text-slate-500">
                    {(agent.confidence * 100).toFixed(0)}%
                  </span>
                )}
              </div>
            )}
            
            {/* Animated Border */}
            {agent.status === 'analyzing' && (
              <div className="absolute inset-0 rounded-xl border-2 border-cyan-500/30 animate-pulse pointer-events-none" />
            )}
          </div>
        ))}
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-4 pt-4 border-t border-slate-700">
        <div className="text-center">
          <div className="text-2xl font-bold text-cyan-400">{agents.length}</div>
          <div className="text-xs text-slate-500">Total Agents</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-green-400">{runningAgents.length}</div>
          <div className="text-xs text-slate-500">Active Now</div>
        </div>
        <div className="text-center">
          <div className="text-2xl font-bold text-blue-400">{idleAgents.length}</div>
          <div className="text-xs text-slate-500">On Standby</div>
        </div>
      </div>

      {/* Market Pulse */}
      <div className="mt-4 pt-4 border-t border-slate-700">
        <div className="flex items-center justify-between text-xs text-slate-400">
          <span>Market Pulse</span>
          <div className="flex items-center gap-1">
            <div className="w-1.5 h-1.5 rounded-full bg-green-500" />
            <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse delay-75" />
            <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse delay-150" />
          </div>
        </div>
      </div>
    </Card>
  );
}

export default AgentFleetVisualizer;
