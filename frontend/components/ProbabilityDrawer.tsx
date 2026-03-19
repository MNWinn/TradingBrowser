type Props = {
  probability: any
  signal: any
  loading: boolean
  timeframe: string
}

export function ProbabilityDrawer({ probability, signal, loading, timeframe }: Props) {
  const hasMirofish = Boolean(probability?.contributors?.includes('mirofish') || signal?.reason_codes?.includes('mirofish_context'))

  return (
    <aside className="card p-3 w-80">
      <h3 className="font-semibold mb-2">Probability / Stats</h3>
      <div className="text-xs text-neutral-500 mb-2">Timeframe: {timeframe}</div>

      {loading && <div className="text-sm text-neutral-700 mb-2">Computing analysis…</div>}

      {!probability ? (
        <div className="text-sm text-neutral-500">Click Analyze to compute probability and fetch a fresh signal.</div>
      ) : (
        <ul className="text-sm space-y-1 text-neutral-800">
          <li>Next-bar Up Prob: {Math.round((probability.next_bar_direction_probability?.up || 0) * 100)}%</li>
          <li>Target-before-stop: {Math.round((probability.target_before_stop_probability || 0) * 100)}%</li>
          <li>Regime: {probability.volatility_regime}</li>
          <li>Model Confidence: {Math.round((probability.model_confidence || 0) * 100)}%</li>
          <li>Recommendation: {signal?.action || probability.recommendation}</li>
          <li className="pt-2">
            MiroFish Context:{' '}
            <span className={hasMirofish ? 'text-emerald-700' : 'text-amber-700'}>{hasMirofish ? 'Included (stub provider)' : 'Not included'}</span>
          </li>
          <li className="text-xs text-neutral-500 pt-2">{signal?.explanation || probability.plain_english}</li>
        </ul>
      )}
    </aside>
  )
}
