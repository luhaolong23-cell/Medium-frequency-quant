const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api').replace(/\/$/, '')

function buildQuery(params = {}) {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null || value === '' || value === 'ALL') {
      return
    }
    searchParams.set(key, String(value))
  })
  const query = searchParams.toString()
  return query ? `?${query}` : ''
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(options.headers || {}),
    },
    ...options,
  })

  const payload = await response.json().catch(() => null)
  if (!response.ok) {
    const message = payload?.error?.message || `Request failed: ${response.status}`
    throw new Error(message)
  }
  if (payload?.status !== 'success') {
    throw new Error(payload?.error?.message || 'Unexpected API response')
  }
  return payload.data
}

export function fetchHealth() {
  return request('/health')
}

export function fetchDataSources() {
  return request('/data-sources')
}

export function fetchWorkflowSummary() {
  return request('/workflow/logs/latest-summary')
}

export function fetchSchedulerLogs() {
  return request('/workflow/logs/scheduler')
}

export function fetchBullSearchProcess() {
  return request('/markets/bull-search/process')
}

export function fetchMarketOverview() {
  return request('/markets/overview')
}

export function runBullSearch(payload = {}) {
  return request('/markets/bull-search/run', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function fetchThemes(marketCode) {
  return request(`/themes/hot/today${buildQuery({ market_code: marketCode })}`)
}

export function fetchUniverse(marketCode) {
  return request(`/universe/today${buildQuery({ market_code: marketCode })}`)
}

export function fetchSeeds(marketCode) {
  return request(`/seeds/today${buildQuery({ market_code: marketCode })}`)
}

export function fetchCandidates(marketCode) {
  return request(`/candidates/today${buildQuery({ market_code: marketCode })}`)
}

export function runStockScreen(payload = {}) {
  return request('/candidates/run', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function fetchWatchlist(marketCode) {
  return request(`/watchlist/today${buildQuery({ market_code: marketCode })}`)
}

export function fetchSignals(marketCode) {
  return request(`/signals/today${buildQuery({ market_code: marketCode })}`)
}

export function fetchOrders(marketCode) {
  return request(`/orders/today${buildQuery({ market_code: marketCode })}`)
}

export function fetchPositions(marketCode) {
  return request(`/positions${buildQuery({ market_code: marketCode, status: 'OPEN' })}`)
}

export function runPositionSell(payload = {}) {
  return request('/positions/sell', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function runDailyWorkflow(payload) {
  return request('/admin/run-daily', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function composeThemeStrategyAgent(payload) {
  return request('/agent/themes/compose', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function addDataSourceAgent(payload) {
  return request('/agent/data-sources/add', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
