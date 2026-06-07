<script setup>
import { computed } from 'vue'

import { formatNumber, toneForRegime } from '../../../lib/format'

const props = defineProps({
  regimes: {
    type: Array,
    default: () => [],
  },
  tracked: {
    type: Array,
    default: () => [],
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

const trackedMap = computed(() => new Set(props.tracked.map((item) => item.market_code)))
</script>

<template>
  <section class="panel">
    <div class="panel-heading">
      <div>
        <p class="panel-kicker">Markets</p>
        <h2>全球市场状态带</h2>
      </div>
      <span class="panel-meta">{{ loading ? '数据刷新中' : '最新市场快照' }}</span>
    </div>

    <div class="ribbon-grid">
      <article
        v-for="item in regimes"
        :key="item.market_code"
        class="ribbon-card"
        :class="[toneForRegime(item.regime_status), { focused: selectedMarket === item.market_code }]"
      >
        <div class="ribbon-top">
          <p class="ribbon-code">{{ item.market_code }}</p>
          <span class="badge">{{ item.regime_status }}</span>
        </div>
        <p class="ribbon-score">{{ formatNumber(item.bull_score) }}</p>
        <p class="ribbon-label">bull score</p>
        <p class="ribbon-foot">
          {{ trackedMap.has(item.market_code) ? '已纳入牛市跟踪名单' : '尚未进入跟踪名单' }}
        </p>
      </article>
    </div>
  </section>
</template>
