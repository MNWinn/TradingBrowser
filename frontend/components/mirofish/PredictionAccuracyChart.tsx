'use client'

import React, { useMemo } from 'react'
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
  ReferenceLine,
} from 'recharts'
import { MiroFishSignal } from './MiroFishAnalyticsDashboard'

interface PredictionAccuracyChartProps {
  signals: MiroFishSignal[]
}

export function PredictionAccuracyChart({ signals }: PredictionAccuracyChartProps) {
  // 1. Accuracy over time (line chart data)
  const accuracyOverTime = useMemo(() => {
    const resolvedSignals = signals.filter(s => s.actualOutcome !== 'PENDING')
    
    // Group by date
    const byDate = new Map<string, { correct: number; total: number }>()
    
    resolvedSignals.forEach(signal => {
      const date = new Date(signal.timestamp).toISOString().split('T')[0]
      const current = byDate.get(date) || { correct: 0, total: 0 }
      current.total++
      if (signal.actualOutcome === 'CORRECT') current.correct++
      byDate.set(date, current)
    })
    
    return Array.from(byDate.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([date, stats]) => ({
        date,
        accuracy: stats.total > 0 ? (stats.correct / stats.total) * 100 : 0,
        total: stats.total,
      }))
  }, [signals])

  // 2. Accuracy by ticker (bar chart data)
  const accuracyByTicker = useMemo(() => {
    const byTicker = new Map<string, { correct: number; total: number; ticker: string }>()
    
    signals.filter(s => s.actualOutcome !== 'PENDING').forEach(signal => {
      const current = byTicker.get(signal.ticker) || { correct: 0, total: 0, ticker: signal.ticker }
      current.total++
      if (signal.actualOutcome === 'CORRECT') current.correct++
      byTicker.set(signal.ticker, current)
    })
    
    return Array.from(byTicker.values())
      .map(t => ({
        ...t,
        accuracy: t.total > 0 ? (t.correct / t.total) * 100 : 0,
      }))
      .sort((a, b) => b.accuracy - a.accuracy)
  }, [signals])

  // 3. Heat map data (accuracy by hour and day)
  const heatMapData = useMemo(() => {
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']
    const hours = Array.from({ length: 24 }, (_, i) => i)
    
    const grid: { day: string; hour: number; accuracy: number; count: number }[] = []
    
    days.forEach((day, dayIndex) => {
      hours.forEach(hour => {
        const hourSignals = signals.filter(s => {
          const date = new Date(s.timestamp)
          return date.getDay() === dayIndex && date.getHours() === hour && s.actualOutcome !== 'PENDING'
        })
        
        const correct = hourSignals.filter(s => s.actualOutcome === 'CORRECT').length
        const accuracy = hourSignals.length > 0 ? (correct / hourSignals.length) * 100 : 0
        
        grid.push({
          day,
          hour,
          accuracy,
          count: hourSignals.length,
        })
      })
    })
    
    return { days, hours, grid }
  }, [signals])

  // 4. Confidence vs Actual Accuracy (scatter plot data)
  const confidenceVsAccuracy = useMemo(() => {
    // Bucket by confidence ranges
    const buckets = new Map<string, { min: number; max: number; correct: number; total: number }>()
    
    for (let i = 0; i < 10; i++) {
      const min = i * 0.1
      const max = (i + 1) * 0.1
      buckets.set(`${min}-${max}`, { min, max, correct: 0, total: 0 })
    }
    
    signals.filter(s => s.actualOutcome !== 'PENDING').forEach(signal => {
      const bucketIndex = Math.min(Math.floor(signal.confidence * 10), 9)
      const key = `${bucketIndex * 0.1}-${(bucketIndex + 1) * 0.1}`
      const bucket = buckets.get(key)!
      bucket.total++
      if (signal.actualOutcome === 'CORRECT') bucket.correct++
    })
    
    return Array.from(buckets.values())
      .filter(b => b.total > 0)
      .map(b => ({
        confidence: (b.min + b.max) / 2 * 100,
        actualAccuracy: (b.correct / b.total) * 100,
        count: b.total,
      }))
  }, [signals])

  // Color scale for heat map
  const getHeatColor = (accuracy: number, count: number) => {
    if (count === 0) return '#f3f4f6'
    if (accuracy >= 70) return '#22c55e'
    if (accuracy >= 55) return '#84cc16'
    if (accuracy >= 45) return '#eab308'
    if (accuracy >= 30) return '#f97316'
    return '#ef4444'
  }

  return (
    <div className="space-y-6">
      {/* Row 1: Line Chart and Bar Chart */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Accuracy Over Time */}
        <div className="card p-4">
          <h3 className="text-sm font-semibold mb-4">Accuracy Over Time</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={accuracyOverTime}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis 
                  dataKey="date" 
                  tick={{ fontSize: 10 }}
                  tickFormatter={(value) => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                />
                <YAxis 
                  tick={{ fontSize: 10 }}
                  domain={[0, 100]}
                  tickFormatter={(value) => `${value}%`}
                />
                <Tooltip 
                  formatter={(value: number) => [`${value.toFixed(1)}%`, 'Accuracy']}
                  labelFormatter={(label) => new Date(label).toLocaleDateString()}
                />
                <ReferenceLine y={50} stroke="#ef4444" strokeDasharray="3 3" />
                <Line 
                  type="monotone" 
                  dataKey="accuracy" 
                  stroke="#111111" 
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Accuracy by Ticker */}
        <div className="card p-4">
          <h3 className="text-sm font-semibold mb-4">Accuracy by Ticker</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={accuracyByTicker} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis 
                  type="number" 
                  domain={[0, 100]}
                  tickFormatter={(value) => `${value}%`}
                  tick={{ fontSize: 10 }}
                />
                <YAxis 
                  type="category" 
                  dataKey="ticker" 
                  tick={{ fontSize: 10 }}
                  width={50}
                />
                <Tooltip formatter={(value: number) => [`${value.toFixed(1)}%`, 'Accuracy']} />
                <Bar dataKey="accuracy" fill="#111111" radius={[0, 4, 4, 0]}>
                  {accuracyByTicker.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={entry.accuracy >= 60 ? '#22c55e' : entry.accuracy >= 45 ? '#eab308' : '#ef4444'}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Row 2: Heat Map and Scatter Plot */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Heat Map - Accuracy by Time */}
        <div className="card p-4">
          <h3 className="text-sm font-semibold mb-4">Accuracy Heat Map (Day/Hour)</h3>
          <div className="h-64 overflow-x-auto">
            <div className="min-w-[600px]">
              {/* Header row with hours */}
              <div className="flex">
                <div className="w-12 text-xs text-gray-500"></div>
                {heatMapData.hours.filter(h => h % 3 === 0).map(hour => (
                  <div key={hour} className="flex-1 text-center text-xs text-gray-500">
                    {hour}:00
                  </div>
                ))}
              </div>
              
              {/* Grid rows */}
              {heatMapData.days.map(day => (
                <div key={day} className="flex items-center">
                  <div className="w-12 text-xs text-gray-500">{day}</div>
                  <div className="flex flex-1">
                    {heatMapData.hours.filter(h => h % 3 === 0).map(hour => {
                      // Average accuracy for this 3-hour block
                      const blockData = heatMapData.grid.filter(
                        g => g.day === day && g.hour >= hour && g.hour < hour + 3
                      )
                      const totalCount = blockData.reduce((sum, d) => sum + d.count, 0)
                      const avgAccuracy = totalCount > 0 
                        ? blockData.reduce((sum, d) => sum + d.accuracy * d.count, 0) / totalCount 
                        : 0
                      
                      return (
                        <div
                          key={`${day}-${hour}`}
                          className="flex-1 h-8 m-0.5 rounded flex items-center justify-center text-xs"
                          style={{ 
                            backgroundColor: getHeatColor(avgAccuracy, totalCount),
                            color: avgAccuracy > 50 ? 'white' : 'black',
                            opacity: totalCount === 0 ? 0.3 : 1
                          }}
                          title={`${day} ${hour}:00-${hour+3}:00 - Accuracy: ${avgAccuracy.toFixed(1)}% (${totalCount} signals)`}
                        >
                          {totalCount > 0 && avgAccuracy.toFixed(0)}
                        </div>
                      )
                    })}
                  </div>
                </div>
              ))}
              
              {/* Legend */}
              <div className="flex items-center gap-2 mt-3 text-xs">
                <span className="text-gray-500">Low</span>
                {['#ef4444', '#f97316', '#eab308', '#84cc16', '#22c55e'].map((color, i) => (
                  <div key={i} className="w-4 h-4 rounded" style={{ backgroundColor: color }} />
                ))}
                <span className="text-gray-500">High</span>
              </div>
            </div>
          </div>
        </div>

        {/* Confidence vs Actual Accuracy Scatter */}
        <div className="card p-4">
          <h3 className="text-sm font-semibold mb-4">Confidence vs Actual Accuracy</h3>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis 
                  type="number" 
                  dataKey="confidence" 
                  name="Confidence"
                  domain={[0, 100]}
                  tickFormatter={(value) => `${value}%`}
                  tick={{ fontSize: 10 }}
                />
                <YAxis 
                  type="number" 
                  dataKey="actualAccuracy" 
                  name="Actual Accuracy"
                  domain={[0, 100]}
                  tickFormatter={(value) => `${value}%`}
                  tick={{ fontSize: 10 }}
                />
                <Tooltip 
                  cursor={{ strokeDasharray: '3 3' }}
                  formatter={(value: number, name: string) => [
                    name === 'confidence' ? `${value.toFixed(0)}%` : `${value.toFixed(1)}%`,
                    name === 'confidence' ? 'Predicted Confidence' : 'Actual Accuracy'
                  ]}
                  labelFormatter={(_, payload) => {
                    if (payload && payload[0]) {
                      return `${payload[0].payload.count} signals`
                    }
                    return ''
                  }}
                />
                <ReferenceLine x={50} stroke="#ef4444" strokeDasharray="3 3" />
                <ReferenceLine y={50} stroke="#ef4444" strokeDasharray="3 3" />
                <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 100, y: 100 }]} stroke="#22c55e" strokeDasharray="3 3" />
                <Scatter data={confidenceVsAccuracy} fill="#111111">
                  {confidenceVsAccuracy.map((entry, index) => (
                    <Cell 
                      key={`cell-${index}`} 
                      fill={Math.abs(entry.confidence - entry.actualAccuracy) < 10 ? '#22c55e' : '#ef4444'}
                    />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <p className="text-xs text-gray-500 mt-2">
            Green dots = well-calibrated, Red dots = miscalibrated. Diagonal line = perfect calibration.
          </p>
        </div>
      </div>
    </div>
  )
}
