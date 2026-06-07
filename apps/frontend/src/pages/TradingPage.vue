<script setup>
import { useDashboardState } from '../lib/dashboard-state'
import TradingStrategyWorkbench from '../modules/trading/components/TradingStrategyWorkbench.vue'

const { state } = useDashboardState()
</script>

<template>
  <TradingStrategyWorkbench
    :signals="state.signals"
    :selected-market="state.selectedMarket"
    :loading="state.loading"
  />
</template>
