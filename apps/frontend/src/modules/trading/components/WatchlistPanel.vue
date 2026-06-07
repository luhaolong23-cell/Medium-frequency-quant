<script setup>
import { computed } from 'vue'

import { formatNumber, formatPercent } from '../../../lib/format'

const props = defineProps({
  watchlist: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
})

const cards = computed(() => [...props.watchlist].sort((left, right) => left.watch_rank - right.watch_rank).slice(0, 5))
</script>

<template>
  <section class="panel side-panel">
    <div class="panel-heading">
      <div>
        <p class="panel-kicker">Watchlist</p>
        <h2>前 5 补涨观察池</h2>
      </div>
      <span class="panel-meta">{{ loading ? '更新中' : '即时盯盘名单' }}</span>
    </div>

    <div class="watchlist-stack">
      <article v-for="item in cards" :key="`${item.market_code}-${item.ticker}`" class="watch-card">
        <div class="watch-top">
          <strong>#{{ item.watch_rank }} {{ item.ticker }}</strong>
          <span>{{ item.market_code }}</span>
        </div>
        <p class="watch-name">{{ item.company_name }}</p>
        <p class="watch-reason">{{ item.watch_reason }}</p>
        <div class="watch-metrics">
          <span>综合 {{ formatNumber(item.composite_score) }}</span>
          <span>补涨 {{ formatNumber(item.lagging_score) }}</span>
          <span>趋势 {{ formatNumber(item.trend_recovery_score) }}</span>
        </div>
        <div class="watch-metrics">
          <span>5D {{ formatPercent(item.ret_5d) }}</span>
          <span>VR3 {{ formatNumber(item.volume_ratio_3d) }}</span>
          <span>距60高点 {{ formatPercent(item.distance_to_60d_high) }}</span>
        </div>
      </article>
    </div>
  </section>
</template>
