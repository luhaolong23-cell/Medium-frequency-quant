<script setup>
import { computed, onMounted, ref, watch } from 'vue'

import { fetchUniverse } from '../lib/api'
import { useDashboardState } from '../lib/dashboard-state'
import { buildMarketUniverseRows } from '../modules/markets/components/market-universe-groups'

const { state, marketOptions, ensureDashboardLoaded } = useDashboardState()

const selectedMarket = ref('')
const loading = ref(false)
const error = ref('')
const universeRows = ref([])

const availableMarkets = computed(() => marketOptions.value.filter((item) => item !== 'ALL'))
const selectedUniverseRows = computed(() => buildMarketUniverseRows(universeRows.value, selectedMarket.value))

function formatNumber(value, digits = 2) {
  if (value === null || value === undefined || value === '') {
    return '--'
  }
  return Number(value).toLocaleString('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })
}

function formatCompactNumber(value) {
  if (value === null || value === undefined || value === '') {
    return '--'
  }
  return Number(value).toLocaleString('zh-CN', {
    notation: 'compact',
    maximumFractionDigits: 2,
  })
}

async function loadUniverse() {
  if (!selectedMarket.value) {
    universeRows.value = []
    return
  }

  loading.value = true
  error.value = ''

  try {
    universeRows.value = await fetchUniverse(selectedMarket.value)
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载市场股票池失败'
  } finally {
    loading.value = false
  }
}

watch(availableMarkets, (markets) => {
  if (!markets.length) {
    selectedMarket.value = ''
    universeRows.value = []
    return
  }
  if (!markets.includes(selectedMarket.value)) {
    selectedMarket.value = state.selectedMarket !== 'ALL' && markets.includes(state.selectedMarket)
      ? state.selectedMarket
      : markets[0]
  }
}, { immediate: true })

watch(selectedMarket, () => {
  void loadUniverse()
})

onMounted(async () => {
  await ensureDashboardLoaded()
  if (!selectedMarket.value && availableMarkets.value.length) {
    selectedMarket.value = state.selectedMarket !== 'ALL' && availableMarkets.value.includes(state.selectedMarket)
      ? state.selectedMarket
      : availableMarkets.value[0]
  }
})
</script>

<template>
  <section class="panel market-universe-panel">
    <div class="panel-heading">
      <div>
        <p class="panel-kicker">Market Universe</p>
        <h2>市场股票池</h2>
      </div>
    </div>

    <div class="hero-toolbar market-universe-toolbar">
      <label class="toolbar-field">
        <span>选择市场</span>
        <select v-model="selectedMarket">
          <option v-for="market in availableMarkets" :key="market" :value="market">
            {{ market }}
          </option>
        </select>
      </label>
    </div>

    <div v-if="error" class="banner banner-error">
      {{ error }}
    </div>

    <div v-else-if="loading" class="banner banner-notice">
      正在加载 {{ selectedMarket }} 股票池...
    </div>

    <div v-else-if="selectedUniverseRows.length" class="table-wrap">
      <table class="data-table market-universe-table">
        <thead>
          <tr>
            <th>股票</th>
            <th>公司</th>
            <th>行业</th>
            <th>价格</th>
            <th>市值</th>
            <th>动量</th>
            <th>量比</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in selectedUniverseRows" :key="row.ticker">
            <td><strong>{{ row.ticker }}</strong></td>
            <td>{{ row.company_name || '--' }}</td>
            <td>{{ row.industry || row.sector || '--' }}</td>
            <td>{{ formatNumber(row.price) }}</td>
            <td>{{ formatCompactNumber(row.market_cap) }}</td>
            <td>{{ formatNumber(row.momentum_pct) }}%</td>
            <td>{{ formatNumber(row.volume_ratio) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <p v-else class="sidebar-copy">当前还没有可展示的本地股票池。</p>
  </section>
</template>
