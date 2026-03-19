'use client'

import React, { useMemo } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  LineChart,
  Line,
  Legend,
} from 'recharts'
import { MiroFishSignal } from './MiroFishAnalyticsDashboard'

interface MultiTimeframeAnalysisProps {
  signals: MiroFishSignal[]
}

const TIMEFRAMES: ('1m' | '5m' | '15m' | '1h' | '1d' | '1w')[] = ['1m', '5m', '15m', '1h', '1d', '1w']

export function MultiTimeframeAnalysis({ signals }: MultiTimeframeAnalysisProps) {
  // Calculate metrics for each timeframe
  const timeframeMetrics = useMemo(() => {
    return TIMEFRAMES.map(timeframe => {
      const tfSignals = signals.filter(s => s.timeframe === timeframe && s.actualOutcome !== 'PENDING')
      
      if (tfSignals.length === 0) {
        return {
          timeframe,
          totalSignals: 0,
          accuracy: 0,
          avgReturn: 0,
          avgConfidence: 0,
          sharpeRatio: 0,
          sampleSize: 0,
        }
      }

      const correct = tfSignals.filter(s => s.actualOutcome === 'CORRECT').length
      const returns = tfSignals.map(s => s.actualReturn || 0)
      const avgReturn = returns.reduce((a, b) => a + b, 0) / returns.length
      const avgConfidence = tfSignals.reduce((sum, s) => sum + s.confidence, 0) / tfSignals.length

      // Sharpe ratio
      const mean = avgReturn
      const variance = returns.reduce((sum, r) => sum + Math.pow(r - mean, 2), 0) / returns.length
      const stdDev = Math.sqrt(variance)
      const sharpeRatio = stdDev > 0 ? (mean / stdDev) * Math.sqrt(252) : 0

      return {
        timeframe,
        totalSignals: tfSignals.length,
        accuracy: (correct / tfSignals.length) * 100,
        avgReturn,
        avgConfidence: avgConfidence * 100,
        sharpeRatio,
        sampleSize: tfSignals.length,
      }
    })
  }, [signals])

  // Find best timeframe
  const bestTimeframe = useMemo(() => {
    const validMetrics = timeframeMetrics.filter(m => m.sampleSize >= 5)
    if (validMetrics.length === 0) return null
    
    return validMetrics.reduce((best, current) => 
      current.accuracy > best.accuracy ? current : best
    )
  }, [timeframeMetrics])

  // Alignment analysis - check if multiple timeframes agree
  const alignmentData = useMemo(() => {
    // Group signals by ticker and approximate time window (within 1 hour)
    const groups = new Map<string, MiroFishSignal[]>()
    
    signals.forEach(signal => {
      const date = new Date(signal.timestamp)
      const hourKey = `${signal.ticker}-${date.toISOString().split('T')[0]}-${date.getHours()}`
      const current = groups.get(hourKey) || []
      current.push(signal)
      groups.set(hourKey, current)
    })

    // Analyze alignment within each group
    let alignedSignals = 0
    let alignedCorrect = 0
    let misalignedSignals = 0
    let misalignedCorrect = 0

    groups.forEach(group => {
      if (group.length < 2) return

      // Check if predictions align
      const predictions = group.map(s => s.prediction)
      const longCount = predictions.filter(p => p === 'LONG').length
      const shortCount = predictions.filter(p => p === 'SHORT').length
      const neutralCount = predictions.filter(p => p === 'NEUTRAL').length

      const isAligned = longCount === group.length || 
                        shortCount === group.length || 
                        neutralCount === group.length

      // Check if at least one signal is resolved
      const resolvedSignals = group.filter(s => s.actualOutcome !== 'PENDING')
      if (resolvedSignals.length === 0) return

      const correctCount = resolvedSignals.filter(s => s.actualOutcome === 'CORRECT').length
      const accuracy = correctCount / resolvedSignals.length

      if (isAligned) {
        alignedSignals += resolvedSignals.length
        alignedCorrect += correctCount
      } else {
        misalignedSignals += resolvedSignals.length
        misalignedCorrect += correctCount
      }
    })

    return {
      aligned: {
        total: alignedSignals,
        correct: alignedCorrect,
        accuracy: alignedSignals > 0 ? (alignedCorrect / alignedSignals) * 100 : 0,
      },
      misaligned: {
        total: misalignedSignals,
        correct: misalignedCorrect,
        accuracy: misalignedSignals > 0 ? (misalignedCorrect / misalignedSignals) * 100 : 0,
      },
    }
  }, [signals])

  // Chart data for comparison
  const chartData = timeframeMetrics.map(m => ({
    timeframe: m.timeframe,
    accuracy: m.accuracy,
    avgReturn: m.avgReturn,
    confidence: m.avgConfidence,
    sharpe: m.sharpeRatio,
  }))

  return (
    <div className="space-y-6">
      {/* Best Timeframe Banner */}
      {bestTimeframe && (
        <div className="card p-4 bg-green-50 border-green-200">
          <div className="flex items-center gap-3">
            <div className="text-2xl">🏆</div>
            <div>
              <h3 className="font-semibold text-green-900">
                Best Performing Timeframe: {bestTimeframe.timeframe}
              </h3>
              <p className="text-sm text-green-700">
                {bestTimeframe.accuracy.toFixed(1)}% accuracy · {bestTimeframe.avgReturn.toFixed(2)}% avg return · {bestTimeframe.totalSignals} signals
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Timeframe Comparison Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Accuracy by Timeframe */}
        <div className="card p-4">
          <h3 className="text-sm font-semibold mb-4">Accuracy by Timeframe</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="timeframe" tick={{ fontSize: 11 }} />
                <YAxis 
                  tick={{ fontSize: 11 }}
                  domain={[0, 100]}
                  tickFormatter={(value) => `${value}%`}
                />
                <Tooltip formatter={(value: number) => [`${value.toFixed(1)}%`, 'Accuracy']} />
                <Bar dataKey="accuracy" fill="#111111" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry, index) => (
                    <cell 
                      key={`cell-${index}`}
                      style={{
                        fill: entry.accuracy >= 60 ? '#22c55e' : entry.accuracy >= 45 ? '#eab308' : '#ef4444'
                      }}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Average Return by Timeframe */}
        <div className="card p-4">
          <h3 className="text-sm font-semibold mb-4">Average Return by Timeframe</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="timeframe" tick={{ fontSize: 11 }} />
                <YAxis 
                  tick={{ fontSize: 11 }}
                  tickFormatter={(value) => `${value}%`}
                />
                <Tooltip formatter={(value: number) => [`${value.toFixed(2)}%`, 'Avg Return']} />
                <Bar dataKey="avgReturn" radius={[4, 4, 0, 0]}>
                  {chartData.map((entry, index) => (
                    <cell 
                      key={`cell-${index}`}
                      style={{
                        fill: entry.avgReturn >= 0 ? '#22c55e' : '#ef4444'
                      }}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Detailed Metrics Table */}
      <div className="card p-4">
        <h3 className="text-sm font-semibold mb-4">Timeframe Performance Metrics</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-3 px-3 font-medium text-gray-600">Timeframe</th>
                <th className="text-right py-3 px-3 font-medium text-gray-600">Signals</th>
                <th className="text-right py-3 px-3 font-medium text-gray-600">Accuracy</th>
                <th className="text-right py-3 px-3 font-medium text-gray-600">Avg Return</th>
                <th className="text-right py-3 px-3 font-medium text-gray-600">Avg Confidence</th>
                <th className="text-right py-3 px-3 font-medium text-gray-600">Sharpe Ratio</th>
                <th className="text-center py-3 px-3 font-medium text-gray-600">Rating</th>
              </tr>
            </thead>
            <tbody>
              {timeframeMetrics.map((metric, index) => {
                const rating = metric.accuracy >= 60 ? 'A' : 
                              metric.accuracy >= 50 ? 'B' : 
                              metric.accuracy >= 40 ? 'C' : 'D'
                const ratingColor = rating === 'A' ? 'text-green-600 bg-green-100' :
                                   rating === 'B' ? 'text-blue-600 bg-blue-100' :
                                   rating === 'C' ? 'text-yellow-600 bg-yellow-100' : 'text-red-600 bg-red-100'
                
                return (
                  <tr key={metric.timeframe} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-3 px-3 font-medium">{metric.timeframe}</td>
                    <td className="text-right py-3 px-3">{metric.totalSignals}</td>
                    <td className={`text-right py-3 px-3 font-medium ${
                      metric.accuracy >= 55 ? 'text-green-600' : metric.accuracy < 45 ? 'text-red-600' : ''
                    }`}>
                      {metric.sampleSize > 0 ? `${metric.accuracy.toFixed(1)}%` : 'N/A'}
                    </td>
                    <td className={`text-right py-3 px-3 ${
                      metric.avgReturn >= 0 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {metric.sampleSize > 0 ? `${metric.avgReturn >= 0 ? '+' : ''}${metric.avgReturn.toFixed(2)}%` : 'N/A'}
                    </td>
                    <td className="text-right py-3 px-3">
                      {metric.sampleSize > 0 ? `${metric.avgConfidence.toFixed(1)}%` : 'N/A'}
                    </td>
                    <td className="text-right py-3 px-3">
                      {metric.sampleSize > 0 ? metric.sharpeRatio.toFixed(2) : 'N/A'}
                    </td>
                    <td className="text-center py-3 px-3">
                      {metric.sampleSize > 0 ? (
                        <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-sm font-bold ${ratingColor}`}>
                          {rating}
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Alignment Analysis */}
      <div className="card p-4">
        <h3 className="text-sm font-semibold mb-4">Multi-Timeframe Alignment Analysis</h3>
        <p className="text-sm text-gray-600 mb-4">
          Do signals perform better when multiple timeframes agree on the same direction?
        </p>
        
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className={`p-4 rounded-lg ${alignmentData.aligned.accuracy > alignmentData.misaligned.accuracy ? 'bg-green-50' : 'bg-gray-50'}`}>
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium">Aligned Signals</span>
              <span className="text-2xl">🎯</span>
            </div>
            <div className="text-3xl font-bold">
              {alignmentData.aligned.total > 0 ? `${alignmentData.aligned.accuracy.toFixed(1)}%` : 'N/A'}
            </div>
            <div className="text-sm text-gray-600 mt-1">
              {alignmentData.aligned.correct} / {alignmentData.aligned.total} correct
            </div>
            <div className="text-xs text-gray-500 mt-2">
              Multiple timeframes predicting the same direction
            </div>
          </div>

          <div className={`p-4 rounded-lg ${alignmentData.misaligned.accuracy > alignmentData.aligned.accuracy ? 'bg-green-50' : 'bg-gray-50'}`}>
            <div className="flex items-center justify-between mb-2">
              <span className="font-medium">Misaligned Signals</span>
              <span className="text-2xl">⚡</span>
            </div>
            <div className="text-3xl font-bold">
              {alignmentData.misaligned.total > 0 ? `${alignmentData.misaligned.accuracy.toFixed(1)}%` : 'N/A'}
            </div>
            <div className="text-sm text-gray-600 mt-1">
              {alignmentData.misaligned.correct} / {alignmentData.misaligned.total} correct
            </div>
            <div className="text-xs text-gray-500 mt-2">
              Timeframes disagree on direction
            </div>
          </div>
        </div>

        {alignmentData.aligned.total > 0 && alignmentData.misaligned.total > 0 && (
          <div className="mt-4 p-3 bg-blue-50 rounded-lg text-sm text-blue-800">
            {alignmentData.aligned.accuracy > alignmentData.misaligned.accuracy ? (
              <>
                <strong>💡 Insight:</strong> Aligned signals perform 
                <strong> {(alignmentData.aligned.accuracy - alignmentData.misaligned.accuracy).toFixed(1)} percentage points better</strong> than misaligned ones. 
                Consider waiting for multiple timeframe confirmation before trading.
              </>
            ) : alignmentData.misaligned.accuracy > alignmentData.aligned.accuracy ? (
              <>
                <strong>💡 Insight:</strong> Interestingly, misaligned signals perform better. 
                This could indicate that short-term signals are more reliable than long-term consensus.
              </>
            ) : (
              <>
                <strong>💡 Insight:</strong> Alignment doesn't seem to significantly affect accuracy in this dataset.
              </>
            )}
          </div>
        )}
      </div>

      {/* Recommendations */}
      <div className="card p-4 bg-gray-50">
        <h3 className="text-sm font-semibold mb-3">Timeframe Recommendations</h3>
        <ul className="space-y-2 text-sm">
          {bestTimeframe && (
            <li className="flex items-start gap-2">
              <span className="text-green-600">✓</span>
              <span>
                Focus on <strong>{bestTimeframe.timeframe}</strong> timeframe for best accuracy ({bestTimeframe.accuracy.toFixed(1)}%)
              </span>
            </li>
          )}
          {alignmentData.aligned.accuracy > alignmentData.misaligned.accuracy + 5 && (
            <li className="flex items-start gap-2">
              <span className="text-green-600">✓</span>
              <span>
                Wait for <strong>multi-timeframe alignment</strong> before entering positions (+{(alignmentData.aligned.accuracy - alignmentData.misaligned.accuracy).toFixed(1)}% accuracy)
              </span>
            </li>
          )}
          {timeframeMetrics.some(m => m.sharpeRatio > 1.5) && (
            <li className="flex items-start gap-2">
              <span className="text-green-600">✓</span>
              <span>
                {timeframeMetrics.find(m => m.sharpeRatio > 1.5)?.timeframe} timeframe shows excellent risk-adjusted returns (Sharpe {'>'} 1.5)
              </span>
            </li>
          )}
        </ul>
      </div>
    </div>
  )
}
