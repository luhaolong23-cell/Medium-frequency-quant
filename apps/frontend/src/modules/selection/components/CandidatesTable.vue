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
  selectedMarket: {
    type: String,
    default: 'ALL',
  },
  runningStockScreen: {
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

const emit = defineEmits(['refresh', 'run-stock-screen'])

const rows = computed(() => [...props.watchlist].sort((left, right) => left.watch_rank - right.watch_rank))

const panelMeta = computed(() => {
  if (props.loading) {
    return '更新中'
  }

  return `共 ${rows.value.length} 只待选观察股`
})

const marketLabel = computed(() => (props.selectedMarket === 'ALL' ? '全部市场' : props.selectedMarket))

const formatTags = (tags) => (Array.isArray(tags) && tags.length ? tags.join(' / ') : '--')
const formatValue = (value) => (value == null ? '--' : formatNumber(value))
</script>

<template>
  <section class="panel">
    <div class="panel-heading">
      <div>
        <p class="panel-kicker">Watchlist</p>
        <h2>待选股票观察池</h2>
      </div>
      <div class="overview-heading-actions">
        <span class="panel-meta">{{ panelMeta }}</span>
        <button class="ghost-button overview-refresh-button" type="button" :disabled="loading || runningStockScreen" @click="emit('refresh')">
          {{ loading ? '刷新中...' : '刷新' }}
        </button>
        <button class="primary-button overview-run-button" type="button" :disabled="loading || runningStockScreen" @click="emit('run-stock-screen')">
          {{ runningStockScreen ? '更新中...' : '更新观察池' }}
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
        <p>筛选范围</p>
        <strong>{{ marketLabel }}</strong>
        <span>仅展示当前 watchlist 里的待选观察股票</span>
      </article>
      <article class="stat-card">
        <p>数据状态</p>
        <strong>{{ loading ? '更新中' : '已完成' }}</strong>
        <span>直接展示观察池股票的理由、指标和综合评分</span>
      </article>
    </div>

    <div class="table-wrap">
      <table class="data-table">
        <thead>
          <tr>
            <th>观察顺位</th>
            <th>股票</th>
            <th>市场</th>
            <th>综合分</th>
            <th>趋势 / 收益</th>
            <th>量能 / 位置</th>
            <th>分项得分</th>
            <th>题材标签</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in rows" :key="`${item.market_code}-${item.ticker}-${item.trade_date}`">
            <td class="rank-cell">#{{ item.watch_rank }}</td>
            <td>
              <strong>{{ item.ticker }}</strong>
              <small>{{ item.company_name || '--' }}</small>
            </td>
            <td>{{ item.market_code }}</td>
            <td><div class="factor-stack"><span>综合 {{ formatValue(item.composite_score) }}</span><span>{{ item.watch_reason || '--' }}</span></div></td>
            <td>
              <div class="factor-stack">
                <span>Close {{ formatValue(item.close) }}</span>
                <span>5D {{ formatPercent(item.ret_5d) }}</span>
                <span>20D {{ formatPercent(item.ret_20d) }}</span>
                <span>MA20 / MA60 {{ formatValue(item.ma_20) }} / {{ formatValue(item.ma_60) }}</span>
              </div>
            </td>
            <td>
              <div class="factor-stack">
                <span>VR3 {{ formatValue(item.volume_ratio_3d) }}</span>
                <span>ADV3 {{ formatValue(item.avg_dollar_volume_3d) }}</span>
                <span>ADV20 {{ formatValue(item.avg_dollar_volume_20d) }}</span>
                <span>放量天数 {{ formatValue(item.volume_up_days_5d) }}</span>
                <span>距60高点 {{ formatPercent(item.distance_to_60d_high) }}</span>
                <span>加速度 {{ formatPercent(item.momentum_acceleration) }}</span>
              </div>
            </td>
            <td>
              <div class="factor-stack">
                <span>题材 {{ formatValue(item.theme_score) }}</span>
                <span>补涨 {{ formatValue(item.lagging_score) }}</span>
                <span>趋势 {{ formatValue(item.trend_recovery_score) }}</span>
                <span>动量 {{ formatValue(item.momentum_acceleration_score) }}</span>
                <span>试探量 {{ formatValue(item.volume_probe_score) }}</span>
                <span>风险 {{ formatValue(item.risk_control_score) }}</span>
              </div>
            </td>
            <td>{{ formatTags(item.theme_tags) }}</td>
          </tr>
          <tr v-if="!rows.length">
            <td colspan="8" class="empty-cell">{{ loading ? '正在加载观察池...' : '当前没有观察池结果。' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
