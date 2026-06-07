<script setup>
import { useDashboardState } from '../lib/dashboard-state'
import OpenPositionsPanel from '../modules/trading/components/OpenPositionsPanel.vue'
import SignalOrderTimeline from '../modules/trading/components/SignalOrderTimeline.vue'
import RunDailyPanel from '../modules/system/components/RunDailyPanel.vue'

const { state, marketOptions, handleRunDaily } = useDashboardState()

async function submit(payload) {
  await handleRunDaily(payload)
}
</script>

<template>
  <section class="view-stack ops-layout">
    <RunDailyPanel
      :running="state.running"
      :result="state.runResult"
      :selected-market="state.selectedMarket"
      :market-options="marketOptions"
      @submit="submit"
    />

    <div class="duo-grid">
      <SignalOrderTimeline
        :signals="state.signals"
        :orders="state.orders"
        :loading="state.loading"
      />
      <OpenPositionsPanel :positions="state.positions" :loading="state.loading" />
    </div>
  </section>
</template>
