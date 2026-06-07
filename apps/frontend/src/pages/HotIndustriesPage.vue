<script setup>
import { useDashboardState } from '../lib/dashboard-state'
import HotIndustriesWorkbench from '../modules/selection/components/HotIndustriesWorkbench.vue'

const { state } = useDashboardState()
</script>

<template>
  <HotIndustriesWorkbench
    :themes="state.themes"
    :selected-market="state.selectedMarket"
    :loading="state.loading"
  />
</template>
