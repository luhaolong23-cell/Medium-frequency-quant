<script setup>
import { computed, ref } from 'vue'

import { runStockScreen } from '../lib/api'
import { useDashboardState } from '../lib/dashboard-state'
import CandidatesTable from '../modules/selection/components/CandidatesTable.vue'

const { state, loadDashboard } = useDashboardState()
const runningStockScreen = ref(false)
const error = ref('')
const notice = ref('')

const visibleWatchlist = computed(() => {
  if (state.selectedMarket === 'ALL') {
    return state.watchlist
  }

  return state.watchlist.filter((item) => item.market_code === state.selectedMarket)
})

async function executeStockScreen() {
  runningStockScreen.value = true
  error.value = ''
  notice.value = ''

  try {
    const marketCodes = state.selectedMarket === 'ALL' ? ['ALL'] : [state.selectedMarket]
    const result = await runStockScreen({ market_codes: marketCodes })
    notice.value = `观察池更新完成：${result.trade_date}，覆盖 ${result.tracked_market_count} 个牛市市场，产出 ${result.watchlist_count} 只观察池股票。`
    await loadDashboard()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '更新观察池失败'
  } finally {
    runningStockScreen.value = false
  }
}
</script>

<template>
  <CandidatesTable
    :watchlist="visibleWatchlist"
    :loading="state.loading"
    :selected-market="state.selectedMarket"
    :running-stock-screen="runningStockScreen"
    :error="error"
    :notice="notice"
    @refresh="loadDashboard"
    @run-stock-screen="executeStockScreen"
  />
</template>
