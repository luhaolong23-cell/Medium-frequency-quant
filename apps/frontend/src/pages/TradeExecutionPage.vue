<script setup>
import { computed } from 'vue'

import { useDashboardState } from '../lib/dashboard-state'
import BuyExecutionBoard from '../modules/trading/components/BuyExecutionBoard.vue'

const { state, loadDashboard } = useDashboardState()

const buySignals = computed(() => {
  return [...state.signals]
    .filter((item) => item.side === 'BUY' && item.triggered)
    .sort((left, right) => Number(right.volume_ratio_5d ?? 0) - Number(left.volume_ratio_5d ?? 0))
})
</script>

<template>
  <BuyExecutionBoard
    :signals="buySignals"
    :loading="state.loading"
    :selected-market="state.selectedMarket"
    @refresh="loadDashboard"
  />
</template>
