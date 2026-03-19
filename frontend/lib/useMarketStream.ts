'use client'

import { useEffect, useState } from 'react'

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000/ws/market'

export function useMarketStream() {
  const [tick, setTick] = useState<any>(null)

  useEffect(() => {
    const ws = new WebSocket(WS_URL)
    ws.onmessage = (e) => setTick(JSON.parse(e.data))
    return () => ws.close()
  }, [])

  return tick
}
