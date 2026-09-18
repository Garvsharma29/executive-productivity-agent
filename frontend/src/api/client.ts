import type { DailyBriefResponse, AgentQueryResponse } from './types'

const API_BASE = '/api'

export async function fetchDailyBrief(asOfDate: string): Promise<DailyBriefResponse> {
  const url = `${API_BASE}/brief?as_of_date=${encodeURIComponent(asOfDate)}`
  const response = await fetch(url, {
    headers: {
      'Accept': 'application/json',
    },
  })

  if (!response.ok) {
    const errorText = await response.text().catch(() => '')
    throw new Error(
      `Failed to fetch daily brief (${response.status} ${response.statusText}): ${errorText || 'Server error'}`
    )
  }

  return response.json()
}

export async function queryAgent(
  query: string,
  asOfDate: string
): Promise<AgentQueryResponse> {
  const url = `${API_BASE}/agent/query`
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Accept': 'application/json',
    },
    body: JSON.stringify({
      query,
      as_of_date: asOfDate,
    }),
  })

  if (!response.ok) {
    const errorText = await response.text().catch(() => '')
    throw new Error(
      `Failed to query executive agent (${response.status} ${response.statusText}): ${errorText || 'Server error'}`
    )
  }

  return response.json()
}
