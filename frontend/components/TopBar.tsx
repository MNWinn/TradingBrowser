export function TopBar({ mode }: { mode: string }) {
  return (
    <header className="card p-3 mb-3 flex justify-between items-center">
      <div>
        <h1 className="font-bold">TradingBrowser</h1>
        <p className="text-xs text-neutral-600">AI-assisted research and execution platform</p>
      </div>
      <div className="text-sm px-3 py-1 rounded border border-neutral-300">
        MODE: {mode.toUpperCase()}
      </div>
    </header>
  )
}
