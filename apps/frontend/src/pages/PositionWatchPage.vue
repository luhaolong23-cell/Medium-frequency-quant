<script setup>
import { computed, ref } from 'vue'

import { runPositionSell } from '../lib/api'
import { useDashboardState } from '../lib/dashboard-state'
import PositionWatchBoard from '../modules/trading/components/PositionWatchBoard.vue'

const { state, loadDashboard } = useDashboardState()
const runningSell = ref(false)
const error = ref('')
const notice = ref('')

const visiblePositions = computed(() => {
  return [...state.positions].sort((left, right) => Number(right.unrealized_pnl ?? 0) - Number(left.unrealized_pnl ?? 0))
})

async function executeSell(selectedPositions) {
  runningSell.value = true
  error.value = ''
  notice.value = ''

  try {
    const result = await runPositionSell({ positions: selectedPositions })
    notice.value = `卖出完成：请求 ${result.requested_count} 个持仓，实际卖出 ${result.sold_count} 个。`
    await loadDashboard()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '执行卖出失败'
  } finally {
    runningSell.value = false
  }
}
</script>

<template>
  <PositionWatchBoard
    :positions="visiblePositions"
    :loading="state.loading"
    :selected-market="state.selectedMarket"
    :running-sell="runningSell"
    :error="error"
    :notice="notice"
    @refresh="loadDashboard"
    @sell-selected="executeSell"
  />
</template>
