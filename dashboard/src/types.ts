export interface EndpointStats {
  capacity: number
  active_requests: number
  available_slots: number
}

export interface StatsResponse {
  endpoints: Record<string, EndpointStats>
}

export interface TimePoint {
  ts: number
  [endpoint: string]: number
}
