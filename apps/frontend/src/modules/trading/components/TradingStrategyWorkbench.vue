<script setup>
import { computed } from 'vue'

import { formatDateTime, formatMoney, formatNumber } from '../../../lib/format'

const props = defineProps({
  signals: {
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

const strategyEntries = [
  {
    key: 'buy_only',
    title: '只看 BUY 信号',
    summary: '交易策略页只关注触发买入的条件，不展示卖出和平仓策略。',
    details: [
      '当前页面只围绕 BUY_VOLUME_SURGE 这一类买入触发逻辑展示。',
      '未触发或 SELL 类型的信号不作为买入条件展示主体。',
    ],
  },
  {
    key: 'volume_surge',
    title: '量能放大触发',
    summary: '只有 5 日量比达到阈值，才会触发买入信号。',
    details: [
      '核心条件是 volume_ratio_5d >= threshold_volume_ratio。',
      '如果量能没有放大到阈值以上，只记录信号，不执行买入。',
    ],
  },
  {
    key: 'triggered_only',
    title: '必须已触发',
    summary: '只有 triggered=true 的 BUY 信号才进入可买入结果。',
    details: [
      '页面结果区只展示当前真正满足买入条件的股票。',
      '未触发的 BUY 信号不进入当前可买入结果。',
    ],
  },
  {
    key: 'fixed_notional',
    title: '固定金额下单',
    summary: '触发后按固定买入金额生成订单。',
    details: [
      '当前执行层不是按主观仓位，而是按固定 order_notional 进行纸面下单。',
      '页面会直接展示当前策略对应的买入金额。',
    ],
  },
]

const visibleSignals = computed(() => props.signals.filter((item) => props.selectedMarket === 'ALL' || item.market_code === props.selectedMarket))
const buySignals = computed(() => visibleSignals.value.filter((item) => item.side === 'BUY'))
const triggeredBuySignals = computed(() => buySignals.value.filter((item) => item.triggered))
const latestTradeDate = computed(() => triggeredBuySignals.value[0]?.trade_date || buySignals.value[0]?.trade_date || null)
const currentThreshold = computed(() => Number(buySignals.value[0]?.threshold_volume_ratio ?? 0))
const currentNotional = computed(() => Number(buySignals.value[0]?.order_notional ?? 0))
</script>

<template>
  <section class="view-stack bull-strategy-stack">
    <section class="panel strategy-current-panel">
      <div class="panel-heading">
        <div>
          <p class="panel-kicker">Trading Strategy</p>
          <h2>当前买入触发条件</h2>
        </div>
        <span class="panel-meta">{{ latestTradeDate ? formatDateTime(latestTradeDate) : (loading ? '加载中' : '暂无数据') }}</span>
      </div>

      <div class="strategy-current-grid">
        <article class="strategy-metric-card">
          <span>买入信号类型</span>
          <strong>BUY_VOLUME_SURGE</strong>
        </article>
        <article class="strategy-metric-card">
          <span>量能阈值</span>
          <strong>{{ formatNumber(currentThreshold) }}</strong>
        </article>
        <article class="strategy-metric-card">
          <span>固定买入金额</span>
          <strong>{{ formatMoney(currentNotional) }}</strong>
        </article>
      </div>

      <p class="strategy-description">
        当前交易策略页只展示触发买入的条件。核心逻辑是观察池股票出现 BUY_VOLUME_SURGE 信号，且 5 日量比达到系统阈值后，
        才进入可买入结果，并按固定金额生成买入订单。
      </p>
    </section>

    <section class="panel strategy-list-panel">
      <div class="panel-heading">
        <div>
          <p class="panel-kicker">Buy Rules</p>
          <h2>当前买入策略</h2>
        </div>
        <span class="panel-meta">只看触发买入条件</span>
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
          <h2>当前满足买入条件的股票</h2>
        </div>
        <span class="panel-meta">BUY 信号 {{ buySignals.length }} / 已触发 {{ triggeredBuySignals.length }}</span>
      </div>

      <div class="process-grid">
        <article v-for="signal in triggeredBuySignals" :key="`${signal.market_code}-${signal.ticker}-${signal.trade_date}-${signal.signal_type}`" class="process-card tone-bull">
          <div class="process-header">
            <div>
              <p class="process-code">{{ signal.ticker }}</p>
              <p class="process-sub">{{ signal.market_code }} / {{ signal.trade_date ? formatDateTime(signal.trade_date) : '--' }}</p>
            </div>
            <div class="market-overview-score">
              <span class="badge">BUY</span>
              <strong>{{ signal.signal_type }}</strong>
            </div>
          </div>

          <div class="process-metrics">
            <div>
              <span>收盘价</span>
              <strong>{{ formatNumber(signal.close) }}</strong>
            </div>
            <div>
              <span>5日量比</span>
              <strong>{{ formatNumber(signal.volume_ratio_5d) }}</strong>
            </div>
            <div>
              <span>触发阈值</span>
              <strong>{{ formatNumber(signal.threshold_volume_ratio) }}</strong>
            </div>
          </div>

          <div class="process-metrics">
            <div>
              <span>买入金额</span>
              <strong>{{ formatMoney(signal.order_notional) }}</strong>
            </div>
            <div>
              <span>触发状态</span>
              <strong>{{ signal.triggered ? '已触发' : '未触发' }}</strong>
            </div>
            <div>
              <span>信号来源</span>
              <strong>{{ signal.source || '--' }}</strong>
            </div>
          </div>

          <p class="process-decision">{{ signal.signal_reason }}</p>
        </article>
      </div>

      <p v-if="!triggeredBuySignals.length && !loading" class="strategy-empty">当前没有满足买入条件的股票。</p>
    </section>
  </section>
</template>
