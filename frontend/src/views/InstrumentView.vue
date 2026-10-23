<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { del, get, post } from '../api'
import {
  fmtCompact,
  fmtPct,
  fmtPrice,
  fmtSigned,
  fmtTime,
  tone,
} from '../utils'
import { useChartPrefs } from '../composables/useChartPrefs'
import { useToast } from '../composables/useToast'
import PriceChart from '../components/PriceChart.vue'

const route = useRoute()
const router = useRouter()
const prefs = useChartPrefs()
const { push } = useToast()

const symbol = computed(() => String(route.params.symbol || '').toUpperCase())
const meta = ref(null)
const snapshot = ref(null)
const chart = ref(null)
const numeraires = ref([])
const loading = ref(true)
const chartLoading = ref(false)
const error = ref('')
const snapshotError = ref('')
const indicatorOpen = ref(false)
const indicatorMenu = ref(null)

const timeframe = ref('1d')
const adjust = ref('qfq')
const range = ref('1y')
const normalize = ref(false)
const numeraire = ref('CNY')
let controller = null
let snapshotTimer = null
let snapController = null

const kindLabel = {
  stock: 'A 股',
  etf: 'ETF',
  lof: 'LOF',
  index: '指数',
  fx: '汇率',
  commodity: '商品',
  yield: '美债',
}
const sourceLabel = {
  demo: '演示数据',
  tdx: '通达信',
  sina: '新浪财经',
  frankfurter: 'ECB',
  treasury: '美国财政部',
  sge: '上金所',
  cache: '缓存',
  expression: '表达式',
}

const groups = computed(() => {
  const groups = {}
  for (const item of numeraires.value) {
    ;(groups[item.group] ||= []).push(item)
  }
  return groups
})

const isEquity = computed(() =>
  ['stock', 'etf', 'lof', 'index'].includes(meta.value?.kind),
)
const canAdjust = computed(() => ['stock', 'etf', 'lof'].includes(meta.value?.kind))
const isYield = computed(() => meta.value?.kind === 'yield')
const hasOrderBook = computed(() => ['stock', 'etf', 'lof'].includes(meta.value?.kind))
const showVolume = computed(() => prefs.volume && isEquity.value)

const indicatorSpec = computed(() => {
  const parts = []
  if (prefs.ma20) parts.push('ma:20')
  if (prefs.ma60) parts.push('ma:60')
  if (prefs.boll) parts.push('boll:20')
  if (prefs.macd) parts.push('macd')
  if (prefs.rsi) parts.push('rsi:14')
  if (prefs.kdj) parts.push('kdj')
  return parts.join(',')
})

const activeIndicators = computed(
  () => [prefs.ma20, prefs.ma60, prefs.boll, prefs.macd, prefs.rsi, prefs.kdj].filter(Boolean).length,
)

const numeraireMeta = computed(
  () => numeraires.value.find((item) => item.id === numeraire.value) || { id: 'CNY', label: '人民币', unit: '元' },
)
const chartMeta = computed(() => chart.value?.meta)
const selectedUnit = computed(() => {
  if (isYield.value) return '%'
  return numeraireMeta.value.unit
})
const quoted = computed(() => chartMeta.value?.quoted !== false && !chartMeta.value?.quote_error)
const stats = computed(() => chart.value?.stats || null)
const flatChart = computed(() => {
  const bars = chart.value?.bars
  if (!bars || bars.length < 2) return false
  const first = bars[0].close
  return bars.every((bar) => Math.abs(bar.close - first) <= 1e-9)
})

const conversion = computed(() => {
  if (!stats.value || !quoted.value || isYield.value) return null
  const kind = meta.value?.kind
  const price = stats.value.last
  const unit = numeraireMeta.value.unit
  if (normalize.value) {
    return {
      normalized: true,
      text: `起点 = 1.0000，当前 = ${fmtPrice(price)}`,
    }
  }
  if (kind === 'stock' || kind === 'etf' || kind === 'lof') {
    const inverse =
      price > 0 && numeraireMeta.value.id !== meta.value?.currency
        ? `1 ${unit} ≈ ${fmtPrice(1 / price)} ${meta.value?.unit || '股'}`
        : ''
    return {
      normalized: false,
      text: `1 ${meta.value?.unit || '股'} ≈ ${fmtPrice(price)} ${unit}`,
      inverse,
    }
  }
  if (kind === 'index') {
    return { normalized: false, text: `当前指数点位折算 ${fmtPrice(price)} ${unit}`, inverse: '' }
  }
  if (kind === 'fx') {
    const inverse =
      price > 0 && numeraireMeta.value.id !== 'USD'
        ? `1 ${unit} ≈ ${fmtPrice(1 / price)} 美元`
        : ''
    return { normalized: false, text: `1 美元 = ${fmtPrice(price)} ${unit}`, inverse }
  }
  if (kind === 'commodity') {
    const quantity = meta.value?.unit?.split('/').pop() || '单位'
    return {
      normalized: false,
      text: `1 ${quantity} = ${fmtPrice(price)} ${unit}`,
      inverse: price > 0 ? `1 ${unit} ≈ ${fmtPrice(1 / price)} ${quantity}` : '',
    }
  }
  return { normalized: false, text: `当前 ${fmtPrice(price)} ${unit}`, inverse: '' }
})

const bestAsk = computed(() => snapshot.value?.asks?.[0]?.price)
const bestBid = computed(() => snapshot.value?.bids?.[0]?.price)
const bookMax = computed(() => {
  const levels = [...(snapshot.value?.asks || []), ...(snapshot.value?.bids || [])]
  return Math.max(...levels.map((level) => level.volume), 1)
})

const rangeOptions = [
  ['1m', '1月'],
  ['3m', '3月'],
  ['6m', '6月'],
  ['1y', '1年'],
  ['3y', '3年'],
  ['5y', '5年'],
  ['max', '全部'],
]
const timeframeOptions = [
  ['1d', '日'],
  ['1w', '周'],
  ['1m', '月'],
]
const adjustOptions = [
  ['qfq', '前复权'],
  ['hfq', '后复权'],
  ['none', '不复权'],
]

function indicatorSpecForRequest() {
  return indicatorSpec.value
}

async function loadMeta() {
  const response = await get(`/instruments/${symbol.value}`)
  meta.value = response.data
  if (!canAdjust.value && adjust.value !== 'none') adjust.value = 'none'
}

async function loadSnapshot() {
  snapController?.abort()
  snapController = new AbortController()
  try {
    const response = await get(`/instruments/${symbol.value}/snapshot`, undefined, snapController.signal)
    snapshot.value = response.data
    snapshotError.value = ''
  } catch (requestError) {
    if (requestError.name !== 'AbortError') snapshotError.value = requestError.message
  }
}

async function loadChart() {
  controller?.abort()
  controller = new AbortController()
  chartLoading.value = true
  error.value = ''
  try {
    const response = await get(
      `/instruments/${symbol.value}/chart`,
      {
        timeframe: timeframe.value,
        adjust: adjust.value,
        numeraire: numeraire.value,
        normalize: normalize.value,
        range: range.value,
        indicators: indicatorSpecForRequest(),
      },
      controller.signal,
    )
    chart.value = response.data
  } catch (requestError) {
    if (requestError.name !== 'AbortError') {
      error.value = requestError.message
      chart.value = null
    }
  } finally {
    chartLoading.value = false
  }
}

async function loadNumeraires() {
  try {
    const response = await get('/meta/numeraires')
    numeraires.value = response.data
    if (!numeraires.value.some((item) => item.id === numeraire.value)) {
      numeraire.value = numeraires.value[0]?.id || 'CNY'
    }
  } catch {
    numeraires.value = [
      { id: 'CNY', label: '人民币', group: '法币', unit: '元' },
      { id: 'USD', label: '美元', group: '法币', unit: '美元' },
      { id: 'JPY', label: '日元', group: '法币', unit: '日元' },
      { id: 'EUR', label: '欧元', group: '法币', unit: '欧元' },
      { id: 'GBP', label: '英镑', group: '法币', unit: '英镑' },
      { id: 'XAU', label: '黄金', group: '贵金属', unit: '盎司' },
    ]
  }
}

function nativeNumeraire() {
  const currency = meta.value?.currency
  const available = new Set(numeraires.value.map((item) => item.id))
  if (currency && available.has(currency)) return currency
  return available.has('CNY') ? 'CNY' : numeraires.value[0]?.id || 'CNY'
}

function resetPricing() {
  numeraire.value = nativeNumeraire()
  normalize.value = false
}

async function loadAll() {
  loading.value = true
  error.value = ''
  meta.value = null
  snapshot.value = null
  chart.value = null
  await loadNumeraires()
  try {
    await loadMeta()
    resetPricing()
    await Promise.all([loadSnapshot(), loadChart()])
    document.title = `${meta.value.name} · xfinance`
  } catch (requestError) {
    error.value = requestError.message
  } finally {
    loading.value = false
  }
}

function goBack() {
  if (window.history.length > 1) router.back()
  else router.push('/')
}

function scheduleSnapshot() {
  snapshotTimer = window.setTimeout(async () => {
    if (!document.hidden) await loadSnapshot()
    scheduleSnapshot()
  }, 10000)
}

async function toggleWatch() {
  try {
    if (meta.value.watched) {
      await del(`/watchlist/${symbol.value}`)
      meta.value.watched = false
      push('已移出自选', 'success')
    } else {
      await post(`/watchlist/${symbol.value}`)
      meta.value.watched = true
      push('已加入自选', 'success')
    }
  } catch (requestError) {
    push(requestError.message, 'error')
  }
}

function onDocumentClick(event) {
  if (indicatorMenu.value && !indicatorMenu.value.contains(event.target)) {
    indicatorOpen.value = false
  }
}

watch(
  () => route.params.symbol,
  async () => {
    await loadAll()
  },
)

watch([timeframe, adjust, numeraire, normalize, range, indicatorSpec], () => {
  if (!loading.value && meta.value) loadChart()
})

onMounted(async () => {
  document.addEventListener('click', onDocumentClick)
  await loadAll()
  scheduleSnapshot()
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
  window.clearTimeout(snapshotTimer)
  controller?.abort()
  snapController?.abort()
  document.title = 'xfinance · 任意标的 × 任意硬通货'
})
</script>

<template>
  <div class="page">
    <div v-if="loading && !meta" class="detail-head">
      <div class="skeleton" style="width: 280px; height: 56px"></div>
      <div class="skeleton" style="width: 180px; height: 56px"></div>
    </div>

    <template v-else-if="meta">
      <button class="back-link" @click="goBack">
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 18l-6-6 6-6" />
        </svg>
        返回
      </button>

      <div class="detail-head" style="margin-top: 10px">
        <div>
          <div class="detail-identity">
            <div class="detail-names">
              <h1>
                {{ meta.name }}
                <span class="detail-code">{{ meta.symbol }}</span>
                <span class="chip">{{ kindLabel[meta.kind] || meta.kind }}</span>
              </h1>
              <div class="detail-sub">
                {{ meta.market }} · 原生计价 {{ meta.currency }} · 单位 {{ meta.unit }}
              </div>
            </div>
          </div>
          <div class="detail-stats">
            <div class="stat"><span>今开</span><strong>{{ fmtPrice(snapshot?.open) }}</strong></div>
            <div class="stat"><span>最高</span><strong>{{ fmtPrice(snapshot?.high) }}</strong></div>
            <div class="stat"><span>最低</span><strong>{{ fmtPrice(snapshot?.low) }}</strong></div>
            <div v-if="isEquity" class="stat"><span>成交量（手）</span><strong>{{ fmtCompact(snapshot?.volume) }}</strong></div>
            <div v-if="isEquity" class="stat"><span>成交额</span><strong>{{ fmtCompact(snapshot?.amount) }}</strong></div>
            <div v-if="snapshot" class="stat">
              <span>更新</span><strong>{{ fmtTime(snapshot.ts) }}</strong>
            </div>
          </div>
        </div>

        <div class="detail-quote">
          <div class="detail-price" :class="tone(snapshot?.change_pct)">
            {{ fmtPrice(snapshot?.last) }}
          </div>
          <div class="detail-delta" :class="tone(snapshot?.change_pct)">
            {{ fmtSigned(snapshot?.change) }} · {{ fmtPct(snapshot?.change_pct) }}
          </div>
          <div style="margin-top: 10px; display: flex; gap: 8px; justify-content: flex-end">
            <button class="btn btn-sm star-btn" :class="{ active: meta.watched }" @click="toggleWatch">
              {{ meta.watched ? '★ 已自选' : '☆ 加自选' }}
            </button>
          </div>
        </div>
      </div>

      <div v-if="error" class="banner error">
        <span>{{ error }}</span>
        <button class="btn btn-sm" @click="loadChart">重试</button>
      </div>

      <div class="detail-grid">
        <section class="chart-panel">
          <div class="chart-toolbar">
            <div class="toolbar-group">
              <span class="toolbar-label">区间</span>
              <div class="seg">
                <button
                  v-for="[key, label] in rangeOptions"
                  :key="key"
                  :class="{ active: range === key }"
                  @click="range = key"
                >
                  {{ label }}
                </button>
              </div>
            </div>

            <div class="toolbar-group">
              <span class="toolbar-label">周期</span>
              <div class="seg">
                <button
                  v-for="[key, label] in timeframeOptions"
                  :key="key"
                  :class="{ active: timeframe === key }"
                  @click="timeframe = key"
                >
                  {{ label }}
                </button>
              </div>
            </div>

            <div v-if="canAdjust" class="toolbar-group">
              <span class="toolbar-label">复权</span>
              <div class="seg">
                <button
                  v-for="[key, label] in adjustOptions"
                  :key="key"
                  :class="{ active: adjust === key }"
                  @click="adjust = key"
                >
                  {{ label }}
                </button>
              </div>
            </div>

            <div class="toolbar-right">
              <div class="toolbar-group">
                <span class="toolbar-label">计价</span>
                <select v-model="numeraire" class="select" style="width: 116px; height: 30px" :disabled="isYield">
                  <optgroup v-for="(items, group) in groups" :key="group" :label="group">
                    <option v-for="item in items" :key="item.id" :value="item.id">
                      {{ item.label }}
                    </option>
                  </optgroup>
                </select>
                <button
                  class="btn btn-sm btn-ghost"
                  title="恢复标的原生货币计价，并关闭起点归一化"
                  :disabled="isYield"
                  @click="resetPricing"
                >
                  重置
                </button>
              </div>

              <label class="switch" :title="isYield ? '收益率不支持归一化' : '把区间起点换算为 1'">
                <input v-model="normalize" type="checkbox" :disabled="isYield" />
                起点=1
              </label>

              <div ref="indicatorMenu" class="indicator-menu">
                <button class="btn btn-sm" @click.stop="indicatorOpen = !indicatorOpen">
                  指标 <span class="chip">{{ activeIndicators }}</span>
                </button>
                <div v-if="indicatorOpen" class="indicator-pop" @click.stop>
                  <label><span>MA20</span><input v-model="prefs.ma20" type="checkbox" /></label>
                  <label><span>MA60</span><input v-model="prefs.ma60" type="checkbox" /></label>
                  <label><span>BOLL(20)</span><input v-model="prefs.boll" type="checkbox" /></label>
                  <label><span>成交量</span><input v-model="prefs.volume" type="checkbox" /></label>
                  <label><span>MACD</span><input v-model="prefs.macd" type="checkbox" /></label>
                  <label><span>RSI(14)</span><input v-model="prefs.rsi" type="checkbox" /></label>
                  <label><span>KDJ(9)</span><input v-model="prefs.kdj" type="checkbox" /></label>
                </div>
              </div>
            </div>
          </div>

          <div v-if="chartMeta?.quote_error" class="chart-note warn">
            计价序列不可用，已回退原生价格：{{ chartMeta.quote_error }}
          </div>

          <div v-if="flatChart" class="chart-note warn">
            当前计价下价格恒定，可能是同一资产在用自身计价，请更换计价物。
          </div>

          <PriceChart
            v-if="chart?.bars?.length"
            :bars="chart.bars"
            :indicators="chart.indicators"
            :chart-type="chartMeta.chart"
            :show-volume="showVolume"
            :show-macd="prefs.macd"
            :show-rsi="prefs.rsi"
            :show-kdj="prefs.kdj"
            :title="`${meta.name} · ${isYield ? '收益率' : numeraireMeta.label}`"
            :unit="selectedUnit"
          />

          <div v-else-if="chartLoading" class="chart-empty">正在加载 K 线…</div>
          <div v-else class="chart-empty">所选区间没有数据</div>

          <div class="chart-note">
            <span v-if="chartMeta">
              {{ chartMeta.timeframe === '1d' ? '日线' : chartMeta.timeframe === '1w' ? '周线' : '月线' }}
              · 来源 {{ sourceLabel[chartMeta.source] || chartMeta.source }}
              · {{ chart?.bars?.length || 0 }} 根
              <template v-if="chartMeta.quote_error">· 原生价格</template>
            </span>
            <span v-else>切换计价方式，观察同一段行情换一种尺度后的形状。</span>
          </div>
        </section>

        <aside class="side-panel">
          <section class="panel">
            <div class="panel-head">
              <h2 class="panel-title">实时快照</h2>
              <span class="panel-sub">{{ snapshot ? sourceLabel[snapshot.source] || snapshot.source : '—' }}</span>
            </div>
            <div v-if="snapshot" class="snapshot-block">
              <div class="snapshot-price" :class="tone(snapshot.change_pct)">{{ fmtPrice(snapshot.last) }}</div>
              <div class="fx-delta" :class="tone(snapshot.change_pct)">
                {{ fmtSigned(snapshot.change) }} · {{ fmtPct(snapshot.change_pct) }}
              </div>

              <div v-if="snapshot.asks?.length && hasOrderBook" class="book">
                <div v-for="(level, index) in [...snapshot.asks].reverse()" :key="`a${index}`" class="book-row">
                  <span class="book-label">卖{{ snapshot.asks.length - index }}</span>
                  <span class="book-bar">
                    <i class="ask" :style="{ width: `${(level.volume / bookMax) * 100}%` }"></i>
                  </span>
                  <span class="book-price" style="color: var(--down)">{{ fmtPrice(level.price) }}</span>
                  <span class="book-volume">{{ fmtCompact(level.volume) }}</span>
                </div>
                <div class="book-row" style="height: 24px">
                  <span class="book-label">价差</span>
                  <span class="book-bar"></span>
                  <span class="book-price" style="color: var(--accent)">
                    {{ bestAsk && bestBid ? fmtPrice(bestAsk - bestBid) : '—' }}
                  </span>
                  <span class="book-volume"></span>
                </div>
                <div v-for="(level, index) in snapshot.bids" :key="`b${index}`" class="book-row">
                  <span class="book-label">买{{ index + 1 }}</span>
                  <span class="book-bar">
                    <i class="bid" :style="{ width: `${(level.volume / bookMax) * 100}%` }"></i>
                  </span>
                  <span class="book-price" style="color: var(--up)">{{ fmtPrice(level.price) }}</span>
                  <span class="book-volume">{{ fmtCompact(level.volume) }}</span>
                </div>
              </div>
              <div v-else class="tool-hint" style="margin-top: 10px">
                该品种没有盘口深度，显示最新快照与日内区间。
              </div>
              <div v-if="snapshotError" class="expr-error">{{ snapshotError }}</div>
            </div>
            <div v-else class="tool-hint">快照加载中…</div>
          </section>

          <section class="panel">
            <div class="panel-head">
              <h2 class="panel-title">计价换算</h2>
              <span class="panel-sub">{{ isYield ? '不适用' : numeraireMeta.label }}</span>
            </div>
            <div v-if="isYield" class="tool-hint">收益率序列以百分比呈现，不做计价换算。</div>
            <div v-else-if="conversion" class="snapshot-block">
              <div class="quote-conversion" style="margin-top: 0">
                {{ conversion.text }}
                <div v-if="conversion.normalized" style="margin-top: 4px; color: var(--faint)">
                  归一化后的涨跌幅不受起点影响。
                </div>
              </div>
              <div v-if="conversion.inverse" class="tool-hint" style="margin-top: 8px">
                {{ conversion.inverse }}
              </div>
              <div class="meta-list" style="margin-top: 12px">
                <div class="meta-row"><span>原生价格</span><strong>{{ fmtPrice(stats?.native_last) }} {{ meta.currency }}</strong></div>
                <div class="meta-row"><span>计价后</span><strong>{{ fmtPrice(stats?.last) }} {{ selectedUnit }}</strong></div>
                <div class="meta-row"><span>区间涨跌</span><strong :class="tone(stats?.change_pct)">{{ fmtPct(stats?.change_pct) }}</strong></div>
                <div class="meta-row"><span>区间高点</span><strong>{{ fmtPrice(stats?.high) }}</strong></div>
                <div class="meta-row"><span>区间低点</span><strong>{{ fmtPrice(stats?.low) }}</strong></div>
              </div>
            </div>
            <div v-else class="tool-hint">计价数据暂时不可用。</div>
          </section>

          <section class="panel">
            <div class="panel-head">
              <h2 class="panel-title">标的</h2>
              <span class="panel-sub">{{ meta.symbol }}</span>
            </div>
            <div class="meta-list">
              <div class="meta-row"><span>类型</span><strong>{{ kindLabel[meta.kind] || meta.kind }}</strong></div>
              <div class="meta-row"><span>市场</span><strong>{{ meta.market }}</strong></div>
              <div class="meta-row"><span>原生货币</span><strong>{{ meta.currency }}</strong></div>
              <div class="meta-row"><span>报价单位</span><strong>{{ meta.unit }}</strong></div>
              <div class="meta-row"><span>数据源</span><strong>{{ chartMeta ? sourceLabel[chartMeta.source] || chartMeta.source : '—' }}</strong></div>
              <div class="meta-row"><span>自选</span><strong>{{ meta.watched ? '已加入' : '未加入' }}</strong></div>
            </div>
          </section>
        </aside>
      </div>
    </template>

    <div v-else class="banner error">
      <span>{{ error || '标的加载失败' }}</span>
      <button class="btn btn-sm" @click="loadAll">重试</button>
    </div>
  </div>
</template>
