import { computed, reactive, watch } from 'vue'

import {
  fetchBullSearchProcess,
  fetchCandidates,
  fetchDataSources,
  fetchHealth,
  fetchOrders,
  fetchPositions,
  fetchSeeds,
  fetchSignals,
  fetchSchedulerLogs,
  fetchThemes,
  fetchUniverse,
  fetchWatchlist,
  fetchWorkflowSummary,
  runDailyWorkflow,
} from './api'

const state = reactive({
  loading: false,
  running: false,
  error: '',
  notice: '',
  lastLoadedAt: '',
  selectedMarket: 'ALL',
  health: null,
  dataSources: null,
  summary: null,
  schedulerLogs: [],
  bullProcess: null,
  themes: [],
  industryThemes: [],
  universe: [],
  seeds: [],
  candidates: [],
  watchlist: [],
  signals: [],
  orders: [],
  positions: [],
  runResult: null,
})

let hasLoaded = false
let pendingLoad = null

const marketOptions = computed(() => {
  const codes = new Set(['ALL'])
  const sources = [
    state.summary?.latest_market_regimes || [],
    state.summary?.tracked_bull_markets || [],
    state.bullProcess?.markets || [],
    state.watchlist || [],
    state.positions || [],
    state.universe || [],
  ]

  sources.forEach((items) => {
    items.forEach((item) => {
      if (item.market_code) {
        codes.add(item.market_code)
      }
    })
  })

  return Array.from(codes)
})

const buyExecutionCount = computed(() => state.signals.filter((item) => item.side === 'BUY' && item.triggered).length)
const marketUniverseCount = computed(() => new Set((state.universe || []).map((item) => item.market_code).filter(Boolean)).size)

const navMetrics = computed(() => ({
  overview: state.summary?.tracked_bull_count ?? 0,
  'markets-universe': marketUniverseCount.value,
  'stock-screen': state.watchlist.length,
  'trade-execution': buyExecutionCount.value,
  'position-watch': state.positions.length,
  'bull-strategy': state.bullProcess?.markets?.length ?? 0,
  'theme-strategy': state.themes.length,
  'stock-strategy': state.watchlist.length,
  'trading-strategy': state.positions.length,
  'scheduler-logs': state.schedulerLogs.length,
  operations: state.runResult?.status === 'completed' ? 'OK' : 'RUN',
  'data-sources': state.dataSources?.sources?.length ?? 0,
}))

async function loadDashboard() {
  if (pendingLoad) {
    return pendingLoad
  }

  pendingLoad = (async () => {
    state.loading = true
    state.error = ''
    state.notice = ''

    try {
      const marketCode = state.selectedMarket === 'ALL' ? undefined : state.selectedMarket
      const [
        health,
        dataSources,
        summary,
        schedulerLogs,
        bullProcess,
        themes,
        universe,
        seeds,
        candidates,
        watchlist,
        signals,
        orders,
        positions,
      ] = await Promise.all([
        fetchHealth(),
        fetchDataSources(),
        fetchWorkflowSummary(),
        fetchSchedulerLogs(),
        fetchBullSearchProcess(),
        fetchThemes(marketCode),
        fetchUniverse().catch(() => []),
        fetchSeeds(marketCode),
        fetchCandidates(marketCode),
        fetchWatchlist(marketCode),
        fetchSignals(marketCode),
        fetchOrders(marketCode),
        fetchPositions(marketCode),
      ])

      state.health = health
      state.dataSources = dataSources
      state.summary = summary
      state.schedulerLogs = schedulerLogs
      state.bullProcess = bullProcess
      state.themes = themes
      state.industryThemes = themes.filter((item) => item.theme_type === 'industry')
      state.universe = universe
      state.seeds = seeds
      state.candidates = candidates
      state.watchlist = watchlist
      state.signals = signals
      state.orders = orders
      state.positions = positions
      state.lastLoadedAt = new Date().toLocaleString('zh-CN', { hour12: false })
      hasLoaded = true
    } catch (error) {
      state.error = error instanceof Error ? error.message : '加载数据失败'
    } finally {
      state.loading = false
      pendingLoad = null
    }
  })()

  return pendingLoad
}

async function ensureDashboardLoaded() {
  if (hasLoaded || pendingLoad) {
    return pendingLoad
  }
  return loadDashboard()
}

async function handleRunDaily(payload) {
  state.running = true
  state.error = ''
  state.notice = ''

  try {
    const result = await runDailyWorkflow(payload)
    state.runResult = result
    state.notice = `执行完成：${result.trade_date}，候选 ${result.selected_candidates}，观察池 ${result.watchlist_count}，信号 ${result.generated_signals}。`
    await loadDashboard()
    return result
  } catch (error) {
    state.error = error instanceof Error ? error.message : '执行每日流程失败'
    throw error
  } finally {
    state.running = false
  }
}

watch(
  () => state.selectedMarket,
  () => {
    if (hasLoaded) {
      void loadDashboard()
    }
  },
)

export function useDashboardState() {
  return {
    state,
    marketOptions,
    navMetrics,
    ensureDashboardLoaded,
    loadDashboard,
    handleRunDaily,
  }
}
