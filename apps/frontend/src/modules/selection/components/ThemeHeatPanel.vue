<script setup>
import { computed } from 'vue'

import { formatNumber } from '../../../lib/format'

const props = defineProps({
  themes: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
  title: {
    type: String,
    default: '题材热度',
  },
  subtitle: {
    type: String,
    default: 'Top 8',
  },
})

const topThemes = computed(() =>
  [...props.themes].sort((left, right) => right.smoothed_heat_score - left.smoothed_heat_score).slice(0, 8),
)
</script>

<template>
  <section class="panel">
    <div class="panel-heading">
      <div>
        <p class="panel-kicker">Selection</p>
        <h2>{{ title }}</h2>
      </div>
      <span class="panel-meta">{{ loading ? '更新中' : subtitle }}</span>
    </div>

    <div class="theme-stack">
      <article
        v-for="theme in topThemes"
        :key="`${theme.market_code}-${theme.theme_type}-${theme.theme_name}`"
        class="theme-row"
      >
        <div class="theme-copy">
          <p>{{ theme.theme_name }}</p>
          <small>{{ theme.market_code }} / {{ theme.theme_type }}</small>
        </div>
        <div class="theme-meter">
          <span :style="{ width: `${Math.min(theme.smoothed_heat_score * 10, 100)}%` }"></span>
        </div>
        <div class="theme-score">
          <strong>{{ formatNumber(theme.smoothed_heat_score) }}</strong>
          <small>{{ theme.constituent_count }} 只成分</small>
        </div>
      </article>
    </div>
  </section>
</template>
