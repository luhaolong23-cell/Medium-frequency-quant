<script setup>
import { ref, watch } from 'vue'

const props = defineProps({
  running: {
    type: Boolean,
    default: false,
  },
  result: {
    type: Object,
    default: null,
  },
  selectedMarket: {
    type: String,
    default: 'ALL',
  },
  marketOptions: {
    type: Array,
    default: () => [],
  },
})

const emit = defineEmits(['submit'])

const tradeDate = ref('')
const marketCode = ref(props.selectedMarket || 'ALL')

watch(
  () => props.selectedMarket,
  (value) => {
    marketCode.value = value || 'ALL'
  },
)

function submitForm() {
  emit('submit', {
    trade_date: tradeDate.value || null,
    market_codes: marketCode.value === 'ALL' ? ['ALL'] : [marketCode.value],
  })
}
</script>

<template>
  <section class="panel side-panel">
    <div class="panel-heading">
      <div>
        <p class="panel-kicker">Execution</p>
        <h2>手动触发日更</h2>
      </div>
      <span class="badge badge-warm">POST /admin/run-daily</span>
    </div>

    <div class="form-stack">
      <label class="toolbar-field">
        <span>交易日期</span>
        <input v-model="tradeDate" type="date" />
      </label>

      <label class="toolbar-field">
        <span>市场范围</span>
        <select v-model="marketCode">
          <option v-for="market in marketOptions" :key="market" :value="market">
            {{ market === 'ALL' ? '全部市场' : market }}
          </option>
        </select>
      </label>

      <button class="primary-button" type="button" :disabled="running" @click="submitForm">
        {{ running ? '执行中...' : '运行每日流程' }}
      </button>
    </div>

    <div v-if="result" class="run-summary">
      <div class="mini-metric">
        <span>候选</span>
        <strong>{{ result.selected_candidates }}</strong>
      </div>
      <div class="mini-metric">
        <span>观察池</span>
        <strong>{{ result.watchlist_count }}</strong>
      </div>
      <div class="mini-metric">
        <span>信号</span>
        <strong>{{ result.generated_signals }}</strong>
      </div>
      <div class="mini-metric">
        <span>订单</span>
        <strong>{{ result.executed_orders }}</strong>
      </div>
    </div>
  </section>
</template>
