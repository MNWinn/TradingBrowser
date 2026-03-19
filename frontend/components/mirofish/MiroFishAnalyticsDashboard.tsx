'use client'

import React, { useState, useMemo } from 'react'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ScatterChart,
  Scatter,
  Cell,
} from 'recharts'
import { PredictionAccuracyChart } from './PredictionAccuracyChart'
import { SignalTimeline } from './SignalTimeline'
import { ConfidenceCalibration } from './ConfidenceCalibration'
import { MultiTimeframeAnalysis } from './MultiTimeframeAnalysis'
import { TickerPerformance } from './TickerPerformance'

// Types
export interface MiroFishSignal {
  id: string
  ticker: string
  timestamp: string
  prediction: 'LONG' | 'SHORT' | 'NEUTRAL'
  confidence: number
  timeframe: '1m' | '5m' | '15m' | '1h' | '1d' | '1w'
  actualOutcome?: 'CORRECT' | 'WRONG' | 'PENDING'
  actualReturn?: number
  priceAtSignal: number
  priceAtResolution?: number
}

export interface AccuracyMetrics {
  totalSignals: number
  correctPredictions: number
  wrongPredictions: number
  pendingPredictions: number
  winRate: number
  avgReturn: number
  avgConfidence: number
  sharpeRatio: number
}

// Mock data generator
const generateMockData = (): MiroFishSignal[] => {
  const tickers = ['AAPL', 'GOOGL', 'MSFT', 'TSLA', 'NVDA', 'AMZN', 'META', 'NFLX']
  const timeframes: ('1m' | '5m' | '15m' | '1h' | '1d' | '1w')[] = ['1m', '5m', '15m', '1h', '1d', '1w']
  const predictions: ('LONG' | 'SHORT' | 'NEUTRAL')[] = ['LONG', 'SHORT', 'NEUTRAL']
  
  const signals: MiroFishSignal[] = []
  const now = new Date()
  
  for (let i = 0; i < 500; i++) {
    const date = new Date(now.getTime() - Math.random() * 90 * 24 * 60 * 60 * 1000)
    const confidence = 0.5 + Math.random() * 0.5
    const isCorrect = Math.random() < (0.55 + confidence * 0.3)
    
    signals.push({
      id: `sig-${i}`,
      ticker: tickers[Math.floor(Math.random() * tickers.length)],
      timestamp: date.toISOString(),
      prediction: predictions[Math.floor(Math.random() * predictions.length)],
      confidence: parseFloat(confidence.toFixed(2)),
      timeframe: timeframes[Math.floor(Math.random() * timeframes.length)],
      actualOutcome: Math.random() > 0.2 ? (isCorrect ? 'CORRECT' : 'WRONG') : 'PENDING',
      actualReturn: isCorrect ? parseFloat((Math.random() * 5).toFixed(2)) : parseFloat((-Math.random() * 3).toFixed(2)),
      priceAtSignal: parseFloat((100 + Math.random() * 200).toFixed(2)),
    })
  }
  
  return signals.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
}

const mockSignals = generateMockData()

// Calculate metrics
const calculateMetrics = (signals: MiroFishSignal[]): AccuracyMetrics => {
  const resolved = signals.filter(s => s.actualOutcome !== 'PENDING')
  const correct = resolved.filter(s => s.actualOutcome === 'CORRECT')
  const wrong = resolved.filter(s => s.actualOutcome === 'WRONG')
  const returns = resolved.map(s => s.actualReturn || 0)
  
  const avgReturn = returns.length > 0 ? returns.reduce((a, b) => a + b, 0) / returns.length : 0
  const avgConfidence = signals.length > 0 ? signals.reduce((a, b) => a + b.confidence, 0) / signals.length : 0
  
  // Sharpe ratio calculation (simplified)
  const mean = avgReturn
  const variance = returns.length > 0 ? returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / returns.length : 0
  const stdDev = Math.sqrt(variance)
  const sharpeRatio = stdDev > 0 ? (mean / stdDev) * Math.sqrt(252) : 0
  
  return {
    totalSignals: signals.length,
    correctPredictions: correct.length,
    wrongPredictions: wrong.length,
    pendingPredictions: signals.filter(s => s.actualOutcome === 'PENDING').length,
    winRate: resolved.length > 0 ? (correct.length / resolved.length) * 100 : 0,
    avgReturn,
    avgConfidence,
    sharpeRatio,
  }
}

// Metric Card Component
const MetricCard = ({ title, value, subtitle, trend }: { title: string; value: string; subtitle?: string; trend?: 'up' | 'down' | 'neutral' }) => (
  <div className="card p-4">
    <div className="text-xs text-gray-500 uppercase tracking-wide">{title}</div>
    <div className="text-2xl font-bold mt-1">{value}</div>
    {subtitle && (
      <div className={`text-xs mt-1 ${trend === 'up' ? 'text-green-600' : trend === 'down' ? 'text-red-600' : 'text-gray-500'}`}>
        {subtitle}
      </div>
    )}
  </div>
)

// Time period options
const TIME_PERIODS = [
  { label: '7D', value: 7 },
  { label: '30D', value: 30 },
  { label: '90D', value: 90 },
  { label: '1Y', value: 365 },
]

export function MiroFishAnalyticsDashboard() {
  const [selectedPeriod, setSelectedPeriod] = useState(30)
  const [selectedTicker, setSelectedTicker] = useState<string>('ALL')
  const [activeTab, setActiveTab] = useState<'overview' | 'signals' | 'confidence' | 'timeframes' | 'tickers'>('overview')
  const [lastUpdate, setLastUpdate] = useState(new Date())

  // Filter signals based on period and ticker
  const filteredSignals = useMemo(() => {
    const cutoffDate = new Date()
    cutoffDate.setDate(cutoffDate.getDate() - selectedPeriod)
    
    return mockSignals.filter(signal => {
      const signalDate = new Date(signal.timestamp)
      const withinPeriod = signalDate >= cutoffDate
      const tickerMatch = selectedTicker === 'ALL' || signal.ticker === selectedTicker
      return withinPeriod && tickerMatch
    })
  }, [selectedPeriod, selectedTicker])

  const metrics = useMemo(() => calculateMetrics(filteredSignals), [filteredSignals])

  // Get unique tickers
  const tickers = useMemo(() => {
    const unique = new Set(mockSignals.map(s => s.ticker))
    return ['ALL', ...Array.from(unique).sort()]
  }, [])

  // Simulate real-time updates
  React.useEffect(() => {
    const interval = setInterval(() => {
      setLastUpdate(new Date())
    }, 30000)
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="space-y-4">
      {/* Header with controls */}
      <div className="card p-4">
        <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
          <div>
            <h1 className="text-xl font-bold">MiroFish Analytics</h1>
            <p className="text-sm text-gray-500">
              Last updated: {lastUpdate.toLocaleTimeString()}
              <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs bg-green-100 text-green-800">
                Live
              </span>
            </p>
          </div>
          
          <div className="flex flex-wrap items-center gap-3">
            {/* Time period selector */}
            <div className="flex items-center gap-1 bg-gray-100 rounded-lg p-1">
              {TIME_PERIODS.map(period => (
                <button
                  key={period.value}
                  onClick={() => setSelectedPeriod(period.value)}
                  className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                    selectedPeriod === period.value
                      ? 'bg-white text-black shadow-sm'
                      : 'text-gray-600 hover:text-black'
                  }`}
                >
                  {period.label}
                </button>
              ))}
            </div>
            
            {/* Ticker filter */}
            <select
              value={selectedTicker}
              onChange={(e) => setSelectedTicker(e.target.value)}
              className="px-3 py-1.5 text-sm border rounded-md bg-white"
            >
              {tickers.map(ticker => (
                <option key={ticker} value={ticker}>
                  {ticker === 'ALL' ? 'All Tickers' : ticker}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      {/* Metric Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          title="Win Rate"
          value={`${metrics.winRate.toFixed(1)}%`}
          subtitle={`${metrics.correctPredictions} / ${metrics.correctPredictions + metrics.wrongPredictions} resolved`}
          trend={metrics.winRate > 55 ? 'up' : metrics.winRate < 45 ? 'down' : 'neutral'}
        />
        <MetricCard
          title="Avg Return"
          value={`${metrics.avgReturn >= 0 ? '+' : ''}${metrics.avgReturn.toFixed(2)}%`}
          subtitle="Per signal"
          trend={metrics.avgReturn > 0 ? 'up' : metrics.avgReturn < 0 ? 'down' : 'neutral'}
        />
        <MetricCard
          title="Avg Confidence"
          value={`${(metrics.avgConfidence * 100).toFixed(0)}%`}
          subtitle="Model certainty"
          trend="neutral"
        />
        <MetricCard
          title="Sharpe Ratio"
          value={metrics.sharpeRatio.toFixed(2)}
          subtitle="Risk-adjusted return"
          trend={metrics.sharpeRatio > 1 ? 'up' : metrics.sharpeRatio < 0 ? 'down' : 'neutral'}
        />
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-200">
        <nav className="flex space-x-8">
          {[
            { id: 'overview', label: 'Overview' },
            { id: 'signals', label: 'Signal Timeline' },
            { id: 'confidence', label: 'Confidence Analysis' },
            { id: 'timeframes', label: 'Timeframe Analysis' },
            { id: 'tickers', label: 'Ticker Performance' },
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`py-2 px-1 text-sm font-medium border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-black text-black'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <div className="section-transition">
        {activeTab === 'overview' && (
          <div className="space-y-4">
            <PredictionAccuracyChart signals={filteredSignals} />
          </div>
        )}
        
        {activeTab === 'signals' && (
          <SignalTimeline signals={filteredSignals} />
        )}
        
        {activeTab === 'confidence' && (
          <ConfidenceCalibration signals={filteredSignals} />
        )}
        
        {activeTab === 'timeframes' && (
          <MultiTimeframeAnalysis signals={filteredSignals} />
        )}
        
        {activeTab === 'tickers' && (
          <TickerPerformance signals={filteredSignals} allSignals={mockSignals} />
        )}
      </div>
    </div>
  )
}
