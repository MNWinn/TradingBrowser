'use client'

import { useEffect, useState } from 'react'
import { Sidebar } from '@/components/Sidebar'
import { ChartPane } from '@/components/ChartPane'
import { ProbabilityDrawer } from '@/components/ProbabilityDrawer'
import { addWatchlistTicker, getProbability, getSignal, getWatchlist, removeWatchlistTicker } from '@/lib/api'

const USER_ID = 'demo'

export default function WorkspacePage() {
  const [ticker, setTicker] = useState('AAPL')
  const [tickers, setTickers] = useState<string[]>([])
  const [probability, setProbability] = useState<any>(null)
  const [signal, setSignal] = useState<any>(null)
  const [loading, setLoading] = useState(false)
  const [timeframe, setTimeframe] = useState('5m')

  useEffect(() => {
    getWatchlist(USER_ID).then((res) => {
      const items = res.items || []
      setTickers(items)
      if (items.length && !items.includes(ticker)) setTicker(items[0])
    })
  }, [])

  const refreshAnalysis = async (tf: string) => {
    setLoading(true)
    setTimeframe(tf)
    try {
      const [p, s] = await Promise.all([getProbability(ticker, tf), getSignal(ticker)])
      setProbability(p)
      setSignal(s)
    } finally {
      setLoading(false)
    }
  }

  const handleAdd = async (t: string) => {
    const res = await addWatchlistTicker(USER_ID, t)
    setTickers(res.items || [])
  }

  const handleRemove = async (t: string) => {
    const res = await removeWatchlistTicker(USER_ID, t)
    setTickers(res.items || [])
    if (ticker === t && res.items?.length) setTicker(res.items[0])
  }

  return (
    <main>
      <div className="flex gap-3">
        <Sidebar
          tickers={tickers}
          activeTicker={ticker}
          onSelect={setTicker}
          onAdd={handleAdd}
          onRemove={handleRemove}
        />
        <ChartPane ticker={ticker} onInspect={refreshAnalysis} />
        <ProbabilityDrawer probability={probability} signal={signal} loading={loading} timeframe={timeframe} />
      </div>
      <div className="card p-3 mt-3 text-xs text-slate-300">
        Bottom Console: swarm logs, order logs, queue health. Current signal: {signal?.action || 'N/A'}
      </div>
    </main>
  )
}
