<script setup>
import { onMounted, ref } from 'vue'

import { fetchMarketOverview, runBullSearch } from '../lib/api'
import MarketOverviewTable from '../modules/markets/components/MarketOverviewTable.vue'

const rows = ref([])
const loading = ref(false)
const runningBullSearch = ref(false)
const error = ref('')
const notice = ref('')

function sortRows(items) {
  const regimeRank = {
    BULL: 0,
    NEUTRAL: 1,
    BEAR: 2,
  }

  return [...items].sort((left, right) => {
    const leftRank = regimeRank[left.regime_status] ?? 3
    const rightRank = regimeRank[right.regime_status] ?? 3
    if (leftRank !== rightRank) {
      return leftRank - rightRank
    }

    const leftScore = Number(left.bull_score ?? Number.NEGATIVE_INFINITY)
    const rightScore = Number(right.bull_score ?? Number.NEGATIVE_INFINITY)
    if (leftScore !== rightScore) {
      return rightScore - leftScore
    }

    return String(left.market_code).localeCompare(String(right.market_code))
  })
}

async function loadOverview() {
  loading.value = true
  error.value = ''
  try {
    rows.value = sortRows(await fetchMarketOverview())
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载市场筛选失败'
    rows.value = []
  } finally {
    loading.value = false
  }
}

async function executeBullSearch() {
  runningBullSearch.value = true
  error.value = ''
  notice.value = ''

  try {
    const result = await runBullSearch({ market_codes: ['ALL'] })
    notice.value = `牛市筛选完成：${result.trade_date}，扫描 ${result.processed_markets} 个市场，筛出 ${result.bull_market_count} 个牛市市场。`
    await loadOverview()
  } catch (err) {
    error.value = err instanceof Error ? err.message : '执行牛市筛选失败'
  } finally {
    runningBullSearch.value = false
  }
}

onMounted(() => {
  void loadOverview()
})
</script>

<template>
  <section class="view-stack overview-stack">
    <MarketOverviewTable
      :rows="rows"
      :loading="loading"
      :running-bull-search="runningBullSearch"
      :error="error"
      :notice="notice"
      @refresh="loadOverview"
      @run-bull-search="executeBullSearch"
    />
  </section>
</template>
