<script setup>
import { useDashboardState } from '../lib/dashboard-state'
import DataSourceWorkbench from '../modules/data-sources/components/DataSourceWorkbench.vue'

const { state, loadDashboard } = useDashboardState()
</script>

<template>
  <DataSourceWorkbench
    :catalog="state.dataSources"
    :loading="state.loading"
    @refresh="loadDashboard"
  />
</template>
