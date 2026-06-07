<script setup>
import { computed } from 'vue'

import { formatDateTime, formatNumber } from '../../../lib/format'
import BullFactorList from './BullFactorList.vue'

const props = defineProps({
  rows: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  runningBullSearch: {
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

const emit = defineEmits(['refresh', 'run-bull-search'])

const hasRows = computed(() => props.rows.length > 0)
const summary = computed(() => {
  const counts = {
    total: props.rows.length,
    bull: 0,
    neutral: 0,
    bear: 0,
    latestTradeDate: '',
  }

  props.rows.forEach((item) => {
    if (item.regime_status === 'BULL') {
      counts.bull += 1
    } else if (item.regime_status === 'NEUTRAL') {
      counts.neutral += 1
    } else if (item.regime_status === 'BEAR') {
      counts.bear += 1
    }

    if (!counts.latestTradeDate && item.trade_date) {
      counts.latestTradeDate = item.trade_date
    }
  })

  return counts
})

const summaryCards = computed(() => [
  { label: '总市场数', value: summary.value.total, tone: 'tone-neutral' },
  { label: '牛市', value: summary.value.bull, tone: 'tone-bull' },
  { label: '观望', value: summary.value.neutral, tone: 'tone-neutral' },
  { label: '熊市', value: summary.value.bear, tone: 'tone-bear' },
])

function regimeTone(status) {
  if (status === 'BULL') {
    return 'tone-bull'
  }
  if (status === 'NEUTRAL') {
    return 'tone-neutral'
  }
  if (status === 'BEAR') {
    return 'tone-bear'
  }
  return 'tone-neutral'
}
</script>

<template>
  <section class="panel overview-panel">
    <div class="panel-heading">
      <div>
        <p class="panel-kicker">Market Screen</p>
        <h2>市场筛选总览</h2>
      </div>
      <div class="overview-heading-actions">
        <span class="panel-meta">{{ loading ? '更新中' : `共 ${rows.length} 个市场` }}</span>
        <button class="ghost-button overview-refresh-button" type="button" :disabled="loading || runningBullSearch" @click="emit('refresh')">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
        <button class="primary-button overview-run-button" type="button" :disabled="loading || runningBullSearch" @click="emit('run-bull-search')">
          {{ runningBullSearch ? '筛选中...' : '执行牛市筛选' }}
        </button>
      </div>
    </div>

    <div v-if="error" class="banner banner-error overview-banner">
      {{ error }}
    </div>
    <div v-else-if="notice" class="banner banner-notice overview-banner">
      {{ notice }}
    </div>

    <div class="overview-summary-grid">
      <article
        v-for="card in summaryCards"
        :key="card.label"
        class="overview-summary-card"
        :class="card.tone"
      >
        <span>{{ card.label }}</span>
        <strong>{{ formatNumber(card.value, 0) }}</strong>
      </article>
      <article class="overview-summary-card tone-neutral overview-summary-date">
        <span>数据日期</span>
        <strong>{{ summary.latestTradeDate ? formatDateTime(summary.latestTradeDate) : '--' }}</strong>
      </article>
    </div>

    <div class="market-overview-list">
      <article v-if="loading && !hasRows" class="panel market-overview-card market-overview-empty">
        加载中...
      </article>
      <article v-else-if="!loading && !hasRows" class="panel market-overview-card market-overview-empty">
        暂无市场数据
      </article>
      <article v-for="item in rows" :key="item.market_code" class="panel market-overview-card">
        <div class="market-overview-top">
          <div>
            <p class="process-code">{{ item.market_code }}</p>
            <p class="process-sub">{{ item.market_name }} / {{ item.country_code }} / {{ item.region || '--' }}</p>
          </div>
          <div class="market-overview-score">
            <span class="badge" :class="regimeTone(item.regime_status)">{{ item.regime_status || 'N/A' }}</span>
            <strong>{{ formatNumber(item.bull_score) }}</strong>
            <small>{{ item.is_bull ? '已进入牛市名单' : '未进入牛市名单' }}</small>
          </div>
        </div>

        <BullFactorList :item="item" />

        <div class="market-overview-footer">
          <strong>{{ item.decision_reason || '暂无判定说明' }}</strong>
          <small>{{ item.trade_date ? formatDateTime(item.trade_date) : '--' }} / {{ item.feature_source || '--' }} / {{ item.price_proxy || '--' }}</small>
        </div>
      </article>
    </div>
  </section>
</template>
