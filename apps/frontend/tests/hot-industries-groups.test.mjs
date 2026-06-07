import assert from 'node:assert/strict'

import { buildGlobalThemes, buildLocalThemeGroups, getVisibleThemes } from '../src/modules/selection/components/hot-industries-groups.js'

const themes = [
  { market_code: 'US_EQ', theme_type: 'global_theme', theme_name: '半导体', smoothed_heat_score: 99.9, constituent_count: 1 },
  { market_code: 'US_EQ', theme_type: 'official_local_industry', theme_name: 'Information Technology Select Sector', smoothed_heat_score: 68.3, constituent_count: 1 },
  { market_code: 'CN_EQ', theme_type: 'global_theme', theme_name: '半导体', smoothed_heat_score: 99.9, constituent_count: 1 },
  { market_code: 'CN_EQ', theme_type: 'official_local_industry', theme_name: '中证全指半导体产品与设备指数', smoothed_heat_score: 55.5, constituent_count: 1 },
  { market_code: 'JP_EQ', theme_type: 'official_local_industry', theme_name: 'TOPIX-17 IT & SERVICES, OTHERS', smoothed_heat_score: 60.1, constituent_count: 1 },
]

const visibleThemes = getVisibleThemes(themes, 'ALL')
const globalThemes = buildGlobalThemes(visibleThemes)
const localThemeGroups = buildLocalThemeGroups(visibleThemes)

assert.deepEqual(globalThemes.map((item) => item.theme_name), ['半导体'])
assert.equal(globalThemes[0].constituent_count, 2)
assert.deepEqual(localThemeGroups, [
  {
    marketCode: 'CN_EQ',
    themes: ['中证全指半导体产品与设备指数', '半导体'],
  },
  {
    marketCode: 'JP_EQ',
    themes: ['IT & SERVICES, OTHERS'],
  },
  {
    marketCode: 'US_EQ',
    themes: ['Information Technology Select Sector', '半导体'],
  },
])

const usVisibleThemes = getVisibleThemes(themes, 'US_EQ')
assert.deepEqual(buildGlobalThemes(usVisibleThemes).map((item) => item.theme_name), ['半导体'])
assert.deepEqual(buildLocalThemeGroups(usVisibleThemes), [
  {
    marketCode: 'US_EQ',
    themes: ['Information Technology Select Sector', '半导体'],
  },
])

console.log('hot-industries-groups tests passed')
