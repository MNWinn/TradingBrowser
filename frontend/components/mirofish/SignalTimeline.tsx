'use client'

import React, { useState, useMemo } from 'react'
import { MiroFishSignal } from './MiroFishAnalyticsDashboard'

interface SignalTimelineProps {
  signals: MiroFishSignal[]
}

type SignalType = 'ALL' | 'LONG' | 'SHORT' | 'NEUTRAL'

export function SignalTimeline({ signals }: SignalTimelineProps) {
  const [filterType, setFilterType] = useState<SignalType>('ALL')
  const [selectedSignal, setSelectedSignal] = useState<MiroFishSignal | null>(null)

  const filteredSignals = useMemo(() => {
    if (filterType === 'ALL') return signals
    return signals.filter(s => s.prediction === filterType)
  }, [signals, filterType])

  const getSignalColor = (signal: MiroFishSignal) => {
    if (signal.actualOutcome === 'PENDING') return 'bg-gray-400'
    if (signal.actualOutcome === 'CORRECT') return 'bg-green-500'
    return 'bg-red-500'
  }

  const getSignalBorderColor = (signal: MiroFishSignal) => {
    if (signal.actualOutcome === 'PENDING') return 'border-gray-400'
    if (signal.actualOutcome === 'CORRECT') return 'border-green-500'
    return 'border-red-500'
  }

  const getPredictionIcon = (prediction: string) => {
    switch (prediction) {
      case 'LONG': return '↑'
      case 'SHORT': return '↓'
      default: return '→'
    }
  }

  const getPredictionColor = (prediction: string) => {
    switch (prediction) {
      case 'LONG': return 'text-green-600'
      case 'SHORT': return 'text-red-600'
      default: return 'text-gray-500'
    }
  }

  // Group signals by date
  const groupedSignals = useMemo(() => {
    const groups = new Map<string, MiroFishSignal[]>()
    
    filteredSignals.forEach(signal => {
      const date = new Date(signal.timestamp).toISOString().split('T')[0]
      const current = groups.get(date) || []
      current.push(signal)
      groups.set(date, current)
    })
    
    return Array.from(groups.entries())
      .sort((a, b) => b[0].localeCompare(a[0]))
      .map(([date, sigs]) => ({
        date,
        signals: sigs.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()),
      }))
  }, [filteredSignals])

  // Stats
  const stats = useMemo(() => {
    const resolved = filteredSignals.filter(s => s.actualOutcome !== 'PENDING')
    return {
      total: filteredSignals.length,
      correct: resolved.filter(s => s.actualOutcome === 'CORRECT').length,
      wrong: resolved.filter(s => s.actualOutcome === 'WRONG').length,
      pending: filteredSignals.filter(s => s.actualOutcome === 'PENDING').length,
    }
  }, [filteredSignals])

  return (
    <div className="space-y-4">
      {/* Filter Bar */}
      <div className="card p-4">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <span className="text-sm font-medium">Filter:</span>
            {(['ALL', 'LONG', 'SHORT', 'NEUTRAL'] as SignalType[]).map(type => (
              <button
                key={type}
                onClick={() => setFilterType(type)}
                className={`px-3 py-1.5 text-sm font-medium rounded-md transition-colors ${
                  filterType === type
                    ? 'bg-black text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                }`}
              >
                {type === 'ALL' ? 'All Signals' : type}
              </button>
            ))}
          </div>
          
          <div className="flex items-center gap-4 text-sm">
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-full bg-green-500" />
              <span className="text-gray-600">{stats.correct} Correct</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-full bg-red-500" />
              <span className="text-gray-600">{stats.wrong} Wrong</span>
            </div>
            <div className="flex items-center gap-1">
              <div className="w-3 h-3 rounded-full bg-gray-400" />
              <span className="text-gray-600">{stats.pending} Pending</span>
            </div>
          </div>
        </div>
      </div>

      {/* Timeline */}
      <div className="card p-4">
        <div className="space-y-6 max-h-[600px] overflow-y-auto">
          {groupedSignals.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              No signals found for the selected filter.
            </div>
          ) : (
            groupedSignals.map(({ date, signals: daySignals }) => (
              <div key={date} className="relative">
                {/* Date Header */}
                <div className="sticky top-0 bg-white z-10 py-2 border-b border-gray-200 mb-3">
                  <h3 className="text-sm font-semibold text-gray-700">
                    {new Date(date).toLocaleDateString('en-US', { 
                      weekday: 'long', 
                      year: 'numeric', 
                      month: 'long', 
                      day: 'numeric' 
                    })}
                  </h3>
                  <p className="text-xs text-gray-500">
                    {daySignals.length} signals · {' '}
                    {daySignals.filter(s => s.actualOutcome === 'CORRECT').length} correct · {' '}
                    {daySignals.filter(s => s.actualOutcome === 'WRONG').length} wrong
                  </p>
                </div>

                {/* Signals for this day */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                  {daySignals.map(signal => (
                    <div
                      key={signal.id}
                      onClick={() => setSelectedSignal(signal)}
                      className={`p-3 rounded-lg border-2 cursor-pointer transition-all hover:shadow-md ${
                        selectedSignal?.id === signal.id 
                          ? 'border-black bg-gray-50' 
                          : getSignalBorderColor(signal)
                      } ${signal.actualOutcome === 'PENDING' ? 'bg-gray-50' : signal.actualOutcome === 'CORRECT' ? 'bg-green-50' : 'bg-red-50'}`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className={`text-lg font-bold ${getPredictionColor(signal.prediction)}`}>
                            {getPredictionIcon(signal.prediction)}
                          </span>
                          <span className="font-semibold">{signal.ticker}</span>
                        </div>
                        <div className={`w-3 h-3 rounded-full ${getSignalColor(signal)}`} />
                      </div>
                      
                      <div className="mt-2 space-y-1 text-xs text-gray-600">
                        <div className="flex justify-between">
                          <span>Time:</span>
                          <span>{new Date(signal.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Confidence:</span>
                          <span className="font-medium">{(signal.confidence * 100).toFixed(0)}%</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Timeframe:</span>
                          <span className="font-medium">{signal.timeframe}</span>
                        </div>
                        {signal.actualReturn !== undefined && (
                          <div className="flex justify-between">
                            <span>Return:</span>
                            <span className={`font-medium ${signal.actualReturn >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                              {signal.actualReturn >= 0 ? '+' : ''}{signal.actualReturn.toFixed(2)}%
                            </span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Signal Detail Modal */}
      {selectedSignal && (
        <div 
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => setSelectedSignal(null)}
        >
          <div 
            className="bg-white rounded-lg p-6 max-w-md w-full shadow-xl"
            onClick={e => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold">Signal Details</h3>
              <button 
                onClick={() => setSelectedSignal(null)}
                className="text-gray-400 hover:text-gray-600"
              >
                ✕
              </button>
            </div>

            <div className="space-y-4">
              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <span className="text-gray-600">Ticker</span>
                <span className="font-bold text-lg">{selectedSignal.ticker}</span>
              </div>

              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <span className="text-gray-600">Prediction</span>
                <span className={`font-bold ${getPredictionColor(selectedSignal.prediction)}`}>
                  {selectedSignal.prediction} {getPredictionIcon(selectedSignal.prediction)}
                </span>
              </div>

              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <span className="text-gray-600">Confidence</span>
                <span className="font-bold">{(selectedSignal.confidence * 100).toFixed(1)}%</span>
              </div>

              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <span className="text-gray-600">Timeframe</span>
                <span className="font-bold">{selectedSignal.timeframe}</span>
              </div>

              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <span className="text-gray-600">Price at Signal</span>
                <span className="font-bold">${selectedSignal.priceAtSignal.toFixed(2)}</span>
              </div>

              {selectedSignal.actualOutcome !== 'PENDING' && (
                <>
                  <div className={`flex items-center justify-between p-3 rounded-lg ${
                    selectedSignal.actualOutcome === 'CORRECT' ? 'bg-green-50' : 'bg-red-50'
                  }`}>
                    <span className="text-gray-600">Outcome</span>
                    <span className={`font-bold ${
                      selectedSignal.actualOutcome === 'CORRECT' ? 'text-green-600' : 'text-red-600'
                    }`}>
                      {selectedSignal.actualOutcome}
                    </span>
                  </div>

                  {selectedSignal.actualReturn !== undefined && (
                    <div className={`flex items-center justify-between p-3 rounded-lg ${
                      selectedSignal.actualReturn >= 0 ? 'bg-green-50' : 'bg-red-50'
                    }`}>
                      <span className="text-gray-600">Actual Return</span>
                      <span className={`font-bold ${
                        selectedSignal.actualReturn >= 0 ? 'text-green-600' : 'text-red-600'
                      }`}>
                        {selectedSignal.actualReturn >= 0 ? '+' : ''}{selectedSignal.actualReturn.toFixed(2)}%
                      </span>
                    </div>
                  )}
                </>
              )}

              <div className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                <span className="text-gray-600">Timestamp</span>
                <span className="font-medium text-sm">
                  {new Date(selectedSignal.timestamp).toLocaleString()}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
