'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import type { ReactNode } from 'react'
import { CommandPalette } from '@/components/CommandPalette'

const NAV = [
  { href: '/dashboard', label: 'Dashboard' },
  { href: '/workspace', label: 'Workspace' },
  { href: '/agents', label: 'Agents' },
  { href: '/swarm', label: 'Swarm' },
  { href: '/paper-console', label: 'Paper Console' },
  { href: '/strategy-lab', label: 'Strategy Lab' },
  { href: '/training', label: 'Training' },
  { href: '/compliance', label: 'Compliance' },
  { href: '/settings', label: 'Settings' },
  { href: '/journal', label: 'Journal' },
  { href: '/live-control', label: 'Live Control' },
]

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname()

  return (
    <div className="min-h-screen">
      <CommandPalette items={NAV} />
      <div className="max-w-[1800px] mx-auto px-3 py-3 lg:grid lg:grid-cols-[220px_1fr] lg:gap-3">
        <aside className="card p-2 hidden lg:block h-fit sticky top-3">
          <div className="px-2 py-1 mb-1">
            <div className="text-sm font-semibold">TradingBrowser</div>
            <div className="text-[11px] text-slate-400">Operations Console</div>
          </div>
          <nav className="space-y-1">
            {NAV.map((item) => {
              const active = pathname === item.href
              return (
                <Link key={item.href} href={item.href} className={`block px-2 py-1.5 rounded text-sm border ${active ? 'bg-black text-white border-black' : 'bg-white border-transparent hover:border-neutral-300'}`}>
                  {item.label}
                </Link>
              )
            })}
          </nav>
        </aside>

        <div className="space-y-3">
          <header className="card p-2 flex items-center justify-between">
            <div className="text-sm font-medium">{NAV.find((n) => n.href === pathname)?.label || 'TradingBrowser'}</div>
            <div className="text-xs text-slate-400">⌘K / Ctrl+K</div>
          </header>
          {children}
        </div>
      </div>
    </div>
  )
}
