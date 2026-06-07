<script setup>
import { useDashboardState } from '../lib/dashboard-state'
import BullStrategyWorkbench from '../modules/markets/components/BullStrategyWorkbench.vue'

const { state } = useDashboardState()
</script>

<template>
  <BullStrategyWorkbench
    :process="state.bullProcess"
    :selected-market="state.selectedMarket"
    :loading="state.loading"
  />
</template>
