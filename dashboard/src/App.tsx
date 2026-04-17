import { useState, useEffect, useRef, useCallback } from 'react'
import type { StatsResponse, TimePoint } from '@/types'
import { EndpointPanel } from '@/components/EndpointPanel'
import { TimeSeriesChart } from '@/components/TimeSeriesChart'

const MAX_POINTS = 30       // 30 × 2s = 60s window
const POLL_MS    = 2000

const PALETTE = ['#5b8dee', '#22d3a0', '#f5a623', '#9b72f7', '#f25f5c', '#38bdf8']

function colorMap(endpoints: string[]): Record<string, string> {
  return Object.fromEntries(endpoints.map((ep, i) => [ep, PALETTE[i % PALETTE.length]]))
}

export default function App() {
  const [baseUrl, setBaseUrl] = useState(() => window.location.origin)
  const [inputUrl, setInputUrl] = useState(() => window.location.origin)
  const [stats, setStats] = useState<StatsResponse | null>(null)
  const [history, setHistory] = useState<TimePoint[]>([])
  const [error, setError] = useState<string | null>(null)
  const [lastUpdate, setLastUpdate] = useState<Date | null>(null)
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null)

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch(`${baseUrl}/balancer/stats`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data: StatsResponse = await res.json()
      setStats(data)
      setError(null)
      setLastUpdate(new Date())
      setHistory(prev => {
        const point: TimePoint = { ts: Date.now() }
        for (const [ep, s] of Object.entries(data.endpoints)) {
          point[ep] = s.active_requests
        }
        const next = [...prev, point]
        return next.length > MAX_POINTS ? next.slice(next.length - MAX_POINTS) : next
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    }
  }, [baseUrl])

  useEffect(() => {
    fetchStats()
    timerRef.current = setInterval(fetchStats, POLL_MS)
    return () => { if (timerRef.current) clearInterval(timerRef.current) }
  }, [fetchStats])

  const endpoints = stats ? Object.keys(stats.endpoints) : []
  const colors = colorMap(endpoints)

  return (
    <div style={{ minHeight: '100vh', background: 'var(--bg-base)' }}>
      {/* top bar */}
      <header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        padding: '0 24px', height: 52,
        borderBottom: '1px solid var(--border)',
        background: 'var(--bg-panel)',
        position: 'sticky', top: 0, zIndex: 10,
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <div style={{
            width: 8, height: 8, borderRadius: '50%',
            background: error ? 'var(--red)' : 'var(--green)',
            boxShadow: `0 0 8px ${error ? 'var(--red)' : 'var(--green)'}`,
          }} />
          <span style={{ fontFamily: 'var(--mono)', fontWeight: 700, fontSize: 13, color: 'var(--text-1)', letterSpacing: '0.04em' }}>
            FASTAPI BALANCER
          </span>
          <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-3)', marginLeft: 4 }}>
            DASHBOARD
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          {lastUpdate && (
            <span style={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-3)' }}>
              {lastUpdate.toLocaleTimeString()}
            </span>
          )}
          <form
            onSubmit={e => { e.preventDefault(); setBaseUrl(inputUrl); setHistory([]) }}
            style={{ display: 'flex', gap: 6 }}
          >
            <input
              value={inputUrl}
              onChange={e => setInputUrl(e.target.value)}
              style={{
                background: 'var(--bg-input)',
                border: '1px solid var(--border)',
                borderRadius: 4,
                padding: '4px 10px',
                color: 'var(--text-1)',
                fontFamily: 'var(--mono)',
                fontSize: 12,
                width: 220,
                outline: 'none',
              }}
            />
            <button type="submit" style={{
              background: 'var(--blue)',
              border: 'none', borderRadius: 4,
              padding: '4px 12px',
              color: '#fff',
              fontFamily: 'var(--mono)',
              fontSize: 11, fontWeight: 700,
              cursor: 'pointer',
              letterSpacing: '0.04em',
            }}>
              CONNECT
            </button>
          </form>
        </div>
      </header>

      <main style={{ padding: '20px 24px', maxWidth: 1200, margin: '0 auto' }}>
        {/* error banner */}
        {error && (
          <div style={{
            background: 'rgba(242,95,92,0.1)',
            border: '1px solid var(--red)',
            borderRadius: 4, padding: '8px 14px',
            marginBottom: 16,
            fontFamily: 'var(--mono)', fontSize: 12,
            color: 'var(--red)',
            display: 'flex', alignItems: 'center', gap: 8,
          }}>
            <span style={{ fontWeight: 700 }}>ERROR</span>
            <span style={{ color: 'var(--text-2)' }}>{error} — {baseUrl}/balancer/stats</span>
          </div>
        )}

        {/* summary bar */}
        {stats && endpoints.length > 0 && (
          <div style={{
            display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap',
          }}>
            {[
              { label: 'ENDPOINTS', value: endpoints.length, color: 'var(--blue)' },
              { label: 'TOTAL ACTIVE', value: Object.values(stats.endpoints).reduce((s, e) => s + e.active_requests, 0), color: 'var(--yellow)' },
              { label: 'TOTAL CAPACITY', value: Object.values(stats.endpoints).reduce((s, e) => s + e.capacity, 0), color: 'var(--purple)' },
              { label: 'QUEUED', value: Object.values(stats.endpoints).reduce((s, e) => s + Math.max(0, e.active_requests - e.capacity), 0), color: 'var(--red)' },
            ].map(({ label, value, color }) => (
              <div key={label} style={{
                background: 'var(--bg-panel)',
                border: '1px solid var(--border)',
                borderRadius: 5,
                padding: '8px 16px',
                display: 'flex', alignItems: 'baseline', gap: 8,
              }}>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 18, fontWeight: 700, color }}>{value}</span>
                <span style={{ fontFamily: 'var(--mono)', fontSize: 9, color: 'var(--text-3)', letterSpacing: '0.08em' }}>{label}</span>
              </div>
            ))}
          </div>
        )}

        {/* endpoint panels */}
        {stats && endpoints.length > 0 ? (
          <>
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(300px, 1fr))',
              gap: 14,
              marginBottom: 20,
            }}>
              {endpoints.map(ep => (
                <EndpointPanel
                  key={ep}
                  path={ep}
                  stats={stats.endpoints[ep]}
                  color={colors[ep]}
                />
              ))}
            </div>

            <TimeSeriesChart data={history} endpoints={endpoints} colors={colors} />
          </>
        ) : !error ? (
          <div style={{
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            height: 200,
            color: 'var(--text-3)', fontFamily: 'var(--mono)', fontSize: 12,
          }}>
            CONNECTING TO {baseUrl}...
          </div>
        ) : null}
      </main>
    </div>
  )
}
