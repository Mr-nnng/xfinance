import { reactive, watch } from 'vue'

const KEY = 'xfinance.chart-prefs.v1'
const defaults = {
  ma20: true,
  ma60: false,
  boll: false,
  volume: true,
  macd: true,
  rsi: false,
  kdj: false,
  numeraire: 'CNY',
}

function load() {
  try {
    const raw = window.localStorage.getItem(KEY)
    if (!raw) return { ...defaults }
    return { ...defaults, ...JSON.parse(raw) }
  } catch {
    return { ...defaults }
  }
}

const state = reactive(load())

watch(
  state,
  (value) => {
    try {
      window.localStorage.setItem(KEY, JSON.stringify(value))
    } catch {
      /* storage can be unavailable in private mode */
    }
  },
  { deep: true },
)

export function useChartPrefs() {
  return state
}
