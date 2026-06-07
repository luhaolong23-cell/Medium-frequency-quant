<script setup>
import { computed } from 'vue'

import { formatNumber, formatPercent } from '../../../lib/format'

const props = defineProps({
  item: {
    type: Object,
    required: true,
  },
  showDetailNote: {
    type: Boolean,
    default: true,
  },
})

function criterionByName(name) {
  return (props.item.criteria || []).find((criterion) => criterion.name === name) || null
}

function scoreText(criterion) {
  if (!criterion) {
    return '--'
  }
  return `${formatNumber(criterion.score)} / ${formatNumber(criterion.max_score)}`
}

function toneClass(criterion) {
  if (!criterion) {
    return 'tone-neutral'
  }
  return criterion.passed ? 'tone-bull' : 'tone-bear'
}

function metric(label, value) {
  return { label, value: value ?? '--' }
}

const entries = computed(() => {
  const policyBreakout = criterionByName('policy_breakout')
  const trendPersistence = criterionByName('trend_persistence')
  const recoveryReversal = criterionByName('recovery_reversal')
  const globalLeader = criterionByName('global_leader')

  return [
    {
      key: 'policy_breakout',
      label: policyBreakout?.label || '政策点火型',
      score: scoreText(policyBreakout),
      tone: toneClass(policyBreakout),
      note: policyBreakout?.detail || '',
      metrics: [
        metric('20日成交额比', `${formatNumber(props.item.turnover_ratio_20d)}x`),
        metric('单日涨幅', formatPercent(props.item.ret_1d)),
        metric('3日均额比', `${formatNumber(props.item.avg_turnover_ratio_3d)}x`),
        metric('MA5 / MA10 / MA20', `${formatNumber(props.item.ma_5)} / ${formatNumber(props.item.ma_10)} / ${formatNumber(props.item.ma_20)}`),
      ],
    },
    {
      key: 'trend_persistence',
      label: trendPersistence?.label || '趋势慢牛型',
      score: scoreText(trendPersistence),
      tone: toneClass(trendPersistence),
      note: trendPersistence?.detail || '',
      metrics: [
        metric('60日涨幅', formatPercent(props.item.ret_60d)),
        metric('120日涨幅', formatPercent(props.item.ret_120d)),
        metric('Close / MA60 / MA120', `${formatNumber(props.item.close)} / ${formatNumber(props.item.ma_60)} / ${formatNumber(props.item.ma_120)}`),
        metric('相对全球强弱', formatPercent(props.item.relative_strength_world)),
      ],
    },
    {
      key: 'recovery_reversal',
      label: recoveryReversal?.label || '超跌反转型',
      score: scoreText(recoveryReversal),
      tone: toneClass(recoveryReversal),
      note: recoveryReversal?.detail || '',
      metrics: [
        metric('5日涨幅', formatPercent(props.item.ret_5d)),
        metric('连续上涨周数', `${formatNumber(props.item.consecutive_up_weeks, 0)} 周`),
        metric('Close / MA20 / MA60', `${formatNumber(props.item.close)} / ${formatNumber(props.item.ma_20)} / ${formatNumber(props.item.ma_60)}`),
        metric('量能修复', `${formatNumber(props.item.turnover_ratio_20d)}x / ${formatNumber(props.item.avg_turnover_ratio_3d)}x`),
      ],
    },
    {
      key: 'global_leader',
      label: globalLeader?.label || '全球强势型',
      score: scoreText(globalLeader),
      tone: toneClass(globalLeader),
      note: globalLeader?.detail || '',
      metrics: [
        metric('相对全球强弱', formatPercent(props.item.relative_strength_world)),
        metric('120日涨幅', formatPercent(props.item.ret_120d)),
        metric('Close / MA200', `${formatNumber(props.item.close)} / ${formatNumber(props.item.ma_200)}`),
        metric('MA60 / MA120', `${formatNumber(props.item.ma_60)} / ${formatNumber(props.item.ma_120)}`),
        metric('60日回撤', formatPercent(props.item.drawdown_60d)),
      ],
    },
  ]
})
</script>

<template>
  <div class="bull-factor-list">
    <article v-for="entry in entries" :key="entry.key" class="bull-factor-card">
      <div class="bull-factor-head">
        <span class="badge" :class="entry.tone">{{ entry.label }}</span>
        <strong>{{ entry.score }}</strong>
      </div>
      <div class="bull-factor-metrics">
        <div v-for="metric in entry.metrics" :key="`${entry.key}-${metric.label}`" class="bull-factor-metric">
          <span>{{ metric.label }}</span>
          <strong>{{ metric.value }}</strong>
        </div>
      </div>
      <small v-if="showDetailNote && entry.note" class="bull-factor-note">{{ entry.note }}</small>
    </article>
  </div>
</template>
