'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { ColorType, createChart, type IChartApi, type UTCTimestamp } from 'lightweight-charts'
import { getBars } from '@/lib/api'

type Props = {
  ticker: string
  onInspect: (timeframe: string) => void
}

const TIMEFRAMES = ['1m', '5m', '15m', '1h']

export function ChartPane({ ticker, onInspect }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const [timeframe, setTimeframe] = useState('5m')
  const [barsCount, setBarsCount] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [sourceLabel, setSourceLabel] = useState('unknown')
  const [simulated, setSimulated] = useState(true)
  const [lastTs, setLastTs] = useState('—')

  const title = useMemo(() => `Chart Workspace: ${ticker}`, [ticker])

  useEffect(() => {
    if (!containerRef.current) return

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 420,
      layout: {
        textColor: '#222222',
        background: { type: ColorType.Solid, color: '#ffffff' },
      },
      rightPriceScale: {
        borderColor: '#d4d4d4',
      },
      timeScale: {
        borderColor: '#d4d4d4',
      },
      grid: {
        vertLines: { color: '#f0f0f0' },
        horzLines: { color: '#f0f0f0' },
      },
      crosshair: {
        vertLine: { color: '#9ca3af' },
        horzLine: { color: '#9ca3af' },
      },
    })

    const candleSeries = chart.addCandlestickSeries({
      upColor: '#111111',
      downColor: '#6b7280',
      borderVisible: false,
      wickUpColor: '#111111',
      wickDownColor: '#6b7280',
    })

    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const res = await getBars(ticker, timeframe, 240)
        const bars = (res.bars || []).map((b: any, idx: number) => {
          const unix = Math.floor(new Date(b.t).getTime() / 1000) || Math.floor(Date.now() / 1000) + idx
          return {
            time: unix as UTCTimestamp,
            open: b.o,
            high: b.h,
            low: b.l,
            close: b.c,
          }
        })

        candleSeries.setData(bars)
        chart.timeScale().fitContent()
        setBarsCount(bars.length)
        setSourceLabel(res.source || 'unknown')
        setSimulated(Boolean(res.simulated))
        const latest = res.bars?.[res.bars.length - 1]?.t
        setLastTs(latest ? new Date(latest).toLocaleTimeString() : '—')
      } catch (e: any) {
        setError(e?.message || 'Failed to load bars')
        setBarsCount(0)
      } finally {
        setLoading(false)
      }
    }

    void load()
    const poll = window.setInterval(() => void load(), 5000)

    const ro = new ResizeObserver(() => {
      if (!containerRef.current) return
      chart.applyOptions({ width: containerRef.current.clientWidth })
    })
    ro.observe(containerRef.current)

    chartRef.current = chart
    return () => {
      window.clearInterval(poll)
      ro.disconnect()
      chart.remove()
      chartRef.current = null
    }
  }, [ticker, timeframe])

  return (
    <section className="card p-3 flex-1 min-h-[480px]">
      <div className="flex justify-between mb-2 items-center gap-3">
        <h3 className="font-semibold">{title}</h3>
        <div className="flex items-center gap-2 flex-wrap justify-end">
          <div className="text-xs text-neutral-600">Bars: {barsCount}</div>
          <div className="text-xs px-2 py-1 rounded border border-neutral-300 text-neutral-700">
            {sourceLabel} {simulated ? '(sim)' : '(live)'}
          </div>
          <div className="text-xs text-neutral-500">Last bar: {lastTs}</div>
          <div className="flex gap-1">
            {TIMEFRAMES.map((tf) => (
              <button
                key={tf}
                onClick={() => setTimeframe(tf)}
                className={`text-xs px-2 py-1 rounded border ${timeframe === tf ? 'bg-black text-white border-black' : 'bg-white border-neutral-300'}`}
              >
                {tf}
              </button>
            ))}
          </div>
          <button onClick={() => onInspect(timeframe)} className="btn btn-primary">
            Analyze
          </button>
        </div>
      </div>

      <div className="relative h-[420px] w-full rounded border border-neutral-300 overflow-hidden bg-white">
        <div ref={containerRef} className="h-full w-full" />
        {loading && <div className="absolute top-2 left-2 text-xs text-neutral-600">Loading bars…</div>}
        {error && <div className="absolute top-2 left-2 text-xs text-red-700">{error}</div>}
      </div>
    </section>
  )
}
