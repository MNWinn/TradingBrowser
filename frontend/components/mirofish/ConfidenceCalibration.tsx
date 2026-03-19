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
  ReferenceLine,
} from 'recharts'
import { MiroFishSignal } from './MiroFishAnalyticsDashboard'

interface ConfidenceCalibrationProps {
  signals: MiroFishSignal[]
}

export function ConfidenceCalibration({ signals }: ConfidenceCalibrationProps) {
  // Filter to only resolved signals
  const resolvedSignals = useMemo(() => 
    signals.filter(s => s.actualOutcome !== 'PENDING'),
  [signals])

  // Bucket predictions by confidence level
  const confidenceBuckets = useMemo(() => {
    const buckets = [
      { range: '50-60%', min: 0.5, max: 0.6, correct: 0, total: 0 },
      { range: '60-70%', min: 0.6, max: 0.7, correct: 0, total: 0 },
      { range: '70-80%', min: 0.7, max: 0.8, correct: 0, total: 0 },
      { range: '80-90%', min: 0.8, max: 0.9, correct: 0, total: 0 },
      { range: '90-100%', min: 0.9, max: 1.0, correct: 0, total: 0 },
    ]

    resolvedSignals.forEach(signal => {
      const bucket = buckets.find(b => signal.confidence >= b.min && signal.confidence < b.max)
      if (bucket) {
        bucket.total++
        if (signal.actualOutcome === 'CORRECT') bucket.correct++
      }
    })

    return buckets.map(b => ({
      ...b,
      expectedAccuracy: ((b.min + b.max) / 2) * 100,
      actualAccuracy: b.total > 0 ? (b.correct / b.total) * 100 : 0,
      sampleSize: b.total,
    }))
  }, [resolvedSignals])

  // Calibration curve data
  const calibrationCurve = useMemo(() => {
    // Create 10-point calibration curve
    const points = []
    for (let i = 5; i <= 95; i += 10) {
      const confidenceThreshold = i / 100
      const signalsAtConfidence = resolvedSignals.filter(s => 
        Math.abs(s.confidence - confidenceThreshold) < 0.05
      )
      
      if (signalsAtConfidence.length >= 3) {
        const correct = signalsAtConfidence.filter(s => s.actualOutcome === 'CORRECT').length
        points.push({
          confidence: i,
          actualAccuracy: (correct / signalsAtConfidence.length) * 100,
          sampleSize: signalsAtConfidence.length,
        })
      }
    }
    return points
  }, [resolvedSignals])

  // Calculate calibration error (ECE - Expected Calibration Error)
  const calibrationError = useMemo(() => {
    const totalSignals = confidenceBuckets.reduce((sum, b) => sum + b.sampleSize, 0)
    if (totalSignals === 0) return 0

    const ece = confidenceBuckets.reduce((sum, b) => {
      const weight = b.sampleSize / totalSignals
      return sum + weight * Math.abs(b.expectedAccuracy - b.actualAccuracy)
    }, 0)

    return ece
  }, [confidenceBuckets])

  // Determine if model is well-calibrated
  const isWellCalibrated = calibrationError < 5

  return (
    <div className="space-y-6">
      {/* Calibration Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="card p-4">
          <div className="text-xs text-gray-500 uppercase tracking-wide">Calibration Error (ECE)</div>
          <div className={`text-2xl font-bold mt-1 ${isWellCalibrated ? 'text-green-600' : 'text-yellow-600'}`}>
            {calibrationError.toFixed(1)}%
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {isWellCalibrated ? 'Well calibrated' : 'Needs calibration'}
          </div>
        </div>
        
        <div className="card p-4">
          <div className="text-xs text-gray-500 uppercase tracking-wide">Avg Confidence</div>
          <div className="text-2xl font-bold mt-1">
            {resolvedSignals.length > 0 
              ? `${(resolvedSignals.reduce((sum, s) => sum + s.confidence, 0) / resolvedSignals.length * 100).toFixed(1)}%`
              : 'N/A'
            }
          </div>
          <div className="text-xs text-gray-500 mt-1">
            Model's self-assessed accuracy
          </div>
        </div>
        
        <div className="card p-4">
          <div className="text-xs text-gray-500 uppercase tracking-wide">Actual Accuracy</div>
          <div className="text-2xl font-bold mt-1">
            {resolvedSignals.length > 0 
              ? `${(resolvedSignals.filter(s => s.actualOutcome === 'CORRECT').length / resolvedSignals.length * 100).toFixed(1)}%`
              : 'N/A'
            }
          </div>
          <div className="text-xs text-gray-500 mt-1">
            True prediction accuracy
          </div>
        </div>
      </div>

      {/* Bar Chart - Accuracy by Confidence Bucket */}
      <div className="card p-4">
        <h3 className="text-sm font-semibold mb-4">Actual Accuracy by Confidence Level</h3>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={confidenceBuckets} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis 
                dataKey="range" 
                tick={{ fontSize: 11 }}
                label={{ value: 'Confidence Range', position: 'insideBottom', offset: -5, fontSize: 12 }}
              />
              <YAxis 
                tick={{ fontSize: 11 }}
                domain={[0, 100]}
                tickFormatter={(value) => `${value}%`}
              />
              <Tooltip 
                formatter={(value: number, name: string) => {
                  if (name === 'actualAccuracy') return [`${value.toFixed(1)}%`, 'Actual Accuracy']
                  if (name === 'expectedAccuracy') return [`${value.toFixed(1)}%`, 'Expected Accuracy']
                  return [value, name]
                }}
                labelFormatter={(label) => `Confidence: ${label}`}
              />
              <ReferenceLine y={50} stroke="#ef4444" strokeDasharray="3 3" />
              
              {/* Expected accuracy line */}
              <Bar 
                dataKey="expectedAccuracy" 
                fill="#e5e7eb" 
                name="Expected Accuracy"
                radius={[4, 4, 0, 0]}
              />
              
              {/* Actual accuracy bars */}
              <Bar 
                dataKey="actualAccuracy" 
                fill="#111111" 
                name="Actual Accuracy"
                radius={[4, 4, 0, 0]}
              >
                {confidenceBuckets.map((entry, index) => (
                  <cell 
                    key={`cell-${index}`}
                    style={{
                      fill: Math.abs(entry.actualAccuracy - entry.expectedAccuracy) < 10 ? '#22c55e' : '#ef4444'
                    }}
                  />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="flex items-center justify-center gap-4 mt-3 text-xs">
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-gray-200 rounded" />
            <span className="text-gray-600">Expected (if well-calibrated)</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-green-500 rounded" />
            <span className="text-gray-600">Actual (well-calibrated)</span>
          </div>
          <div className="flex items-center gap-1">
            <div className="w-3 h-3 bg-red-500 rounded" />
            <span className="text-gray-600">Actual (miscalibrated)</span>
          </div>
        </div>
      </div>

      {/* Calibration Curve */}
      <div className="card p-4">
        <h3 className="text-sm font-semibold mb-4">Calibration Curve</h3>
        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart margin={{ top: 20, right: 30, left: 20, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis 
                type="number"
                dataKey="confidence"
                domain={[50, 100]}
                tick={{ fontSize: 11 }}
                tickFormatter={(value) => `${value}%`}
                label={{ value: 'Predicted Confidence', position: 'insideBottom', offset: -10, fontSize: 12 }}
              />
              <YAxis 
                type="number"
                dataKey="actualAccuracy"
                domain={[0, 100]}
                tick={{ fontSize: 11 }}
                tickFormatter={(value) => `${value}%`}
                label={{ value: 'Actual Accuracy', angle: -90, position: 'insideLeft', fontSize: 12 }}
              />
              <Tooltip 
                formatter={(value: number, name: string) => {
                  if (name === 'actualAccuracy') return [`${value.toFixed(1)}%`, 'Actual Accuracy']
                  return [`${value}%`, 'Perfect Calibration']
                }}
                labelFormatter={(label) => `Confidence: ${label}%`}
              />
              
              {/* Perfect calibration diagonal */}
              <ReferenceLine 
                segment={[{ x: 50, y: 50 }, { x: 100, y: 100 }]} 
                stroke="#22c55e" 
                strokeDasharray="5 5"
                strokeWidth={2}
              />
              
              {/* Actual calibration curve */}
              <Line
                data={calibrationCurve}
                type="monotone"
                dataKey="actualAccuracy"
                stroke="#111111"
                strokeWidth={2}
                dot={{ fill: '#111111', r: 4 }}
                activeDot={{ r: 6 }}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="text-xs text-gray-500 mt-3">
          The green dashed line represents perfect calibration (predicted confidence = actual accuracy). 
          The black line shows the model's actual calibration. Points closer to the diagonal indicate better calibration.
        </p>
      </div>

      {/* Bucket Details Table */}
      <div className="card p-4">
        <h3 className="text-sm font-semibold mb-4">Confidence Bucket Details</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-2 px-3 font-medium text-gray-600">Confidence Range</th>
                <th className="text-right py-2 px-3 font-medium text-gray-600">Signals</th>
                <th className="text-right py-2 px-3 font-medium text-gray-600">Correct</th>
                <th className="text-right py-2 px-3 font-medium text-gray-600">Wrong</th>
                <th className="text-right py-2 px-3 font-medium text-gray-600">Actual Accuracy</th>
                <th className="text-right py-2 px-3 font-medium text-gray-600">Expected</th>
                <th className="text-right py-2 px-3 font-medium text-gray-600">Difference</th>
              </tr>
            </thead>
            <tbody>
              {confidenceBuckets.map((bucket, index) => {
                const difference = bucket.actualAccuracy - bucket.expectedAccuracy
                return (
                  <tr key={index} className="border-b border-gray-100 hover:bg-gray-50">
                    <td className="py-2 px-3 font-medium">{bucket.range}</td>
                    <td className="text-right py-2 px-3">{bucket.sampleSize}</td>
                    <td className="text-right py-2 px-3 text-green-600">{bucket.correct}</td>
                    <td className="text-right py-2 px-3 text-red-600">{bucket.total - bucket.correct}</td>
                    <td className="text-right py-2 px-3 font-medium">
                      {bucket.sampleSize > 0 ? `${bucket.actualAccuracy.toFixed(1)}%` : 'N/A'}
                    </td>
                    <td className="text-right py-2 px-3 text-gray-500">
                      {bucket.expectedAccuracy.toFixed(1)}%
                    </td>
                    <td className={`text-right py-2 px-3 font-medium ${
                      Math.abs(difference) < 10 ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {bucket.sampleSize > 0 ? `${difference >= 0 ? '+' : ''}${difference.toFixed(1)}%` : 'N/A'}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Interpretation */}
      <div className="card p-4 bg-blue-50 border-blue-200">
        <h3 className="text-sm font-semibold mb-2 text-blue-900">How to Read This</h3>
        <ul className="text-sm text-blue-800 space-y-1 list-disc list-inside">
          <li><strong>Well-calibrated model:</strong> When the model says it's 70% confident, it should be correct ~70% of the time.</li>
          <li><strong>Overconfident:</strong> Model predicts high confidence but actual accuracy is lower (common issue).</li>
          <li><strong>Underconfident:</strong> Model predicts low confidence but actual accuracy is higher (less common).</li>
          <li><strong>ECE (Expected Calibration Error):</strong> Lower is better. Under 5% is considered well-calibrated.</li>
        </ul>
      </div>
    </div>
  )
}
