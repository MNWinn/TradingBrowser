'use client'

import React, { useState, useMemo } from 'react'
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceDot,
  ComposedChart,
  Bar,
} from 'recharts'
import { MiroFishSignal } from './MiroFishAnalyticsDashboard'

interface TickerPerformanceProps {
  signals: MiroFishSignal[]
  allSignals: MiroFishSignal[]
}

interface TickerMetrics {
  ticker: string
  totalSignals: number
  correct: number
  wrong: number
  accuracy: number
  avgReturn: number
  totalReturn: number
  avgConfidence: number
  bestSignal: MiroFishSignal | null
  worstSignal: MiroFishSignal | null
  recentSignals: MiroFishSignal[]
}

// Generate mock price data
const generatePriceData = (ticker: string, signals: MiroFishSignal[]) => {
  const data: { timestamp: string; price: number; signal?: MiroFishSignal }[] = []
  const basePrice = 100 + Math.random() * 100
  
  // Generate 30 days of price data
  const now = new Date()
  for (let i = 30; i >= 0; i--) {
    const date = new Date(now.getTime() - i * 24 * 60 * 60 * 1000)
    const randomWalk = (Math.random() - 0.5) * 5
    const price = basePrice + randomWalk + (30 - i) * 0.5
    
    // Check if there's a signal on this date
    const signalOnDate = signals.find(s => {
      const signalDate = new Date(s.timestamp)
      return signalDate.toDateString() === date.toDateString()
    })
    
    data.push({
      timestamp: date.toISOString(),
      price: parseFloat(price.toFixed(2)),
      signal: signalOnDate,
    })
  }
  
  return data
}

export function TickerPerformance({ signals, allSignals }: TickerPerformanceProps) {
  const [selectedTicker, setSelectedTicker] = useState<string>('')

  // Get all unique tickers
  const tickers = useMemo(() => {
    const unique = new Set(allSignals.map(s => s.ticker))
    return Array.from(unique).sort()
  }, [allSignals])

  // Calculate metrics for each ticker
  const tickerMetrics = useMemo(() => {
    const metrics = new Map<string, TickerMetrics>()
    
    allSignals.forEach(signal => {
      if (!metrics.has(signal.ticker)) {
        metrics.set(signal.ticker, {
          ticker: signal.ticker,
          totalSignals: 0,
          correct: 0,
          wrong: 0,
          accuracy: 0,
          avgReturn: 0,
          totalReturn: 0,
          avgConfidence: 0,
          bestSignal: null,
          worstSignal: null,
          recentSignals: [],
        })
      }
      
      const m = metrics.get(signal.ticker)!
      m.totalSignals++
      
      if (signal.actualOutcome === 'CORRECT') m.correct++
      if (signal.actualOutcome === 'WRONG') m.wrong++
      
      if (signal.actualReturn !== undefined) {
        m.totalReturn += signal.actualReturn
        if (!m.bestSignal || signal.actualReturn > (m.bestSignal.actualReturn || 0)) {
          m.bestSignal = signal
        }
        if (!m.worstSignal || signal.actualReturn < (m.worstSignal.actualReturn || 0)) {
          m.worstSignal = signal
        }
      }
      
      m.avgConfidence += signal.confidence
      m.recentSignals.push(signal)
    })
    
    // Finalize calculations
    metrics.forEach(m => {
      const resolved = m.correct + m.wrong
      m.accuracy = resolved > 0 ? (m.correct / resolved) * 100 : 0
      m.avgReturn = m.totalReturn / m.totalSignals
      m.avgConfidence = (m.avgConfidence / m.totalSignals) * 100
      m.recentSignals = m.recentSignals
        .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime())
        .slice(0, 5)
    })
    
    return Array.from(metrics.values()).sort((a, b) => b.accuracy - a.accuracy)
  }, [allSignals])

  // Selected ticker metrics
  const selectedMetrics = useMemo(() => {
    if (!selectedTicker) return null
    return tickerMetrics.find(m => m.ticker === selectedTicker) || null
  }, [selectedTicker, tickerMetrics])

  // Price chart data for selected ticker
  const priceData = useMemo(() => {
    if (!selectedTicker) return []
    const tickerSignals = allSignals.filter(s => s.ticker === selectedTicker)
    return generatePriceData(selectedTicker, tickerSignals)
  }, [selectedTicker, allSignals])

  // Filtered signals for selected ticker
  const filteredSignals = useMemo(() => {
    if (!selectedTicker) return []
    return signals.filter(s => s.ticker === selectedTicker)
  }, [selectedTicker, signals])

  return (
    <div className="space-y-6">
      {/* Ticker Selector */}
      <div className="card p-4">
        <h3 className="text-sm font-semibold mb-3">Select Ticker for Deep Dive</h3>
        <div className="flex flex-wrap gap-2">
          {tickerMetrics.map(metric => (
            <button
              key={metric.ticker}
              onClick={() => setSelectedTicker(metric.ticker)}
              className={`px-3 py-2 rounded-lg text-sm font-medium transition-all ${
                selectedTicker === metric.ticker
                  ? 'bg-black text-white'
                  : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
              }`}
            >
              <span className="mr-2">{metric.ticker}</span>
              <span className={`text-xs ${
                metric.accuracy >= 60 ? 'text-green-400' : 
                metric.accuracy >= 45 ? 'text-yellow-400' : 'text-red-400'
              }`}>
                {metric.accuracy.toFixed(0)}%
              </span>
            </button>
          ))}
        </div>
      </div>

      {/* Selected Ticker Details */}
      {selectedMetrics && (
        <>
          {/* Metrics Cards */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="card p-4">
              <div className="text-xs text-gray-500 uppercase">Total Signals</div>
              <div className="text-2xl font-bold">{selectedMetrics.totalSignals}</div>
              <div className="text-xs text-gray-500 mt-1">
                {selectedMetrics.correct} correct · {selectedMetrics.wrong} wrong
              </div>
            </div>
            
            <div className="card p-4">
              <div className="text-xs text-gray-500 uppercase">Win Rate</div>
              <div className={`text-2xl font-bold ${
                selectedMetrics.accuracy >= 55 ? 'text-green-600' : 
                selectedMetrics.accuracy < 45 ? 'text-red-600' : ''
              }`}>
                {selectedMetrics.accuracy.toFixed(1)}%
              </div>
              <div className="text-xs text-gray-500 mt-1">
                Accuracy rating
              </div>
            </div>
            
            <div className="card p-4">
              <div className="text-xs text-gray-500 uppercase">Avg Return</div>
              <div className={`text-2xl font-bold ${
                selectedMetrics.avgReturn >= 0 ? 'text-green-600' : 'text-red-600'
              }`}>
                {selectedMetrics.avgReturn >= 0 ? '+' : ''}
                {selectedMetrics.avgReturn.toFixed(2)}%
              </div>
              <div className="text-xs text-gray-500 mt-1">
                Per signal
              </div>
            </div>
            
            <div className="card p-4">
              <div className="text-xs text-gray-500 uppercase">Total Return</div>
              <div className={`text-2xl font-bold ${
                selectedMetrics.totalReturn >= 0 ? 'text-green-600' : 'text-red-600'
              }`}>
                {selectedMetrics.totalReturn >= 0 ? '+' : ''}
                {selectedMetrics.totalReturn.toFixed(2)}%
              </div>
              <div className="text-xs text-gray-500 mt-1">
                Cumulative
              </div>
            </div>
          </div>

          {/* Price Chart with Signals */}
          <div className="card p-4">
            <h3 className="text-sm font-semibold mb-4">
              {selectedTicker} Price with MiroFish Signals
            </h3>
            <div className="h-80">
              <ResponsiveContainer width="100%" height="100%">
                <ComposedChart data={priceData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis 
                    dataKey="timestamp"
                    tick={{ fontSize: 10 }}
                    tickFormatter={(value) => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  />
                  <YAxis 
                    tick={{ fontSize: 10 }}
                    domain={['auto', 'auto']}
                    tickFormatter={(value) => `$${value}`}
                  />
                  <Tooltip 
                    formatter={(value: number) => [`$${value}`, 'Price']}
                    labelFormatter={(label) => new Date(label).toLocaleDateString()}
                  />
                  <Line 
                    type="monotone" 
                    dataKey="price" 
                    stroke="#111111" 
                    strokeWidth={2}
                    dot={false}
                  />
                  {/* Signal markers */}
                  {priceData.filter(d => d.signal).map((d, i) => (
                    <ReferenceDot
                      key={i}
                      x={d.timestamp}
                      y={d.price}
                      r={6}
                      fill={d.signal!.actualOutcome === 'CORRECT' ? '#22c55e' : 
                            d.signal!.actualOutcome === 'WRONG' ? '#ef4444' : '#9ca3af'}
                      stroke="#fff"
                      strokeWidth={2}
                    />
                  ))}
                </ComposedChart>
              </ResponsiveContainer>
            </div>
            <div className="flex items-center justify-center gap-4 mt-3 text-xs">
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded-full bg-green-500 border-2 border-white" />
                <span className="text-gray-600">Correct Signal</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded-full bg-red-500 border-2 border-white" />
                <span className="text-gray-600">Wrong Signal</span>
              </div>
              <div className="flex items-center gap-1">
                <div className="w-3 h-3 rounded-full bg-gray-400 border-2 border-white" />
                <span className="text-gray-600">Pending</span>
              </div>
            </div>
          </div>

          {/* Best and Worst Signals */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {selectedMetrics.bestSignal && (
              <div className="card p-4 bg-green-50 border-green-200">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-2xl">🏆</span>
                  <h3 className="font-semibold text-green-900">Best Signal</h3>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-green-700">Date:</span>
                    <span className="font-medium">{new Date(selectedMetrics.bestSignal.timestamp).toLocaleDateString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-green-700">Prediction:</span>
                    <span className={`font-medium ${
                      selectedMetrics.bestSignal.prediction === 'LONG' ? 'text-green-600' : 
                      selectedMetrics.bestSignal.prediction === 'SHORT' ? 'text-red-600' : ''
                    }`}>
                      {selectedMetrics.bestSignal.prediction}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-green-700">Confidence:</span>
                    <span className="font-medium">{(selectedMetrics.bestSignal.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-green-700">Return:</span>
                    <span className="font-bold text-green-600">
                      +{selectedMetrics.bestSignal.actualReturn?.toFixed(2)}%
                    </span>
                  </div>
                </div>
              </div>
            )}

            {selectedMetrics.worstSignal && (
              <div className="card p-4 bg-red-50 border-red-200">
                <div className="flex items-center gap-2 mb-3">
                  <span className="text-2xl">⚠️</span>
                  <h3 className="font-semibold text-red-900">Worst Signal</h3>
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-red-700">Date:</span>
                    <span className="font-medium">{new Date(selectedMetrics.worstSignal.timestamp).toLocaleDateString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-red-700">Prediction:</span>
                    <span className={`font-medium ${
                      selectedMetrics.worstSignal.prediction === 'LONG' ? 'text-green-600' : 
                      selectedMetrics.worstSignal.prediction === 'SHORT' ? 'text-red-600' : ''
                    }`}>
                      {selectedMetrics.worstSignal.prediction}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-red-700">Confidence:</span>
                    <span className="font-medium">{(selectedMetrics.worstSignal.confidence * 100).toFixed(0)}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-red-700">Return:</span>
                    <span className="font-bold text-red-600">
                      {selectedMetrics.worstSignal.actualReturn?.toFixed(2)}%
                    </span>
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* Recent Signals Table */}
          <div className="card p-4">
            <h3 className="text-sm font-semibold mb-4">Recent Signals for {selectedTicker}</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200">
                    <th className="text-left py-2 px-3 font-medium text-gray-600">Date</th>
                    <th className="text-left py-2 px-3 font-medium text-gray-600">Time</th>
                    <th className="text-left py-2 px-3 font-medium text-gray-600">Prediction</th>
                    <th className="text-right py-2 px-3 font-medium text-gray-600">Confidence</th>
                    <th className="text-left py-2 px-3 font-medium text-gray-600">TF</th>
                    <th className="text-center py-2 px-3 font-medium text-gray-600">Outcome</th>
                    <th className="text-right py-2 px-3 font-medium text-gray-600">Return</th>
                  </tr>
                </thead>
                <tbody>
                  {selectedMetrics.recentSignals.map(signal => (
                    <tr key={signal.id} className="border-b border-gray-100 hover:bg-gray-50">
                      <td className="py-2 px-3">
                        {new Date(signal.timestamp).toLocaleDateString()}
                      </td>
                      <td className="py-2 px-3">
                        {new Date(signal.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}
                      </td>
                      <td className="py-2 px-3">
                        <span className={`font-medium ${
                          signal.prediction === 'LONG' ? 'text-green-600' : 
                          signal.prediction === 'SHORT' ? 'text-red-600' : 'text-gray-600'
                        }`}>
                          {signal.prediction}
                        </span>
                      </td>
                      <td className="text-right py-2 px-3">
                        {(signal.confidence * 100).toFixed(0)}%
                      </td>
                      <td className="py-2 px-3">
                        <span className="text-xs bg-gray-100 px-2 py-0.5 rounded">
                          {signal.timeframe}
                        </span>
                      </td>
                      <td className="text-center py-2 px-3">
                        {signal.actualOutcome === 'PENDING' ? (
                          <span className="text-xs bg-gray-100 text-gray-600 px-2 py-0.5 rounded">Pending</span>
                        ) : signal.actualOutcome === 'CORRECT' ? (
                          <span className="text-xs bg-green-100 text-green-700 px-2 py-0.5 rounded">✓ Correct</span>
                        ) : (
                          <span className="text-xs bg-red-100 text-red-700 px-2 py-0.5 rounded">✗ Wrong</span>
                        )}
                      </td>
                      <td className={`text-right py-2 px-3 font-medium ${
                        signal.actualReturn && signal.actualReturn >= 0 ? 'text-green-600' : 
                        signal.actualReturn && signal.actualReturn < 0 ? 'text-red-600' : ''
                      }`}>
                        {signal.actualReturn !== undefined ? (
                          <>
                            {signal.actualReturn >= 0 ? '+' : ''}
                            {signal.actualReturn.toFixed(2)}%
                          </>
                        ) : (
                          '-'
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {/* All Tickers Summary Table */}
      {!selectedTicker && (
        <div className="card p-4">
          <h3 className="text-sm font-semibold mb-4">All Tickers Performance Summary</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="text-left py-3 px-3 font-medium text-gray-600">Ticker</th>
                  <th className="text-right py-3 px-3 font-medium text-gray-600">Signals</th>
                  <th className="text-right py-3 px-3 font-medium text-gray-600">Win Rate</th>
                  <th className="text-right py-3 px-3 font-medium text-gray-600">Avg Return</th>
                  <th className="text-right py-3 px-3 font-medium text-gray-600">Total Return</th>
                  <th className="text-right py-3 px-3 font-medium text-gray-600">Avg Confidence</th>
                  <th className="text-center py-3 px-3 font-medium text-gray-600">Action</th>
                </tr>
              </thead>
              <tbody>
                {tickerMetrics.map(metric => (
                  <tr key={metric.ticker} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-3 font-bold">{metric.ticker}</td>
                    <td className="text-right py-3 px-3">{metric.totalSignals}</td>
                    <td className={`text-right py-3 px-3 font-medium ${
                      metric.accuracy >= 60 ? 'text-green-600' : 
                      metric.accuracy < 40 ? 'text-red-600' : ''
                    }`}>
                      {metric.accuracy.toFixed(1)}%
                    </td>
                    <td className={`text-right py-3 px-3 ${
                      metric.avgReturn >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {metric.avgReturn >= 0 ? '+' : ''}{metric.avgReturn.toFixed(2)}%
                    </td>
                    <td className={`text-right py-3 px-3 font-medium ${
                      metric.totalReturn >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {metric.totalReturn >= 0 ? '+' : ''}{metric.totalReturn.toFixed(2)}%
                    </td>
                    <td className="text-right py-3 px-3">
                      {metric.avgConfidence.toFixed(1)}%
                    </td>
                    <td className="text-center py-3 px-3">
                      <button
                        onClick={() => setSelectedTicker(metric.ticker)}
                        className="text-xs bg-black text-white px-3 py-1.5 rounded hover:bg-gray-800 transition-colors"
                      >
                        View Details
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
