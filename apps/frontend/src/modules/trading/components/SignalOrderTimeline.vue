<script setup>
import { formatDateTime, formatMoney, formatNumber } from '../../../lib/format'

defineProps({
  signals: {
    type: Array,
    default: () => [],
  },
  orders: {
    type: Array,
    default: () => [],
  },
  loading: {
    type: Boolean,
    default: false,
  },
})
</script>

<template>
  <section class="panel side-panel">
    <div class="panel-heading">
      <div>
        <p class="panel-kicker">Trading</p>
        <h2>信号与订单</h2>
      </div>
      <span class="panel-meta">{{ loading ? '更新中' : '今日执行链路' }}</span>
    </div>

    <div class="timeline-grid">
      <div class="timeline-column">
        <h3>信号</h3>
        <article
          v-for="signal in signals.slice(0, 6)"
          :key="`${signal.market_code}-${signal.ticker}-${signal.side}-${signal.trade_date}`"
          class="timeline-card"
        >
          <div class="timeline-top">
            <strong>{{ signal.ticker }}</strong>
            <span>{{ signal.side }}</span>
          </div>
          <p>{{ signal.signal_type }} / {{ signal.market_code }}</p>
          <small>{{ signal.signal_reason }}</small>
          <div class="timeline-meta">
            <span>量能 {{ formatNumber(signal.volume_ratio_5d) }}</span>
            <span>名义 {{ formatMoney(signal.order_notional) }}</span>
          </div>
        </article>
      </div>

      <div class="timeline-column">
        <h3>订单</h3>
        <article
          v-for="order in orders.slice(0, 6)"
          :key="order.order_id"
          class="timeline-card"
        >
          <div class="timeline-top">
            <strong>{{ order.ticker }}</strong>
            <span>{{ order.status }}</span>
          </div>
          <p>{{ order.side }} / {{ order.signal_type }}</p>
          <small>{{ formatDateTime(order.filled_at) }}</small>
          <div class="timeline-meta">
            <span>成交 {{ formatNumber(order.filled_price) }}</span>
            <span>数量 {{ formatNumber(order.quantity) }}</span>
          </div>
        </article>
      </div>
    </div>
  </section>
</template>
