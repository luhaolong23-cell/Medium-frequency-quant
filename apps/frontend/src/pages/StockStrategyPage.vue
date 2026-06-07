<script setup>
import { useDashboardState } from '../lib/dashboard-state'
import StockStrategyWorkbench from '../modules/selection/components/StockStrategyWorkbench.vue'

const { state } = useDashboardState()
</script>

<template>
  <StockStrategyWorkbench
    :watchlist="state.watchlist"
    :seeds="state.seeds"
    :themes="state.themes"
    :selected-market="state.selectedMarket"
    :loading="state.loading"
  />
</template>
