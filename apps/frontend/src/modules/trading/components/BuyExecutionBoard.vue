<script setup>
import { computed } from 'vue'

import { formatDateTime, formatMoney, formatNumber } from '../../../lib/format'

const props = defineProps({
  signals: {
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
})

const emit = defineEmits(['refresh'])

const summary = computed(() => {
  const markets = new Set()
  let latestTradeDate = ''

  props.signals.forEach((item) => {
    if (item.market_code) {
      markets.add(item.market_code)
    }
    if (!latestTradeDate && item.trade_date) {
      latestTradeDate = item.trade_date
    }
  })

  return {
    count: props.signals.length,
    marketCount: markets.size,
    latestTradeDate,
  }
})

const marketLabel = computed(() => (props.selectedMarket === 'ALL' ? '全部市场' : props.selectedMarket))
</script>

<template>
  <section class="panel">
    <div class="panel-heading">
      <div>
        <p class="panel-kicker">Trade Execution</p>
        <h2>当日可买入股票</h2>
      </div>
      <div class="overview-heading-actions">
        <span class="panel-meta">{{ loading ? '更新中' : `共 ${summary.count} 只可买入股票` }}</span>
        <button class="ghost-button overview-refresh-button" type="button" :disabled="loading" @click="emit('refresh')">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
      </div>
    </div>

    <div class="stats-grid compact-grid">
      <article class="stat-card">
        <p>筛选范围</p>
        <strong>{{ marketLabel }}</strong>
        <span>只保留已触发的 BUY 信号</span>
      </article>
      <article class="stat-card">
        <p>可买入股票</p>
        <strong>{{ summary.count }}</strong>
        <span>按量能强度排序展示</span>
      </article>
      <article class="stat-card">
        <p>覆盖市场</p>
        <strong>{{ summary.marketCount }}</strong>
        <span>{{ summary.latestTradeDate ? formatDateTime(summary.latestTradeDate) : '--' }}</span>
      </article>
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>股票</th>
            <th>市场</th>
            <th>信号类型</th>
            <th>收盘 / 量能</th>
            <th>阈值</th>
            <th>买入金额</th>
            <th>执行说明</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="signal in signals" :key="`${signal.market_code}-${signal.ticker}-${signal.trade_date}-${signal.signal_type}`">
            <td>
              <strong>{{ signal.ticker }}</strong>
              <small>{{ formatDateTime(signal.trade_date) }}</small>
            </td>
            <td>{{ signal.market_code }}</td>
            <td>
              <strong>{{ signal.signal_type }}</strong>
              <small>{{ signal.side }}</small>
            </td>
            <td>
              <div class="factor-stack">
                <span>Close {{ formatNumber(signal.close) }}</span>
                <span>VR5 {{ formatNumber(signal.volume_ratio_5d) }}</span>
              </div>
            </td>
            <td>{{ formatNumber(signal.threshold_volume_ratio) }}</td>
            <td>{{ formatMoney(signal.order_notional) }}</td>
            <td class="decision-cell">
              <strong>{{ signal.signal_reason }}</strong>
              <small>{{ signal.triggered ? '已满足买入条件' : '未触发' }}</small>
            </td>
          </tr>
          <tr v-if="!signals.length">
            <td colspan="7" class="empty-cell">{{ loading ? '正在加载可买入股票...' : '当前没有可买入股票。' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
