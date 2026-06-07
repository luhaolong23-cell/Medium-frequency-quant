const integerFormatter = new Intl.NumberFormat('zh-CN', {
  maximumFractionDigits: 0,
})

const currencyFormatter = new Intl.NumberFormat('zh-CN', {
  style: 'currency',
  currency: 'USD',
  maximumFractionDigits: 0,
})

export function formatNumber(value, digits = 2) {
  if (value === undefined || value === null || Number.isNaN(Number(value))) {
    return '--'
  }
  return new Intl.NumberFormat('zh-CN', {
    maximumFractionDigits: digits,
  }).format(value)
}

export function formatInteger(value) {
  if (value === undefined || value === null || Number.isNaN(Number(value))) {
    return '--'
  }
  return integerFormatter.format(value)
}

export function formatPercent(value, digits = 1) {
  if (value === undefined || value === null || Number.isNaN(Number(value))) {
    return '--'
  }
  return `${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: digits }).format(Number(value) * 100)}%`
}

export function formatMoney(value) {
  if (value === undefined || value === null || Number.isNaN(Number(value))) {
    return '--'
  }
  return currencyFormatter.format(value)
}

export function formatDateTime(value) {
  if (!value) {
    return '--'
  }
  return value.replace('T', ' ').slice(0, 16)
}

export function toneForRegime(status) {
  if (status === 'BULL') {
    return 'tone-bull'
  }
  if (status === 'NEUTRAL') {
    return 'tone-neutral'
  }
  return 'tone-bear'
}

export function toneForPnL(value) {
  if (value > 0) {
    return 'tone-bull-text'
  }
  if (value < 0) {
    return 'tone-bear-text'
  }
  return 'tone-neutral-text'
}
