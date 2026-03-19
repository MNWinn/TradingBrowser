'use client'

import type { AgentHealth } from '@/lib/api'

interface AgentHealthBadgeProps {
  health?: AgentHealth
  size?: 'sm' | 'md' | 'lg'
  showLabel?: boolean
}

export function AgentHealthBadge({
  health,
  size = 'md',
  showLabel = false,
}: AgentHealthBadgeProps) {
  const getHealthStatus = (): 'healthy' | 'degraded' | 'unhealthy' | 'unknown' => {
    if (!health) return 'unknown'
    if (health.status) return health.status
    
    // Infer from score if status not provided
    if (health.score !== undefined) {
      if (health.score >= 0.8) return 'healthy'
      if (health.score >= 0.5) return 'degraded'
      return 'unhealthy'
    }
    
    return 'unknown'
  }

  const getStatusConfig = (status: ReturnType<typeof getHealthStatus>) => {
    switch (status) {
      case 'healthy':
        return {
          dotColor: 'bg-emerald-500',
          bgColor: 'bg-emerald-50',
          borderColor: 'border-emerald-200',
          textColor: 'text-emerald-800',
          label: 'Healthy',
        }
      case 'degraded':
        return {
          dotColor: 'bg-amber-500',
          bgColor: 'bg-amber-50',
          borderColor: 'border-amber-200',
          textColor: 'text-amber-800',
          label: 'Degraded',
        }
      case 'unhealthy':
        return {
          dotColor: 'bg-red-500',
          bgColor: 'bg-red-50',
          borderColor: 'border-red-200',
          textColor: 'text-red-800',
          label: 'Unhealthy',
        }
      default:
        return {
          dotColor: 'bg-neutral-400',
          bgColor: 'bg-neutral-50',
          borderColor: 'border-neutral-200',
          textColor: 'text-neutral-600',
          label: 'Unknown',
        }
    }
  }

  const status = getHealthStatus()
  const config = getStatusConfig(status)

  const sizeClasses = {
    sm: {
      container: 'gap-1',
      dot: 'w-1.5 h-1.5',
      text: 'text-[10px]',
    },
    md: {
      container: 'gap-1.5',
      dot: 'w-2 h-2',
      text: 'text-xs',
    },
    lg: {
      container: 'gap-2',
      dot: 'w-2.5 h-2.5',
      text: 'text-sm',
    },
  }

  const pulseAnimation = status === 'healthy' ? 'animate-pulse' : ''

  return (
    <div
      className={`inline-flex items-center ${sizeClasses[size].container} ${
        showLabel
          ? `px-2 py-1 rounded-full border ${config.bgColor} ${config.borderColor}`
          : ''
      }`}
    >
      <span
        className={`rounded-full ${config.dotColor} ${sizeClasses[size].dot} ${pulseAnimation}`}
        title={config.label}
      />
      {showLabel && (
        <span className={`${sizeClasses[size].text} ${config.textColor} font-medium`}>
          {config.label}
        </span>
      )}
      {!showLabel && health?.score !== undefined && (
        <span className={`${sizeClasses[size].text} text-neutral-500`}>
          {Math.round(health.score * 100)}%
        </span>
      )}
    </div>
  )
}

// Standalone health indicator dot for compact displays
interface HealthDotProps {
  health?: AgentHealth
  size?: 'sm' | 'md' | 'lg'
}

export function HealthDot({ health, size = 'md' }: HealthDotProps) {
  const getHealthStatus = (): 'healthy' | 'degraded' | 'unhealthy' | 'unknown' => {
    if (!health) return 'unknown'
    if (health.status) return health.status
    if (health.score !== undefined) {
      if (health.score >= 0.8) return 'healthy'
      if (health.score >= 0.5) return 'degraded'
      return 'unhealthy'
    }
    return 'unknown'
  }

  const getDotColor = (status: ReturnType<typeof getHealthStatus>) => {
    switch (status) {
      case 'healthy':
        return 'bg-emerald-500'
      case 'degraded':
        return 'bg-amber-500'
      case 'unhealthy':
        return 'bg-red-500'
      default:
        return 'bg-neutral-400'
    }
  }

  const sizeClasses = {
    sm: 'w-1.5 h-1.5',
    md: 'w-2 h-2',
    lg: 'w-3 h-3',
  }

  const status = getHealthStatus()
  const pulseAnimation = status === 'healthy' ? 'animate-pulse' : ''

  return (
    <span
      className={`inline-block rounded-full ${getDotColor(status)} ${sizeClasses[size]} ${pulseAnimation}`}
      title={status.charAt(0).toUpperCase() + status.slice(1)}
    />
  )
}
