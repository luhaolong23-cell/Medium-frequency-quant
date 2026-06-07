<script setup>
import { computed, ref, watch } from 'vue'

import { formatDateTime, formatMoney, formatNumber, formatPercent, toneForPnL } from '../../../lib/format'

const props = defineProps({
  positions: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  selectedMarket: {
    type: String,
    default: 'ALL',
  },
  runningSell: {
    type: Boolean,
    default: false,
  },
  error: {
    type: String,
    default: '',
  },
  notice: {
    type: String,
    default: '',
  },
})

const emit = defineEmits(['refresh', 'sell-selected'])
const selectedKeys = ref([])

function positionKey(position) {
  return `${position.market_code}:${position.ticker}`
}

const positionKeys = computed(() => props.positions.map((position) => positionKey(position)))
const selectedPositions = computed(() => {
  const selected = new Set(selectedKeys.value)
  return props.positions
    .filter((position) => selected.has(positionKey(position)))
    .map((position) => ({ market_code: position.market_code, ticker: position.ticker }))
})
const allSelected = computed(() => positionKeys.value.length > 0 && positionKeys.value.every((key) => selectedKeys.value.includes(key)))

watch(
  () => props.positions,
  (positions) => {
    const next = new Set(positions.map((position) => positionKey(position)))
    selectedKeys.value = selectedKeys.value.filter((key) => next.has(key))
  },
  { deep: true },
)

const summary = computed(() => {
  let pnl = 0
  let latestTradeDate = ''

  props.positions.forEach((item) => {
    pnl += Number(item.unrealized_pnl ?? 0)
    if (!latestTradeDate && item.last_trade_date) {
      latestTradeDate = item.last_trade_date
    }
  })

  return {
    count: props.positions.length,
    pnl,
    latestTradeDate,
  }
})

const marketLabel = computed(() => (props.selectedMarket === 'ALL' ? '全部市场' : props.selectedMarket))

function toggleAll(event) {
  selectedKeys.value = event.target.checked ? [...positionKeys.value] : []
}

function submitSell() {
  emit('sell-selected', selectedPositions.value)
}
</script>

<template>
  <section class="panel">
    <div class="panel-heading">
      <div>
        <p class="panel-kicker">Position Watch</p>
        <h2>当前持仓</h2>
      </div>
      <div class="overview-heading-actions">
        <span class="panel-meta">{{ loading ? '更新中' : `共 ${summary.count} 个持仓 / 已选 ${selectedPositions.length} 个` }}</span>
        <button class="ghost-button overview-refresh-button" type="button" :disabled="loading || runningSell" @click="emit('refresh')">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
        <button class="primary-button overview-run-button" type="button" :disabled="loading || runningSell || !selectedPositions.length" @click="submitSell">
          {{ runningSell ? '卖出中...' : '执行卖出' }}
        </button>
      </div>
    </div>

    <div v-if="error" class="banner banner-error overview-banner">
      {{ error }}
    </div>
    <div v-else-if="notice" class="banner banner-notice overview-banner">
      {{ notice }}
    </div>

    <div class="stats-grid compact-grid">
      <article class="stat-card">
        <p>观察范围</p>
        <strong>{{ marketLabel }}</strong>
        <span>仅展示当前 OPEN 持仓</span>
      </article>
      <article class="stat-card">
        <p>持仓数量</p>
        <strong>{{ summary.count }}</strong>
        <span>{{ summary.latestTradeDate ? formatDateTime(summary.latestTradeDate) : '--' }}</span>
      </article>
      <article class="stat-card">
        <p>浮动盈亏</p>
        <strong :class="toneForPnL(summary.pnl)">{{ formatMoney(summary.pnl) }}</strong>
        <span>当前未实现盈亏汇总</span>
      </article>
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>
              <input type="checkbox" :checked="allSelected" :disabled="!positions.length" @change="toggleAll" />
            </th>
            <th>股票</th>
            <th>市场</th>
            <th>持仓规模</th>
            <th>价格观察</th>
            <th>盈亏</th>
            <th>风控观察</th>
            <th>最近信号</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="position in positions" :key="`${position.market_code}-${position.ticker}-${position.opened_trade_date}`">
            <td>
              <input v-model="selectedKeys" type="checkbox" :value="positionKey(position)" />
            </td>
            <td>
              <strong>{{ position.ticker }}</strong>
              <small>{{ formatDateTime(position.opened_trade_date) }}</small>
            </td>
            <td>{{ position.market_code }}</td>
            <td>
              <div class="factor-stack">
                <span>Qty {{ formatNumber(position.quantity, 4) }}</span>
                <span>{{ formatMoney(position.invested_notional) }}</span>
              </div>
            </td>
            <td>
              <div class="factor-stack">
                <span>Avg {{ formatNumber(position.avg_price) }}</span>
                <span>Last {{ formatNumber(position.last_close) }}</span>
                <span>Peak {{ formatNumber(position.peak_price) }}</span>
              </div>
            </td>
            <td>
              <div class="factor-stack">
                <span :class="toneForPnL(position.unrealized_pnl)">{{ formatMoney(position.unrealized_pnl) }}</span>
                <span :class="toneForPnL(position.unrealized_return)">{{ formatPercent(position.unrealized_return) }}</span>
              </div>
            </td>
            <td>
              <div class="factor-stack">
                <span>VR5 {{ formatNumber(position.last_volume_ratio_5d) }}</span>
                <span>回落 {{ formatNumber(position.consecutive_decline_days, 0) }} 天</span>
                <span>{{ position.status }}</span>
              </div>
            </td>
            <td class="decision-cell">
              <strong>{{ position.last_signal_type }}</strong>
              <small>{{ position.last_signal_reason }}</small>
            </td>
          </tr>
          <tr v-if="!positions.length">
            <td colspan="8" class="empty-cell">{{ loading ? '正在加载持仓...' : '当前没有持仓。' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
