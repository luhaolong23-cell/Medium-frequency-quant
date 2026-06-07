<script setup>
import { computed } from 'vue'

const props = defineProps({
  health: {
    type: Object,
    default: null,
  },
  summary: {
    type: Object,
    default: null,
  },
  loading: {
    type: Boolean,
    default: false,
  },
  selectedMarket: {
    type: String,
    default: 'ALL',
  },
  marketOptions: {
    type: Array,
    default: () => [],
  },
  lastLoadedAt: {
    type: String,
    default: '',
  },
})

defineEmits(['refresh', 'update:selectedMarket'])

const stats = computed(() => [
  {
    label: '覆盖市场',
    value: props.health?.market_count ?? '--',
    note: '已注册全球市场',
  },
  {
    label: '跟踪牛市',
    value: props.summary?.tracked_bull_count ?? '--',
    note: '进入后续选股池',
  },
  {
    label: '开放持仓',
    value: props.summary?.open_position_count ?? '--',
    note: '当前纸面仓位',
  },
  {
    label: '今日观察池',
    value: props.summary?.latest_watchlist?.length ?? '--',
    note: '重点盯盘前 5',
  },
])

const services = computed(() => Object.entries(props.health?.services || {}))
const trackedMarkets = computed(() => props.summary?.tracked_bull_markets || [])
</script>

<template>
  <header class="hero-panel panel">
    <div class="hero-copy">
      <p class="eyebrow">GLOBAL REGIME / DAILY EXECUTION DESK</p>
      <h1>全球牛市捕手</h1>
      <p class="hero-text">
        把周度市场牛熊判断、日度候选排名、观察池信号与纸面持仓串成一张实时前台。
      </p>
    </div>

    <div class="hero-toolbar">
      <label class="toolbar-field">
        <span>观察市场</span>
        <select
          :value="selectedMarket"
          @change="$emit('update:selectedMarket', $event.target.value)"
        >
          <option v-for="market in marketOptions" :key="market" :value="market">
            {{ market === 'ALL' ? '全部市场' : market }}
          </option>
        </select>
      </label>

      <button class="ghost-button" type="button" :disabled="loading" @click="$emit('refresh')">
        {{ loading ? '刷新中...' : '刷新总览' }}
      </button>
    </div>

    <div class="stats-grid">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <p class="stat-label">{{ item.label }}</p>
        <p class="stat-value">{{ item.value }}</p>
        <p class="stat-note">{{ item.note }}</p>
      </article>
    </div>

    <div class="meta-row">
      <div class="service-strip">
        <span v-for="[name, status] in services" :key="name" class="service-chip">
          <strong>{{ name }}</strong>
          <small>{{ status }}</small>
        </span>
      </div>
      <p class="last-loaded">最近刷新 {{ lastLoadedAt || '--' }}</p>
    </div>

    <div v-if="trackedMarkets.length" class="tracked-ticker">
      <span class="ticker-label">正在跟踪的牛市</span>
      <div class="ticker-track">
        <span v-for="item in trackedMarkets" :key="item.market_code" class="ticker-item">
          {{ item.market_code }} / 分数 {{ item.bull_score.toFixed(1) }}
        </span>
      </div>
    </div>
  </header>
</template>
