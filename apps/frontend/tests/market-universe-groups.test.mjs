import assert from 'node:assert/strict'

import { buildMarketUniverseRows } from '../src/modules/markets/components/market-universe-groups.js'

const rows = [
  {
    market_code: 'US_EQ',
    ticker: 'NVDA',
    company_name: 'NVIDIA',
    industry: 'Semiconductors',
    price: 120.5,
    momentum_pct: 8.2,
    volume_ratio: 1.4,
  },
  {
    market_code: 'US_EQ',
    ticker: 'AAPL',
    company_name: 'Apple',
    industry: 'Consumer Electronics',
    price: 199.2,
    momentum_pct: 3.1,
    volume_ratio: 0.9,
  },
  {
    market_code: 'US_EQ',
    ticker: 'NVDA',
    company_name: 'NVIDIA duplicate',
    industry: 'Semiconductors',
    price: 999,
    momentum_pct: 99,
    volume_ratio: 99,
  },
  {
    market_code: 'JP_EQ',
    ticker: '8035.T',
    company_name: 'Tokyo Electron',
    industry: 'Semiconductor Equipment',
    price: 32100,
    momentum_pct: 6.5,
    volume_ratio: 1.1,
  },
]

assert.deepEqual(buildMarketUniverseRows(rows, 'US_EQ'), [
  {
    market_code: 'US_EQ',
    ticker: 'AAPL',
    company_name: 'Apple',
    industry: 'Consumer Electronics',
    price: 199.2,
    momentum_pct: 3.1,
    volume_ratio: 0.9,
  },
  {
    market_code: 'US_EQ',
    ticker: 'NVDA',
    company_name: 'NVIDIA',
    industry: 'Semiconductors',
    price: 120.5,
    momentum_pct: 8.2,
    volume_ratio: 1.4,
  },
])

assert.deepEqual(buildMarketUniverseRows(rows, 'JP_EQ'), [
  {
    market_code: 'JP_EQ',
    ticker: '8035.T',
    company_name: 'Tokyo Electron',
    industry: 'Semiconductor Equipment',
    price: 32100,
    momentum_pct: 6.5,
    volume_ratio: 1.1,
  },
])

console.log('market-universe-groups tests passed')
