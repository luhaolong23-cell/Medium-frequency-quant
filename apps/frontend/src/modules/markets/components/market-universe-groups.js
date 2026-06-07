export function buildMarketUniverseRows(rows, selectedMarket) {
  const deduped = new Map()

  ;(rows || []).forEach((item) => {
    const marketCode = String(item.market_code || '').trim()
    const ticker = String(item.ticker || '').trim()
    if (!marketCode || !ticker || marketCode !== selectedMarket) {
      return
    }
    if (!deduped.has(ticker)) {
      deduped.set(ticker, item)
    }
  })

  return Array.from(deduped.values()).sort((left, right) => String(left.ticker || '').localeCompare(String(right.ticker || '')))
}
