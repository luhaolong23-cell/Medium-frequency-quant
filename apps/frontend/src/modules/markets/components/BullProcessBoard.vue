<script setup>
import { computed } from 'vue'

import { formatDateTime, formatNumber, toneForRegime } from '../../../lib/format'
import BullFactorList from './BullFactorList.vue'

const props = defineProps({
  process: {
    type: Object,
    default: null,
  },
  selectedMarket: {
    type: String,
    default: 'ALL',
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const markets = computed(() => {
  const rows = props.process?.markets || []
  if (props.selectedMarket === 'ALL') {
    return rows
  }
  return rows.filter((item) => item.market_code === props.selectedMarket)
})
</script>

<template>
  <section class="panel">
    <div class="panel-heading">
      <div>
        <p class="panel-kicker">Regime Engine</p>
        <h2>判定过程</h2>
      </div>
      <span class="panel-meta">
        {{ process?.trade_date || (loading ? '加载中' : '暂无数据') }}
      </span>
    </div>

    <div class="process-grid bull-process-grid">
      <article
        v-for="item in markets"
        :key="item.market_code"
        class="process-card bull-process-card"
        :class="[toneForRegime(item.regime_status), { focused: selectedMarket === item.market_code }]"
      >
        <div class="process-header">
          <div>
            <p class="process-code">{{ item.market_code }}</p>
            <p class="process-sub">代理 {{ item.price_proxy || '--' }} / 来源 {{ item.feature_source || '--' }}</p>
          </div>
          <div class="market-overview-score">
            <span class="badge">{{ item.regime_status }}</span>
            <strong>{{ formatNumber(item.bull_score) }}</strong>
          </div>
        </div>

        <BullFactorList :item="item" />

        <p class="process-decision">{{ item.decision_reason }}</p>
        <p class="process-sub">数据日期 {{ item.trade_date ? formatDateTime(item.trade_date) : '--' }}</p>
      </article>
    </div>
  </section>
</template>
