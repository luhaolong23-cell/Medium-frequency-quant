<script setup>
import { computed } from 'vue'

import { formatDateTime, formatNumber, formatPercent } from '../../../lib/format'

const props = defineProps({
  watchlist: {
    type: Array,
    default: () => [],
  },
  seeds: {
    type: Array,
    default: () => [],
  },
  themes: {
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
    key: 'theme_score',
    title: '热门题材策略',
    summary: '只在当前热门题材相关股票里继续筛选。',
    details: [
      '优先保留热度高、持续性更强的题材，不在冷题材里找补涨。',
      '结合题材热度、行业归属和题材标签控制股票池范围。',
    ],
    metrics: '看 theme_tags、raw_heat_score、smoothed_heat_score、theme_score',
  },
  {
    key: 'lagging_score',
    title: '补涨潜力策略',
    summary: '找热门题材里还没主升、但有补涨空间的股票。',
    details: [
      '不是追最强龙头，而是找还没涨完、位置仍有空间的股票。',
      '重点看相对落后但没有走弱的题材内补涨机会。',
    ],
    metrics: '看 lagging_score、ret_5d、ret_20d、distance_to_60d_high',
  },
  {
    key: 'trend_recovery_score',
    title: '趋势修复策略',
    summary: '只保留趋势开始转强的股票。',
    details: [
      '要求价格和均线结构开始修复，避免把纯弱股误当成补涨股。',
      '重点确认股价是否重新站稳中短期趋势。',
    ],
    metrics: '看 trend_recovery_score、ma_20、ma_60、ret_20d、ret_60d',
  },
  {
    key: 'momentum_acceleration_score',
    title: '动量改善策略',
    summary: '只保留动量开始抬升的股票。',
    details: [
      '不是单看绝对涨幅，而是看动量是否从弱转强。',
      '更适合识别准备启动、但还没完全走出来的股票。',
    ],
    metrics: '看 momentum_acceleration_score、momentum_acceleration、ret_5d、ret_20d',
  },
  {
    key: 'volume_probe_score',
    title: '试探量能策略',
    summary: '看资金是否已经开始小范围试探进入。',
    details: [
      '不要求全量爆发，但要看到量能开始放大和资金试探。',
      '避免选到完全没有资金关注的冷门弱股。',
    ],
    metrics: '看 volume_probe_score、volume_ratio_3d、avg_dollar_volume_3d、volume_up_days_5d',
  },
  {
    key: 'risk_control_score',
    title: '风险控制策略',
    summary: '把过弱、过散、过热的股票尽量过滤掉。',
    details: [
      '控制波动和位置风险，避免仅凭题材热度选出高风险标的。',
      '最终进入观察池的股票需要在收益空间和回撤风险之间平衡。',
    ],
    metrics: '看 risk_control_score、vol_20d、distance_to_60d_high、composite_score',
  },
]

const visibleWatchlist = computed(() => {
  const rows = props.selectedMarket === 'ALL'
    ? props.watchlist
    : props.watchlist.filter((item) => item.market_code === props.selectedMarket)

  return [...rows].sort((left, right) => {
    if (left.watch_rank === right.watch_rank) {
      return Number(right.composite_score ?? 0) - Number(left.composite_score ?? 0)
    }
    return left.watch_rank - right.watch_rank
  })
})

const visibleSeeds = computed(() => {
  const rows = props.selectedMarket === 'ALL'
    ? props.seeds
    : props.seeds.filter((item) => item.market_code === props.selectedMarket)

  return [...rows].sort((left, right) => Number(right.theme_score ?? 0) - Number(left.theme_score ?? 0))
})

const themeRows = computed(() => {
  const rows = props.selectedMarket === 'ALL'
    ? props.themes
    : props.themes.filter((item) => item.market_code === props.selectedMarket)

  return [...rows].sort((left, right) => Number(right.smoothed_heat_score ?? 0) - Number(left.smoothed_heat_score ?? 0))
})

const visibleThemes = computed(() => themeRows.value.slice(0, 6))
const totalThemeCount = computed(() => themeRows.value.length)

const latestTradeDate = computed(() => {
  return visibleWatchlist.value[0]?.trade_date || visibleSeeds.value[0]?.trade_date || visibleThemes.value[0]?.trade_date || null
})

const formatTags = (tags) => (Array.isArray(tags) && tags.length ? tags.join(' / ') : '--')
</script>

<template>
  <section class="view-stack bull-strategy-stack">
    <section class="panel strategy-current-panel">
      <div class="panel-heading">
        <div>
          <p class="panel-kicker">Stock Strategy</p>
          <h2>新股票筛选策略</h2>
        </div>
        <span class="panel-meta">{{ latestTradeDate || (loading ? '加载中' : '暂无数据') }}</span>
      </div>

      <div class="strategy-current-grid">
        <article class="strategy-metric-card">
          <span>核心策略</span>
          <strong>6 项并联</strong>
        </article>
        <article class="strategy-metric-card">
          <span>当前热门题材</span>
          <strong>{{ totalThemeCount }}</strong>
        </article>
        <article class="strategy-metric-card">
          <span>待选观察股</span>
          <strong>{{ visibleWatchlist.length }}</strong>
        </article>
      </div>

      <p class="strategy-description">
        当前股票筛选会先识别每个市场各自的热门题材，再围绕补涨潜力、趋势修复、动量改善、试探量能、风险控制六项策略综合打分。
        热门题材数量不是固定值，会随市场和当日热度变化；页面这里只展示当前市场最强的前 6 个题材。
      </p>
    </section>

    <section class="panel strategy-list-panel">
      <div class="panel-heading">
        <div>
          <p class="panel-kicker">Strategy Set</p>
          <h2>当前股票筛选策略</h2>
        </div>
        <span class="panel-meta">按策略项打分</span>
      </div>

      <div class="strategy-saved-stack">
        <article v-for="entry in strategyEntries" :key="entry.key" class="saved-strategy-card active">
          <div>
            <strong>{{ entry.title }}</strong>
            <small>{{ entry.summary }}</small>
            <small v-for="detail in entry.details" :key="detail">{{ detail }}</small>
            <small>{{ entry.metrics }}</small>
          </div>
        </article>
      </div>
    </section>

    <section class="panel strategy-result-panel">
      <div class="panel-heading">
        <div>
          <p class="panel-kicker">Result</p>
          <h2>当前股票筛选结果</h2>
        </div>
        <span class="panel-meta">种子 {{ visibleSeeds.length }} / 观察池 {{ visibleWatchlist.length }} / 展示题材 {{ visibleThemes.length }}</span>
      </div>

      <div class="process-grid">
        <article v-for="item in visibleWatchlist" :key="`${item.market_code}-${item.ticker}-${item.trade_date}`" class="process-card tone-bull">
          <div class="process-header">
            <div>
              <p class="process-code">{{ item.ticker }}</p>
              <p class="process-sub">
                {{ item.market_code }} / #{{ item.watch_rank }} / {{ item.trade_date ? formatDateTime(item.trade_date) : '--' }}
              </p>
            </div>
            <div class="market-overview-score">
              <span class="badge">WATCH</span>
              <strong>{{ formatNumber(item.composite_score) }}</strong>
            </div>
          </div>

          <div class="process-metrics">
            <div>
              <span>题材标签</span>
              <strong>{{ formatTags(item.theme_tags) }}</strong>
            </div>
            <div>
              <span>Close / 5D</span>
              <strong>{{ formatNumber(item.close) }} / {{ formatPercent(item.ret_5d) }}</strong>
            </div>
            <div>
              <span>20D / MA20</span>
              <strong>{{ formatPercent(item.ret_20d) }} / {{ formatNumber(item.ma_20) }}</strong>
            </div>
          </div>

          <div class="process-metrics">
            <div>
              <span>题材分</span>
              <strong>{{ formatNumber(item.theme_score) }}</strong>
            </div>
            <div>
              <span>补涨 / 趋势</span>
              <strong>{{ formatNumber(item.lagging_score) }} / {{ formatNumber(item.trend_recovery_score) }}</strong>
            </div>
            <div>
              <span>动量 / 试探量 / 风险</span>
              <strong>{{ formatNumber(item.momentum_acceleration_score) }} / {{ formatNumber(item.volume_probe_score) }} / {{ formatNumber(item.risk_control_score) }}</strong>
            </div>
          </div>

          <div class="process-metrics">
            <div>
              <span>ADV3 / ADV20</span>
              <strong>{{ formatNumber(item.avg_dollar_volume_3d) }} / {{ formatNumber(item.avg_dollar_volume_20d) }}</strong>
            </div>
            <div>
              <span>VR3 / 放量天数</span>
              <strong>{{ formatNumber(item.volume_ratio_3d) }} / {{ formatNumber(item.volume_up_days_5d) }}</strong>
            </div>
            <div>
              <span>距60高点 / 加速度</span>
              <strong>{{ formatPercent(item.distance_to_60d_high) }} / {{ formatPercent(item.momentum_acceleration) }}</strong>
            </div>
          </div>

          <p class="process-decision">{{ item.watch_reason || '当前没有补充筛选理由。' }}</p>
        </article>
      </div>

      <p v-if="!visibleWatchlist.length && !loading" class="strategy-empty">当前没有可展示的股票策略观察池结果。</p>
    </section>
  </section>
</template>
