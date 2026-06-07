<script setup>
import { computed } from 'vue'

import { formatDateTime, formatNumber } from '../../../lib/format'
import { buildGlobalThemes, buildLocalThemeGroups, getVisibleThemes } from './hot-industries-groups'

const props = defineProps({
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
    key: 'global-theme',
    title: '全球题材聚合策略',
    summary: '先识别跨市场重复出现的 global_theme，形成全球共振题材。',
    details: [
      '同名 global_theme 会按热度聚合，优先保留更强的全球主线。',
      '适合识别 AI、半导体、能源、军工这类跨市场同步升温的主题。',
    ],
    metrics: '看 global_theme、smoothed_heat_score、constituent_count',
  },
  {
    key: 'local-theme',
    title: '地区题材识别策略',
    summary: '每个市场单独识别本地最强题材，不用一套题材覆盖所有地区。',
    details: [
      '同一市场会单独保留自己的强题材，不和其他市场强行统一。',
      '适合识别日本、韩国、印度、欧洲等本地市场的差异化主线。',
    ],
    metrics: '看 market_code、theme_name、theme_type、smoothed_heat_score',
  },
  {
    key: 'heat-score',
    title: '热度平滑策略',
    summary: '题材排序优先看平滑后的热度，不只看单日脉冲。',
    details: [
      '避免因为单日异动把短脉冲题材误当成持续主线。',
      '让当前热门题材更偏向持续升温，而不是一次性跳涨。',
    ],
    metrics: '看 raw_heat_score、smoothed_heat_score',
  },
  {
    key: 'breadth',
    title: '成分股广度策略',
    summary: '用成分股数量辅助判断题材是不是具备扩散能力。',
    details: [
      '热度高但成分很少的题材，更可能是局部热点而不是可扩散主线。',
      '热度和成分股广度一起看，更适合判断题材持续性。',
    ],
    metrics: '看 constituent_count、smoothed_heat_score',
  },
]

const visibleThemes = computed(() => getVisibleThemes(props.themes, props.selectedMarket))
const latestTradeDate = computed(() => visibleThemes.value[0]?.trade_date || null)
const globalThemes = computed(() => buildGlobalThemes(visibleThemes.value))
const localThemeGroups = computed(() => buildLocalThemeGroups(visibleThemes.value))
const topGlobalThemes = computed(() => globalThemes.value.slice(0, 8))
</script>

<template>
  <section class="view-stack bull-strategy-stack">
    <section class="panel strategy-list-panel">
      <div class="panel-heading">
        <div>
          <p class="panel-kicker">Theme Strategy</p>
          <h2>热门题材筛选策略</h2>
        </div>
        <span class="panel-meta">{{ latestTradeDate ? formatDateTime(latestTradeDate) : (loading ? '加载中' : '暂无数据') }}</span>
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

    <section class="panel strategy-current-panel">
      <div class="panel-heading">
        <div>
          <p class="panel-kicker">Global Themes</p>
          <h2>全球热门题材</h2>
        </div>
        <span class="panel-meta">{{ loading ? '更新中' : `${globalThemes.length} 个题材` }}</span>
      </div>

      <div class="process-grid">
        <article v-for="theme in topGlobalThemes" :key="`global-${theme.theme_name}`" class="process-card tone-bull">
          <div class="process-header">
            <div>
              <p class="process-code">{{ theme.theme_name }}</p>
              <p class="process-sub">全球共振题材</p>
            </div>
            <div class="market-overview-score">
              <span class="badge">GLOBAL</span>
              <strong>{{ formatNumber(theme.smoothed_heat_score) }}</strong>
            </div>
          </div>

          <div class="process-metrics">
            <div>
              <span>平滑热度</span>
              <strong>{{ formatNumber(theme.smoothed_heat_score) }}</strong>
            </div>
            <div>
              <span>成分股广度</span>
              <strong>{{ formatNumber(theme.constituent_count, 0) }}</strong>
            </div>
            <div>
              <span>当前定位</span>
              <strong>全球主线</strong>
            </div>
          </div>
        </article>
      </div>

      <p v-if="!topGlobalThemes.length && !loading" class="strategy-empty">当前没有可展示的全球热门题材。</p>
    </section>

    <section class="panel strategy-result-panel">
      <div class="panel-heading">
        <div>
          <p class="panel-kicker">Local Themes</p>
          <h2>各地区热门题材</h2>
        </div>
        <span class="panel-meta">{{ loading ? '更新中' : `${localThemeGroups.length} 个市场` }}</span>
      </div>

      <div class="theme-stack" v-if="localThemeGroups.length">
        <p v-for="group in localThemeGroups" :key="group.marketCode" class="strategy-description">
          <strong>{{ group.marketCode }}</strong>：{{ group.themes.join('、') }}
        </p>
      </div>

      <p v-else-if="!loading" class="strategy-empty">当前没有可展示的各地区热门题材。</p>
    </section>
  </section>
</template>
