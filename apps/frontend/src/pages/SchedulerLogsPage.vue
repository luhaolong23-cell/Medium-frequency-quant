<script setup>
import { computed } from 'vue'

import { useDashboardState } from '../lib/dashboard-state'

const { state } = useDashboardState()

const logs = computed(() => state.schedulerLogs || [])
const latestManualRun = computed(() => logs.value.find((entry) => entry.job_name === 'run_daily_workflow'))

function statusLabel(status) {
  if (status === 'running') return '运行中'
  if (status === 'completed') return '成功'
  return '失败'
}

const jobLabels = {
  run_daily_workflow: '整套流程手动执行',
  sync_refdata: '同步市场基础数据',
  ingest_market_bars: '更新地区股市行情',
  run_regime: '牛市判断',
  sync_stock_universe_inventory: '更新地区股票池',
  prepare_hot_themes: '更新热门题材',
  run_daily_selection: '更新观察池股票',
  run_position_monitor: '更新持仓监控',
}

function formatDateTime(value) {
  if (!value) {
    return '--'
  }
  return new Date(value).toLocaleString('zh-CN', { hour12: false })
}

function formatDuration(value) {
  if (value === null || value === undefined) {
    return '--'
  }
  return `${Number(value).toFixed(2)}s`
}

function formatMarkets(codes) {
  if (!codes?.length) {
    return '全部市场'
  }
  if (codes.length === 1 && codes[0] === 'ALL') {
    return '全部市场'
  }
  return codes.join(' / ')
}

function summarizeResult(result = {}) {
  if (result.current_step) {
    const stepLabels = {
      sync_refdata: '同步市场基础数据',
      ingest_market_bars: '更新地区股市行情',
      run_regime: '牛市判断',
      sync_stock_universe_inventory: '更新地区股票池',
      prepare_hot_themes: '更新热门题材',
      run_daily_selection: '更新观察池股票',
      run_paper_trading: '运行买入/持仓策略',
    }
    const label = stepLabels[result.current_step] || result.current_step
    return `当前步骤：${label}`
  }
  const pairs = [
    ['synced_markets', '同步市场'],
    ['computed_features', '行情'],
    ['computed_regimes', '牛市'],
    ['selected_candidates', '候选'],
    ['watchlist_count', '观察池'],
    ['generated_signals', '信号'],
    ['executed_orders', '订单'],
    ['open_positions', '持仓'],
    ['heat_snapshot_count', '题材快照'],
    ['universe_count', '股票池'],
  ]
  const fragments = pairs
    .filter(([key]) => result[key] !== undefined && result[key] !== null)
    .map(([key, label]) => `${label} ${result[key]}`)
  return fragments.length ? fragments.join(' / ') : '本次任务没有返回额外统计。'
}
</script>

<template>
  <section class="view-stack">
    <section class="panel strategy-result-panel">
      <div class="panel-heading">
        <div>
          <p class="panel-kicker">Scheduler Logs</p>
          <h3>最近任务执行日志</h3>
        </div>
        <span class="panel-meta">{{ state.loading ? '更新中' : `最近 ${logs.length} 条` }}</span>
      </div>

      <div class="stats-grid compact-grid">
        <article class="stat-card">
          <span>最近手动整套流程</span>
          <strong>{{ latestManualRun ? formatDateTime(latestManualRun.completed_at) : '--' }}</strong>
          <small>{{ latestManualRun?.trade_date || '暂无手动执行记录' }}</small>
        </article>
        <article class="stat-card">
          <span>最新牛市快照</span>
          <strong>{{ state.summary?.regime_latest_trade_date || '--' }}</strong>
          <small>{{ state.summary ? `${state.summary.tracked_bull_count} 个牛市市场` : '暂无数据' }}</small>
        </article>
        <article class="stat-card">
          <span>最新观察池快照</span>
          <strong>{{ state.summary?.latest_watchlist_trade_date || '--' }}</strong>
          <small>{{ state.summary ? `${state.summary.latest_watchlist.length} 只观察池股票` : '暂无数据' }}</small>
        </article>
      </div>

      <div v-if="!logs.length" class="empty-state">
        <strong>暂无任务执行日志</strong>
        <span>手动执行整套流程或等待 scheduler 下一次触发后，这里会出现最新记录。</span>
      </div>

      <div v-else class="process-grid">
        <article
          v-for="entry in logs"
          :key="`${entry.job_name}-${entry.started_at}`"
          class="process-card"
        >
          <div class="process-card-header">
            <div>
              <p class="process-card-kicker">{{ entry.trigger_mode === 'manual' ? '手动触发' : entry.trigger_mode === 'startup' ? '启动初始化' : '调度触发' }}</p>
              <h4>{{ jobLabels[entry.job_name] || entry.job_name }}</h4>
            </div>
            <span class="pill" :class="entry.status === 'completed' ? 'pill-positive' : entry.status === 'running' ? 'pill-warning' : 'pill-negative'">{{ statusLabel(entry.status) }}</span>
          </div>

          <dl class="criteria-list">
            <div class="criteria-row">
              <dt>交易日</dt>
              <dd>{{ entry.trade_date || '--' }}</dd>
            </div>
            <div class="criteria-row">
              <dt>市场范围</dt>
              <dd>{{ formatMarkets(entry.market_codes) }}</dd>
            </div>
            <div class="criteria-row">
              <dt>开始时间</dt>
              <dd>{{ formatDateTime(entry.started_at) }}</dd>
            </div>
            <div class="criteria-row">
              <dt>完成时间</dt>
              <dd>{{ formatDateTime(entry.completed_at) }}</dd>
            </div>
            <div class="criteria-row">
              <dt>耗时</dt>
              <dd>{{ formatDuration(entry.duration_seconds) }}</dd>
            </div>
          </dl>

          <p v-if="entry.error" class="empty-state-copy">{{ entry.error }}</p>
          <p v-else class="empty-state-copy">{{ summarizeResult(entry.result) }}</p>
        </article>
      </div>
    </section>
  </section>
</template>
