<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { RouterView, useRoute, useRouter } from 'vue-router'

import { useDashboardState } from './lib/dashboard-state'

const route = useRoute()
const router = useRouter()
const strategyOpen = ref(true)
const sidebarScrollArea = ref(null)
const sidebarScrollContent = ref(null)
const sidebarTrack = ref(null)
const sidebarThumbTop = ref(0)
const sidebarThumbHeight = ref(0)
const sidebarScrollable = ref(false)
const sidebarDragging = ref(false)

let sidebarResizeObserver
let dragPointerId = null
let dragStartY = 0
let dragStartTop = 0

const navItems = [
  { name: 'overview', to: '/', label: '全球市场', kicker: 'Global' },
  { name: 'markets-universe', to: '/market-universe', label: '地区市场股票池', kicker: 'Pool' },
  { name: 'stock-screen', to: '/stock-screen', label: '待选股票观察池', kicker: 'Watch' },
  { name: 'position-watch', to: '/position-watch', label: '持仓观察', kicker: 'Hold' },
  { name: 'scheduler-logs', to: '/scheduler-logs', label: '运行日志', kicker: 'Logs' },
]

const strategyItems = [
  { name: 'bull-strategy', to: '/strategy/bull', label: '牛市筛选策略', kicker: 'Bull' },
  { name: 'stock-strategy', to: '/strategy/stock', label: '股票筛选策略', kicker: 'Stock' },
  { name: 'theme-strategy', to: '/strategy/themes', label: '热门题材策略', kicker: 'Theme' },
  { name: 'trading-strategy', to: '/strategy/trading', label: '交易策略', kicker: 'Trade' },
]

const { state, ensureDashboardLoaded, loadDashboard } = useDashboardState()

const isStrategyRoute = computed(() => strategyItems.some((item) => item.name === route.name))
const marketCountLabel = computed(() => state.health?.market_count ?? '30+')

const currentViewMeta = computed(() => {
  if (route.name === 'bull-strategy') {
    return {
      title: '牛市筛选策略',
      description: '围绕新的牛市筛选策略，查看多入口并联的市场判定规则、评分和跟踪结果。',
    }
  }
  if (route.name === 'stock-strategy') {
    return {
      title: '股票筛选策略',
      description: '围绕新的股票筛选策略，查看观察池 watchlist、筛选范围和当前股票筛选结果。',
    }
  }
  if (route.name === 'theme-strategy') {
    return {
      title: '热门题材策略',
      description: '只展示全球市场热点题材和地区股市热点题材，直接查看当前题材方向。',
    }
  }
  if (route.name === 'scheduler-logs') {
    return {
      title: '运行日志',
      description: '查看 scheduler 和手动整套流程的最近执行记录，确认每日自动化任务有没有按预期跑完。',
    }
  }
  if (route.name === 'markets-universe') {
    return {
      title: '地区市场股票池',
      description: `覆盖全球30多个主要地区的股市，当前共接入 ${marketCountLabel.value} 个市场，可按市场查看本地股票池的全部股票代码。`,
    }
  }
  if (route.name === 'stock-screen') {
    return {
      title: '待选股票观察池',
      description: '只展示当前观察池 watchlist，按市场快速查看待选股票和对应观察理由。',
    }
  }
  if (route.name === 'trade-execution') {
    return {
      title: '交易执行',
      description: '单独查看当日可执行的 BUY 信号，只保留可买入股票和对应交易指标。',
    }
  }
  if (route.name === 'position-watch') {
    return {
      title: '持仓观察',
      description: '单独查看当前持仓、浮盈浮亏和最新风控观察指标。',
    }
  }
  if (route.name === 'trading-strategy') {
    return {
      title: '交易策略',
      description: '围绕观察池、信号、订单和持仓执行交易层策略。',
    }
  }
  if (route.name === 'operations') {
    return {
      title: '运行控制台',
      description: '单独放手动日更触发和运行结果，避免和研究信息混在同一屏。',
    }
  }
  if (route.name === 'data-sources') {
    return {
      title: '数据源',
      description: '查看当前数据源配置，并通过对话方式让智能体新增新的 source key。',
    }
  }
  return {
    title: '全球市场',
    description: '这里集中展示全球市场牛熊筛选结果，并支持直接执行一轮最新筛选。',
  }
})

const sidebarThumbStyle = computed(() => ({
  height: `${sidebarThumbHeight.value}px`,
  transform: `translateY(${sidebarThumbTop.value}px)`,
}))

function goPage(path) {
  if (route.path !== path) {
    void router.push(path)
  }
}

function toggleStrategy() {
  strategyOpen.value = !strategyOpen.value
}

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max)
}

function scheduleSidebarSync() {
  requestAnimationFrame(() => {
    updateSidebarThumb()
  })
}

function updateSidebarThumb() {
  const scrollArea = sidebarScrollArea.value
  const track = sidebarTrack.value
  if (!scrollArea || !track) {
    return
  }

  const visibleHeight = scrollArea.clientHeight
  const contentHeight = scrollArea.scrollHeight
  const trackHeight = track.clientHeight
  const maxScroll = Math.max(contentHeight - visibleHeight, 0)

  if (!visibleHeight || !trackHeight) {
    return
  }

  if (maxScroll <= 0) {
    sidebarScrollable.value = false
    sidebarThumbHeight.value = trackHeight
    sidebarThumbTop.value = 0
    return
  }

  const thumbHeight = Math.max((visibleHeight / contentHeight) * trackHeight, 56)
  const maxThumbTop = Math.max(trackHeight - thumbHeight, 0)

  sidebarScrollable.value = true
  sidebarThumbHeight.value = thumbHeight
  sidebarThumbTop.value = maxThumbTop === 0 ? 0 : (scrollArea.scrollTop / maxScroll) * maxThumbTop
}

function scrollSidebarFromThumb(nextTop) {
  const scrollArea = sidebarScrollArea.value
  const track = sidebarTrack.value
  if (!scrollArea || !track) {
    return
  }

  const maxScroll = Math.max(scrollArea.scrollHeight - scrollArea.clientHeight, 0)
  const maxThumbTop = Math.max(track.clientHeight - sidebarThumbHeight.value, 0)
  const clampedTop = clamp(nextTop, 0, maxThumbTop)

  sidebarThumbTop.value = clampedTop
  scrollArea.scrollTop = maxThumbTop === 0 ? 0 : (clampedTop / maxThumbTop) * maxScroll
}

function handleSidebarScroll() {
  if (!sidebarDragging.value) {
    updateSidebarThumb()
  }
}

function handleSidebarWheel(event) {
  const scrollArea = sidebarScrollArea.value
  event.preventDefault()
  event.stopPropagation()

  if (!scrollArea) {
    return
  }

  if (sidebarScrollable.value) {
    scrollArea.scrollTop += event.deltaY
  }
}

function jumpSidebarThumb(event) {
  if (!sidebarScrollable.value) {
    return
  }

  const track = sidebarTrack.value
  if (!track) {
    return
  }

  const rect = track.getBoundingClientRect()
  scrollSidebarFromThumb(event.clientY - rect.top - (sidebarThumbHeight.value / 2))
}

function stopSidebarDrag(event) {
  if (dragPointerId !== null && event?.pointerId !== undefined && event.pointerId !== dragPointerId) {
    return
  }

  sidebarDragging.value = false
  dragPointerId = null
  window.removeEventListener('pointermove', onSidebarDrag)
  window.removeEventListener('pointerup', stopSidebarDrag)
  window.removeEventListener('pointercancel', stopSidebarDrag)
}

function onSidebarDrag(event) {
  if (!sidebarDragging.value) {
    return
  }

  scrollSidebarFromThumb(dragStartTop + (event.clientY - dragStartY))
}

function startSidebarDrag(event) {
  if (!sidebarScrollable.value) {
    return
  }

  dragPointerId = event.pointerId
  dragStartY = event.clientY
  dragStartTop = sidebarThumbTop.value
  sidebarDragging.value = true

  window.addEventListener('pointermove', onSidebarDrag)
  window.addEventListener('pointerup', stopSidebarDrag)
  window.addEventListener('pointercancel', stopSidebarDrag)

  event.currentTarget.setPointerCapture?.(event.pointerId)
}

watch(
  () => [route.fullPath, strategyOpen.value],
  async () => {
    await nextTick()
    scheduleSidebarSync()
  },
)

onMounted(async () => {
  if (isStrategyRoute.value) {
    strategyOpen.value = true
  }

  await ensureDashboardLoaded()
  await nextTick()

  sidebarResizeObserver = new ResizeObserver(() => {
    scheduleSidebarSync()
  })

  if (sidebarScrollArea.value) {
    sidebarResizeObserver.observe(sidebarScrollArea.value)
  }
  if (sidebarScrollContent.value) {
    sidebarResizeObserver.observe(sidebarScrollContent.value)
  }

  window.addEventListener('resize', scheduleSidebarSync)
  scheduleSidebarSync()
})

onBeforeUnmount(() => {
  sidebarResizeObserver?.disconnect()
  window.removeEventListener('resize', scheduleSidebarSync)
  stopSidebarDrag()
})
</script>

<template>
  <div class="app-shell">
    <div class="ambient ambient-left"></div>
    <div class="ambient ambient-right"></div>

    <div class="app-frame">
      <aside class="sidebar panel">
        <div ref="sidebarScrollArea" class="sidebar-scroll-area" @scroll="handleSidebarScroll" @wheel.prevent.stop="handleSidebarWheel">
          <div ref="sidebarScrollContent" class="sidebar-scroll-content">
            <div class="sidebar-top">
              <p class="eyebrow">Navigator</p>
              <h2>控制面板</h2>
              <p class="sidebar-copy">左侧按钮现在切换的是实际页面路由，不是同页内容开关。</p>
            </div>

            <nav class="sidebar-nav">
              <button
                v-for="item in navItems"
                :key="item.name"
                type="button"
                class="nav-button"
                :class="{ active: route.name === item.name }"
                @click="goPage(item.to)"
              >
                <span class="nav-kicker">{{ item.kicker }}</span>
                <strong>{{ item.label }}</strong>
              </button>

              <div class="nav-group">
                <button
                  type="button"
                  class="nav-button nav-group-button"
                  :class="{ active: isStrategyRoute }"
                  @click="toggleStrategy"
                >
                  <span class="nav-kicker">Strategy</span>
                  <strong>策略</strong>
                  <small>{{ strategyOpen ? '收起' : '展开' }}</small>
                </button>

                <div v-if="strategyOpen" class="subnav">
                  <button
                    v-for="item in strategyItems"
                    :key="item.name"
                    type="button"
                    class="nav-button subnav-button"
                    :class="{ active: route.name === item.name }"
                    @click="goPage(item.to)"
                  >
                    <span class="nav-kicker">{{ item.kicker }}</span>
                    <strong>{{ item.label }}</strong>
                      </button>
                </div>
              </div>
            </nav>

            <div class="sidebar-footer">
              <button class="primary-button" type="button" :disabled="state.loading" @click="loadDashboard">
                {{ state.loading ? '刷新中...' : '刷新全部数据' }}
              </button>
            </div>
          </div>
        </div>

        <div
          ref="sidebarTrack"
          class="sidebar-scrollbar"
          :class="{ disabled: !sidebarScrollable }"
          @pointerdown="jumpSidebarThumb"
        >
          <button
            type="button"
            class="sidebar-scroll-thumb"
            :class="{ dragging: sidebarDragging }"
            :style="sidebarThumbStyle"
            :disabled="!sidebarScrollable"
            aria-label="拖动控制面板滚动"
            @pointerdown.stop="startSidebarDrag"
          ></button>
        </div>
      </aside>

      <main class="content-shell">
        <template v-if="route.name !== 'overview'">
          <div v-if="state.error" class="banner banner-error">
            {{ state.error }}
          </div>
          <div v-else-if="state.notice" class="banner banner-notice">
            {{ state.notice }}
          </div>

          <section class="view-intro panel">
            <p class="panel-kicker">Workspace</p>
            <h2>{{ currentViewMeta.title }}</h2>
            <p class="view-description">{{ currentViewMeta.description }}</p>
          </section>
        </template>

        <RouterView />
      </main>
    </div>
  </div>
</template>
