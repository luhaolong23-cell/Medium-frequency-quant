export function getVisibleThemes(themes, selectedMarket = 'ALL') {
  const items = Array.isArray(themes) ? themes : []
  return items.filter((item) => selectedMarket === 'ALL' || item.market_code === selectedMarket)
}

export function buildGlobalThemes(themes) {
  const grouped = new Map()

  themes
    .filter((item) => item.theme_type === 'global_theme')
    .forEach((item) => {
      const key = String(item.theme_name || '').trim().toLowerCase()
      if (!key) {
        return
      }

      const current = grouped.get(key)
      const nextScore = Number(item.smoothed_heat_score ?? 0)
      const nextConstituentCount = Number(item.constituent_count ?? 0)

      if (!current) {
        grouped.set(key, {
          theme_name: item.theme_name,
          smoothed_heat_score: nextScore,
          constituent_count: nextConstituentCount,
        })
        return
      }

      current.smoothed_heat_score = Math.max(current.smoothed_heat_score, nextScore)
      current.constituent_count += nextConstituentCount
    })

  return Array.from(grouped.values()).sort((left, right) => right.smoothed_heat_score - left.smoothed_heat_score)
}

function formatLocalThemeName(themeName) {
  return String(themeName || '').trim().replace(/^TOPIX-17\s+/, '')
}

export function buildLocalThemeGroups(themes) {
  const grouped = new Map()

  themes
    .slice()
    .sort((left, right) => {
      const marketDiff = String(left.market_code || '').localeCompare(String(right.market_code || ''))
      if (marketDiff !== 0) {
        return marketDiff
      }
      const leftIsGlobal = String(left.theme_type || '').trim() === 'global_theme'
      const rightIsGlobal = String(right.theme_type || '').trim() === 'global_theme'
      if (leftIsGlobal !== rightIsGlobal) {
        return leftIsGlobal ? 1 : -1
      }
      return Number(right.smoothed_heat_score ?? 0) - Number(left.smoothed_heat_score ?? 0)
    })
    .forEach((item) => {
      const marketCode = String(item.market_code || '').trim()
      const themeName = formatLocalThemeName(item.theme_name)
      if (!marketCode || !themeName) {
        return
      }
      if (!grouped.has(marketCode)) {
        grouped.set(marketCode, [])
      }
      const marketThemes = grouped.get(marketCode)
      if (!marketThemes.includes(themeName)) {
        marketThemes.push(themeName)
      }
    })

  return Array.from(grouped.entries()).map(([marketCode, themesForMarket]) => ({
    marketCode,
    themes: themesForMarket,
  }))
}
