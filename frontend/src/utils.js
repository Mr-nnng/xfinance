export function fmtPrice(value, digits) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  const number = Number(value)
  if (digits !== undefined) {
    return number.toLocaleString('zh-CN', {
      minimumFractionDigits: digits,
      maximumFractionDigits: digits,
    })
  }
  const abs = Math.abs(number)
  if (abs >= 1_000_000) return number.toLocaleString('zh-CN', { maximumFractionDigits: 0 })
  if (abs >= 1000) return number.toLocaleString('zh-CN', { maximumFractionDigits: 2 })
  if (abs >= 100) return number.toFixed(2)
  if (abs >= 1) return number.toFixed(3)
  if (abs >= 0.01) return number.toFixed(4)
  if (abs === 0) return '0'
  return number.toPrecision(4)
}

export function fmtCompact(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  const number = Number(value)
  const abs = Math.abs(number)
  if (abs >= 1e8) return `${(number / 1e8).toFixed(2)}亿`
  if (abs >= 1e4) return `${(number / 1e4).toFixed(2)}万`
  return number.toFixed(0)
}

export function fmtPct(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  const number = Number(value)
  return `${number > 0 ? '+' : ''}${number.toFixed(digits)}%`
}

export function fmtSigned(value, digits = 2) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—'
  const number = Number(value)
  return `${number > 0 ? '+' : ''}${number.toFixed(digits)}`
}

export function tone(value) {
  if (value > 0) return 'up'
  if (value < 0) return 'down'
  return 'flat'
}

export function fmtTime(iso, withDate = false) {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return iso
  const time = date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  })
  if (!withDate) return time
  return `${date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })} ${time}`
}

export function timeAgo(date) {
  if (!date) return '—'
  const seconds = Math.max(0, Math.round((Date.now() - date.getTime()) / 1000))
  if (seconds < 5) return '刚刚'
  if (seconds < 60) return `${seconds} 秒前`
  return `${Math.round(seconds / 60)} 分钟前`
}

export function pctChange(last, first) {
  if (!first) return 0
  return (last / first - 1) * 100
}

export function rangeFromNow(days) {
  const date = new Date()
  date.setDate(date.getDate() - days)
  return date.toISOString().slice(0, 10)
}

export function indicatorLabel(indicator) {
  const labels = { ma: 'MA', boll: 'BOLL', macd: 'MACD', rsi: 'RSI', kdj: 'KDJ' }
  return labels[indicator] || indicator
}


export const KIND_LABEL = {
  stock: 'A 股',
  etf: 'ETF',
  lof: 'LOF',
  index: '指数',
  fx: '汇率',
  commodity: '商品',
  yield: '美债',
  custom: '自定义',
}

export function kindLabel(kind) {
  return KIND_LABEL[kind] || kind
}

function chartDateParts(value) {
  if (typeof value === 'string') {
    const match = /^(\d{4})-(\d{1,2})-(\d{1,2})/.exec(value)
    if (match) {
      return { year: Number(match[1]), month: Number(match[2]), day: Number(match[3]) }
    }
    const parsed = new Date(value)
    if (Number.isNaN(parsed.getTime())) return null
    return {
      year: parsed.getFullYear(),
      month: parsed.getMonth() + 1,
      day: parsed.getDate(),
    }
  }
  if (typeof value === 'number') {
    const date = new Date(value * 1000)
    return {
      year: date.getUTCFullYear(),
      month: date.getUTCMonth() + 1,
      day: date.getUTCDate(),
      hour: date.getUTCHours(),
      minute: date.getUTCMinutes(),
    }
  }
  if (value && typeof value === 'object' && 'year' in value) {
    return { year: value.year, month: value.month, day: value.day }
  }
  return null
}

export function formatChartDate(value) {
  const parts = chartDateParts(value)
  if (!parts) return ''
  return `${parts.year}年${parts.month}月${parts.day}日`
}

export function formatChartTick(value, tickMarkType) {
  const parts = chartDateParts(value)
  if (!parts) return ''
  const month = String(parts.month).padStart(2, '0')
  const day = String(parts.day).padStart(2, '0')
  if (tickMarkType === 0) return `${parts.year}年`
  if (tickMarkType === 1) return `${parts.year}-${month}`
  if (tickMarkType >= 3) {
    const hour = String(parts.hour ?? 0).padStart(2, '0')
    const minute = String(parts.minute ?? 0).padStart(2, '0')
    return `${parts.year}-${month}-${day} ${hour}:${minute}`
  }
  return `${parts.year}-${month}-${day}`
}
