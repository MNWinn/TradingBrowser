'use client'

import { useState } from 'react'

type Props = {
  tickers: string[]
  activeTicker: string
  onSelect: (ticker: string) => void
  onAdd: (ticker: string) => void
  onRemove: (ticker: string) => void
}

export function Sidebar({ tickers, activeTicker, onSelect, onAdd, onRemove }: Props) {
  const [value, setValue] = useState('')

  return (
    <aside className="card p-3 w-56">
      <h3 className="font-semibold mb-2">Watchlist</h3>
      <div className="flex gap-1 mb-2">
        <input
          value={value}
          onChange={(e) => setValue(e.target.value.toUpperCase())}
          placeholder="Add ticker"
          className="px-2 py-1 text-xs w-full"
        />
        <button
          onClick={() => {
            if (value.trim()) onAdd(value.trim())
            setValue('')
          }}
          className="btn btn-primary"
        >
          +
        </button>
      </div>
      <div className="space-y-2">
        {tickers.map((t) => (
          <div key={t} className="flex gap-1">
            <button
              className={`flex-1 text-left px-2 py-1 rounded border ${activeTicker === t ? 'bg-black text-white border-black' : 'bg-white border-neutral-300 hover:border-neutral-500'}`}
              onClick={() => onSelect(t)}
            >
              {t}
            </button>
            <button className="btn btn-muted" onClick={() => onRemove(t)}>
              ×
            </button>
          </div>
        ))}
      </div>
    </aside>
  )
}
