<script setup>
import { computed } from 'vue'

import { formatDateTime, formatNumber, formatPercent, toneForRegime } from '../../../lib/format'
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

const strategyEntries = [
  {
    key: 'policy_breakout',
    title: '政策点火型',
    summary: '适合政策驱动、放量启动的牛市。',
    details: [
      '看货币宽松、单日放量上涨和短期趋势转强。',
      '更适合识别类似政策落地后的快速启动行情。',
    ],
  },
  {
    key: 'trend_persistence',
    title: '趋势慢牛型',
    summary: '适合中长期趋势持续上行的牛市。',
    details: [
      '看 60/120 日收益、MA60/MA120 结构和相对全球强弱。',
      '重点补足慢牛、阴涨、持续抬升类市场。',
    ],
  },
  {
    key: 'recovery_reversal',
    title: '超跌反转型',
    summary: '适合熊转牛、修复型反转行情。',
    details: [
      '看 5 日/20 日修复、均线重回站上和周线连续走强。',
      '重点识别深跌后的趋势反转，而不是单日脉冲。',
    ],
  },
  {
    key: 'global_leader',
    title: '全球强势型',
    summary: '适合长期强于全球基准的领先市场。',
    details: [
      '看相对全球强弱、120 日趋势和回撤控制。',
      '更适合识别美股、日股这类全球龙头市场。',
    ],
  },
]

const markets = computed(() => {
  const rows = props.process?.markets || []
  const filtered = props.selectedMarket === 'ALL'
    ? rows
    : rows.filter((item) => item.market_code === props.selectedMarket)

  return [...filtered].sort((left, right) => {
    if (left.regime_status === right.regime_status) {
      return Number(right.bull_score ?? 0) - Number(left.bull_score ?? 0)
    }
    if (left.regime_status === 'BULL') {
      return -1
    }
    if (right.regime_status === 'BULL') {
      return 1
    }
    if (left.regime_status === 'NEUTRAL' && right.regime_status === 'BEAR') {
      return -1
    }
    if (left.regime_status === 'BEAR' && right.regime_status === 'NEUTRAL') {
      return 1
    }
    return 0
  })
})

const bullCount = computed(() => markets.value.filter((item) => item.regime_status === 'BULL').length)
const trackedCount = computed(() => markets.value.filter((item) => item.included_in_tracked_bull).length)
const latestTradeDate = computed(() => props.process?.trade_date || null)
</script>

<template>
  <section class="view-stack bull-strategy-stack">
    <section class="panel strategy-current-panel">
      <div class="panel-heading">
        <div>
          <p class="panel-kicker">Bull Strategy</p>
          <h2>新牛市筛选策略</h2>
        </div>
        <span class="panel-meta">{{ latestTradeDate || (loading ? '加载中' : '暂无数据') }}</span>
      </div>

      <div class="strategy-current-grid">
        <article class="strategy-metric-card">
          <span>策略结构</span>
          <strong>4 套入口并联</strong>
        </article>
        <article class="strategy-metric-card">
          <span>BULL 市场</span>
          <strong>{{ bullCount }}</strong>
        </article>
        <article class="strategy-metric-card">
          <span>跟踪市场</span>
          <strong>{{ trackedCount }}</strong>
        </article>
      </div>

      <p class="strategy-description">
        当前牛市筛选不再只靠单一路径判断，而是并联比较政策点火型、趋势慢牛型、超跌反转型、全球强势型四套入口。
        Bull Score 直接展示四套入口的最新得分和命中情况，用于识别不同类型的牛市市场。
      </p>
    </section>

    <section class="panel strategy-list-panel">
      <div class="panel-heading">
        <div>
          <p class="panel-kicker">Entry Models</p>
          <h2>四套牛市入口</h2>
        </div>
        <span class="panel-meta">并联判定</span>
      </div>

      <div class="strategy-saved-stack">
        <article v-for="entry in strategyEntries" :key="entry.key" class="saved-strategy-card active">
          <div>
            <strong>{{ entry.title }}</strong>
            <small>{{ entry.summary }}</small>
            <small v-for="detail in entry.details" :key="detail">{{ detail }}</small>
          </div>
        </article>
      </div>
    </section>

    <section class="panel strategy-result-panel">
      <div class="panel-heading">
        <div>
          <p class="panel-kicker">Result</p>
          <h2>当前市场结果</h2>
        </div>
        <span class="panel-meta">{{ markets.length }} 个市场</span>
      </div>

      <div class="process-grid">
        <article v-for="item in markets" :key="item.market_code" class="process-card" :class="toneForRegime(item.regime_status)">
          <div class="process-header">
            <div>
              <p class="process-code">{{ item.market_code }}</p>
              <p class="process-sub">
                状态 {{ item.regime_status }} / 数据 {{ item.trade_date ? formatDateTime(item.trade_date) : '--' }}
              </p>
            </div>
            <div class="market-overview-score">
              <span class="badge">{{ item.regime_status }}</span>
              <strong>{{ formatNumber(item.bull_score) }}</strong>
            </div>
          </div>

          <div class="process-metrics">
            <div>
              <span>跟踪状态</span>
              <strong>{{ item.included_in_tracked_bull ? '已跟踪' : '未跟踪' }}</strong>
            </div>
            <div>
              <span>代理</span>
              <strong>{{ item.price_proxy || '--' }}</strong>
            </div>
            <div>
              <span>相对全球强弱</span>
              <strong>{{ formatPercent(item.relative_strength_world) }}</strong>
            </div>
          </div>

          <BullFactorList :item="item" />

          <p class="process-decision">{{ item.decision_reason }}</p>
        </article>
      </div>

      <p v-if="!markets.length && !loading" class="strategy-empty">当前没有可展示的牛市策略结果。</p>
    </section>
  </section>
</template>
