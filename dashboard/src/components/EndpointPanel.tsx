import type { EndpointStats } from '@/types'

interface Props {
  path: string
  stats: EndpointStats
  color: string
}

function healthColor(active: number, capacity: number): string {
  if (capacity === 0) return 'var(--text-3)'
  const ratio = active / capacity
  if (ratio >= 1) return 'var(--red)'
  if (ratio >= 0.8) return 'var(--yellow)'
  return 'var(--green)'
}

function healthLabel(active: number, capacity: number): string {
  if (capacity === 0) return 'UNKNOWN'
  const ratio = active / capacity
  if (ratio >= 1) return 'SATURATED'
  if (ratio >= 0.8) return 'HIGH LOAD'
  return 'HEALTHY'
}

export function EndpointPanel({ path, stats, color }: Props) {
  const { capacity, active_requests, available_slots } = stats
  const queue = Math.max(0, active_requests - capacity)
  const utilPct = capacity > 0 ? Math.min(100, Math.round((active_requests / capacity) * 100)) : 0
  const hColor = healthColor(active_requests, capacity)

  return (
    <div style={{
      background: 'var(--bg-panel)',
      border: `1px solid var(--border)`,
      borderTop: `2px solid ${color}`,
      borderRadius: 6,
      padding: '16px 20px',
      display: 'flex',
      flexDirection: 'column',
      gap: 14,
    }}>
      {/* header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 13, color, fontWeight: 700 }}>{path}</span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          {queue > 0 && (
            <span style={{
              background: 'var(--red)', color: '#fff',
              fontSize: 10, fontWeight: 700, fontFamily: 'var(--mono)',
              padding: '2px 6px', borderRadius: 3,
            }}>
              QUEUE +{queue}
            </span>
          )}
          <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
            <span style={{
              width: 8, height: 8, borderRadius: '50%',
              background: hColor,
              boxShadow: `0 0 6px ${hColor}`,
              display: 'inline-block',
            }} />
            <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: hColor, fontWeight: 600 }}>
              {healthLabel(active_requests, capacity)}
            </span>
          </div>
        </div>
      </div>

      {/* stat row */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 10 }}>
        {[
          { label: 'CAPACITY', value: capacity, accent: color },
          { label: 'ACTIVE', value: active_requests, accent: hColor },
          { label: 'AVAILABLE', value: available_slots, accent: 'var(--text-2)' },
        ].map(({ label, value, accent }) => (
          <div key={label} style={{
            background: 'var(--bg-panel2)',
            border: '1px solid var(--border)',
            borderRadius: 4,
            padding: '10px 12px',
          }}>
            <div style={{ fontSize: 9, fontFamily: 'var(--mono)', color: 'var(--text-3)', fontWeight: 600, letterSpacing: '0.08em', marginBottom: 4 }}>{label}</div>
            <div style={{ fontSize: 22, fontFamily: 'var(--mono)', fontWeight: 700, color: accent, lineHeight: 1 }}>{value}</div>
          </div>
        ))}
      </div>

      {/* utilization bar */}
      <div>
        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 5 }}>
          <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: 'var(--text-3)', letterSpacing: '0.06em' }}>UTILIZATION</span>
          <span style={{ fontSize: 10, fontFamily: 'var(--mono)', color: hColor, fontWeight: 700 }}>{utilPct}%</span>
        </div>
        <div style={{ height: 6, background: 'var(--bg-input)', borderRadius: 3, overflow: 'hidden' }}>
          <div style={{
            height: '100%',
            width: `${utilPct}%`,
            background: `linear-gradient(90deg, ${color}, ${hColor})`,
            borderRadius: 3,
            transition: 'width 0.4s ease',
          }} />
        </div>
      </div>
    </div>
  )
}
