import { createRouter, createWebHistory } from 'vue-router'

import DataSourcesPage from './pages/DataSourcesPage.vue'
import HotIndustriesPage from './pages/HotIndustriesPage.vue'
import MarketUniversePage from './pages/MarketUniversePage.vue'
import MarketsPage from './pages/MarketsPage.vue'
import OperationsPage from './pages/OperationsPage.vue'
import OverviewPage from './pages/OverviewPage.vue'
import SchedulerLogsPage from './pages/SchedulerLogsPage.vue'
import PositionWatchPage from './pages/PositionWatchPage.vue'
import SelectionPage from './pages/SelectionPage.vue'
import StockStrategyPage from './pages/StockStrategyPage.vue'
import TradeExecutionPage from './pages/TradeExecutionPage.vue'
import TradingPage from './pages/TradingPage.vue'

const routes = [
  { path: '/', name: 'overview', component: OverviewPage },
  { path: '/market-universe', name: 'markets-universe', component: MarketUniversePage },
  { path: '/stock-screen', name: 'stock-screen', component: SelectionPage },
  { path: '/trade-execution', name: 'trade-execution', component: TradeExecutionPage },
  { path: '/position-watch', name: 'position-watch', component: PositionWatchPage },
  { path: '/scheduler-logs', name: 'scheduler-logs', component: SchedulerLogsPage },
  { path: '/strategy/bull', name: 'bull-strategy', component: MarketsPage },
  { path: '/strategy/stock', name: 'stock-strategy', component: StockStrategyPage },
  { path: '/strategy/themes', name: 'theme-strategy', component: HotIndustriesPage },
  { path: '/strategy/quality', redirect: '/strategy/stock' },
  { path: '/strategy/trading', name: 'trading-strategy', component: TradingPage },
  { path: '/operations', name: 'operations', component: OperationsPage },
  { path: '/data-sources', name: 'data-sources', component: DataSourcesPage },
  { path: '/hot-industries', redirect: '/strategy/themes' },
  { path: '/markets', redirect: '/strategy/bull' },
  { path: '/selection', redirect: '/stock-screen' },
  { path: '/trading', redirect: '/strategy/trading' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
