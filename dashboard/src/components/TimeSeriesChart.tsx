import {
  LineChart, Line, XAxis, YAxis, CartesianGrid,
  Tooltip, Legend, ResponsiveContainer,
} from 'recharts'
import type { TimePoint } from '@/types'

interface Props {
  data: TimePoint[]
  endpoints: string[]
  colors: Record<string, string>
}

const PALETTE = ['#5b8dee', '#22d3a0', '#f5a623', '#9b72f7', '#f25f5c', '#38bdf8']

function fmtTime(ts: number) {
  const d = new Date(ts)
  return `${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}`
}

export function TimeSeriesChart({ data, endpoints, colors }: Props) {
  return (
    <div style={{
      background: 'var(--bg-panel)',
      border: '1px solid var(--border)',
      borderRadius: 6,
      padding: '16px 20px',
    }}>
      <div style={{ marginBottom: 14 }}>
        <span style={{ fontFamily: 'var(--mono)', fontSize: 11, color: 'var(--text-3)', fontWeight: 600, letterSpacing: '0.08em' }}>
          ACTIVE REQUESTS — LAST 60s
        </span>
      </div>
      <ResponsiveContainer width="100%" height={200}>
        <LineChart data={data} margin={{ top: 4, right: 8, left: -20, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1e2535" vertical={false} />
          <XAxis
            dataKey="ts"
            tickFormatter={fmtTime}
            tick={{ fill: 'var(--text-3)', fontSize: 10, fontFamily: 'var(--mono)' }}
            axisLine={{ stroke: 'var(--border)' }}
            tickLine={false}
            interval="preserveStartEnd"
          />
          <YAxis
            tick={{ fill: 'var(--text-3)', fontSize: 10, fontFamily: 'var(--mono)' }}
            axisLine={false}
            tickLine={false}
            allowDecimals={false}
            width={40}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--bg-panel2)',
              border: '1px solid var(--border)',
              borderRadius: 4,
              fontFamily: 'var(--mono)',
              fontSize: 11,
              color: 'var(--text-1)',
            }}
            labelFormatter={(v) => fmtTime(v as number)}
            itemStyle={{ color: 'var(--text-1)' }}
            cursor={{ stroke: 'var(--border)' }}
          />
          <Legend
            wrapperStyle={{ fontFamily: 'var(--mono)', fontSize: 10, color: 'var(--text-2)' }}
          />
          {endpoints.map((ep, i) => (
            <Line
              key={ep}
              type="monotone"
              dataKey={ep}
              stroke={colors[ep] ?? PALETTE[i % PALETTE.length]}
              strokeWidth={2}
              dot={false}
              isAnimationActive={false}
              connectNulls
            />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
