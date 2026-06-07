<script setup>
import { formatInteger, formatMoney, formatNumber, formatPercent, toneForPnL } from '../../../lib/format'

defineProps({
  positions: {
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
        <p class="panel-kicker">Positions</p>
        <h2>开放持仓</h2>
      </div>
      <span class="panel-meta">{{ loading ? '更新中' : '仅展示 OPEN' }}</span>
    </div>

    <div class="table-wrap">
      <table class="data-table compact-table">
        <thead>
          <tr>
            <th>标的</th>
            <th>仓位</th>
            <th>浮盈亏</th>
            <th>回撤监控</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in positions" :key="`${item.market_code}-${item.ticker}`">
            <td>
              <strong>{{ item.ticker }}</strong>
              <small>{{ item.market_code }}</small>
            </td>
            <td>{{ formatMoney(item.invested_notional) }}</td>
            <td :class="toneForPnL(item.unrealized_pnl)">
              <strong>{{ formatMoney(item.unrealized_pnl) }}</strong>
              <small>{{ formatPercent(item.unrealized_return) }}</small>
            </td>
            <td>
              <strong>{{ formatInteger(item.consecutive_decline_days) }} 天</strong>
              <small>峰值 {{ formatNumber(item.peak_price) }}</small>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
