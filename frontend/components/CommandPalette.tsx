'use client'

import { useEffect, useMemo, useState } from 'react'
import { useRouter } from 'next/navigation'

type Item = { href: string; label: string }

export function CommandPalette({ items }: { items: Item[] }) {
  const router = useRouter()
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setOpen((v) => !v)
      }
      if (e.key === 'Escape') setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return items
    return items.filter((i) => i.label.toLowerCase().includes(q) || i.href.toLowerCase().includes(q))
  }, [items, query])

  if (!open) return null

  return (
    <div className="fixed inset-0 z-[100] bg-black/20 flex items-start justify-center pt-24 px-4" onClick={() => setOpen(false)}>
      <div className="card w-full max-w-xl p-2" onClick={(e) => e.stopPropagation()}>
        <input
          autoFocus
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Go to..."
          className="w-full px-3 py-2 text-sm"
        />
        <div className="mt-2 max-h-72 overflow-auto">
          {filtered.map((i) => (
            <button
              key={i.href}
              className="w-full text-left px-3 py-2 text-sm rounded hover:bg-neutral-100"
              onClick={() => {
                router.push(i.href)
                setOpen(false)
                setQuery('')
              }}
            >
              {i.label}
            </button>
          ))}
          {!filtered.length && <div className="px-3 py-2 text-xs text-slate-400">No results</div>}
        </div>
      </div>
    </div>
  )
}
