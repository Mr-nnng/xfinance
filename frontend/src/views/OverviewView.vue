<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { get, del } from '../api'
import { fmtPct, fmtPrice, fmtTime, tone } from '../utils'
import { useToast } from '../composables/useToast'
import Sparkline from '../components/Sparkline.vue'
import CustomIndexDialog from '../components/CustomIndexDialog.vue'

const router = useRouter()
const { push } = useToast()
const data = ref(null)
const loading = ref(true)
const refreshing = ref(false)
const error = ref('')
const dialogOpen = ref(false)
let timer = null
let controller = null

const market = computed(() => data.value?.market || { label: '加载中', is_open: false })

const sourceLabel = {
  demo: '演示数据',
  tdx: '通达信',
  sina: '新浪财经',
  frankfurter: 'ECB 汇率',
  treasury: '美国财政部',
  sge: '上金所',
  cache: '本地缓存',
  expression: '表达式',
  unavailable: '不可用',
}
const sources = computed(() => {
  const labels = new Set()
  for (const source of data.value?.sources || []) {
    for (const part of String(source).split('+')) {
      labels.add(sourceLabel[part] || part)
    }
  }
  return [...labels].filter(Boolean).join(' · ')
})

const yieldCurve = computed(() => {
  if (!data.value?.yields?.length) return []
  return [...data.value.yields]
    .sort((left, right) => tenorOf(left.meta.symbol) - tenorOf(right.meta.symbol))
    .map((item) => item.value)
})

const maxYieldChange = computed(() => {
  const values = (data.value?.yields || []).map((item) => Math.abs(item.change_bp || 0))
  return Math.max(...values, 0.1)
})

function tenorOf(symbol) {
  const match = /UST(\d+)Y/.exec(symbol)
  return match ? Number(match[1]) : 99
}

async function load() {
  refreshing.value = true
  error.value = ''
  controller?.abort()
  controller = new AbortController()
  try {
    const response = await get('/overview', undefined, controller.signal)
    data.value = response.data
  } catch (requestError) {
    if (requestError.name !== 'AbortError') error.value = requestError.message
  } finally {
    loading.value = false
    refreshing.value = false
  }
}

function schedule() {
  timer = window.setTimeout(async () => {
    if (!document.hidden) await load()
    schedule()
  }, 10000)
}

function open(symbol) {
  router.push(`/s/${symbol}`)
}

function openCustom(id) {
  router.push(`/i/${id}`)
}

async function remove(symbol) {
  try {
    await del(`/watchlist/${symbol}`)
    data.value.watchlist = data.value.watchlist.filter((card) => card.meta.symbol !== symbol)
    push(`已移出自选：${symbol}`, 'success')
  } catch (requestError) {
    push(requestError.message, 'error')
  }
}

function focusSearch() {
  document.querySelector('.search-box input')?.focus()
}

async function onCreated() {
  dialogOpen.value = false
  push('自定义指数已创建', 'success')
  await load()
}

onMounted(async () => {
  await load()
  schedule()
})

onBeforeUnmount(() => {
  window.clearTimeout(timer)
  controller?.abort()
})
</script>

<template>
  <div class="page">
    <header class="page-head">
      <div>
        <p class="eyebrow">Market overview</p>
        <h1 class="page-title">市场总览</h1>
        <p class="page-sub">
          先把市场看清楚，再把同一件东西换成黄金、原油或另一种货币来看。
        </p>
      </div>
      <div class="head-meta">
        <span class="chip" :class="{ 'chip-accent': market.is_open }">
          <span class="badge-dot"></span>{{ market.label }}
        </span>
        <span v-if="data">更新于 {{ fmtTime(data.generated_at) }}</span>
        <button class="icon-btn" :class="{ spin: refreshing }" title="立即刷新" @click="load">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12a9 9 0 1 1-2.64-6.36" />
            <path d="M21 3v6h-6" />
          </svg>
        </button>
      </div>
    </header>

    <div v-if="error" class="banner error">
      <span>{{ error }}</span>
      <button class="btn btn-sm" @click="load">重试</button>
    </div>

    <template v-if="loading && !data">
      <div class="index-grid">
        <div v-for="index in 4" :key="index" class="skeleton skeleton-card"></div>
      </div>
      <div class="overview-grid">
        <div class="skeleton" style="height: 260px"></div>
        <div class="skeleton" style="height: 260px"></div>
      </div>
    </template>

    <template v-else-if="data">
      <section>
        <div class="section-head">
          <h2 class="section-title">主要指数</h2>
          <span class="section-note">点击任意卡片查看 K 线</span>
        </div>
        <div class="index-grid">
          <button
            v-for="card in data.indices"
            :key="card.meta.symbol"
            class="index-card"
            @click="open(card.meta.symbol)"
          >
            <span class="card-top">
              <span class="card-name">{{ card.meta.name }}</span>
              <span class="card-symbol">{{ card.meta.symbol }}</span>
            </span>
            <strong class="card-price mono">
              {{ fmtPrice(card.snapshot?.last) }}
            </strong>
            <span class="card-change" :class="tone(card.snapshot?.change_pct)">
              <span>{{ fmtPct(card.snapshot?.change_pct) }}</span>
              <span class="mono">{{ card.snapshot ? fmtPrice(card.snapshot.change) : '—' }}</span>
            </span>
            <div class="card-spark">
              <Sparkline :values="card.spark" />
            </div>
            <span class="card-foot">
              <span>{{ card.meta.unit }}</span>
              <span>{{ card.source === 'demo' ? '演示' : '查看 →' }}</span>
            </span>
          </button>
        </div>
      </section>

      <div class="overview-grid">
        <section class="panel">
          <div class="panel-head">
            <h2 class="panel-title">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M4 19V5" /><path d="M4 19h16" /><path d="m7 15 4-4 3 3 5-6" />
              </svg>
              自选股
            </h2>
            <button class="linkish" @click="focusSearch">搜索添加 +</button>
          </div>

          <div v-if="!data.watchlist.length" class="empty-state">
            自选列表是空的。用顶部搜索找一只股票，进入详情页点“加自选”。
          </div>
          <div v-else class="watch-table">
            <div
              v-for="card in data.watchlist"
              :key="card.meta.symbol"
              class="watch-row"
              role="link"
              tabindex="0"
              @click="open(card.meta.symbol)"
              @keydown.enter="open(card.meta.symbol)"
            >
              <span class="watch-name">
                <strong>{{ card.meta.name }}</strong>
                <span>{{ card.meta.symbol }}</span>
              </span>
              <span class="watch-spark"><Sparkline :values="card.spark" /></span>
              <span class="watch-price">{{ fmtPrice(card.snapshot?.last) }}</span>
              <span class="watch-change" :class="tone(card.snapshot?.change_pct)">
                {{ fmtPct(card.snapshot?.change_pct) }}
              </span>
              <button class="row-remove" title="移出自选" @click.stop="remove(card.meta.symbol)">
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M6 6l12 12M18 6 6 18" />
                </svg>
              </button>
            </div>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <h2 class="panel-title">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <circle cx="12" cy="12" r="9" /><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18" />
              </svg>
              美元基准
            </h2>
            <span class="panel-sub">USD → </span>
          </div>
          <div class="fx-grid">
            <button
              v-for="card in data.fx"
              :key="card.meta.symbol"
              class="fx-card"
              @click="open(card.meta.symbol)"
            >
              <span class="fx-pair">{{ card.meta.name }}</span>
              <div class="fx-value">{{ fmtPrice(card.snapshot?.last) }}</div>
              <span class="fx-delta" :class="tone(card.snapshot?.change_pct)">
                {{ fmtPct(card.snapshot?.change_pct) }}
              </span>
            </button>
          </div>
        </section>
      </div>

      <div class="overview-grid">
        <section class="panel">
          <div class="panel-head">
            <h2 class="panel-title">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M12 3v18M5 8h14M5 16h14" />
              </svg>
              硬通货
            </h2>
            <span class="panel-sub">黄金 · 白银 · 原油 · 上金所</span>
          </div>
          <div class="commodity-grid">
            <button
              v-for="card in data.commodities"
              :key="card.meta.symbol"
              class="commodity-card"
              @click="open(card.meta.symbol)"
            >
              <div class="commodity-name">{{ card.meta.name }}</div>
              <div class="commodity-value">{{ fmtPrice(card.snapshot?.last) }}</div>
              <div class="commodity-unit">{{ card.meta.unit }}</div>
              <div class="fx-delta" :class="tone(card.snapshot?.change_pct)">
                {{ fmtPct(card.snapshot?.change_pct) }}
              </div>
              <Sparkline :values="card.spark" />
            </button>
          </div>
        </section>

        <section class="panel">
          <div class="panel-head">
            <h2 class="panel-title">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M4 20h16M4 20V4M8 20v-6M12 20v-9M16 20V8M20 20v-4" />
              </svg>
              美债收益率
            </h2>
            <span class="panel-sub">bp</span>
          </div>
          <div class="yield-curve">
            <Sparkline :values="yieldCurve" tone="flat" :stroke-width="1.6" />
          </div>
          <div class="yield-list">
            <button
              v-for="card in data.yields"
              :key="card.meta.symbol"
              class="yield-row"
              @click="open(card.meta.symbol)"
            >
              <span class="tenor">{{ card.meta.symbol.replace('UST', '') }}</span>
              <span class="yield-bar">
                <span
                  class="yield-fill"
                  :style="{ width: `${Math.min(100, Math.abs(card.change_bp) / maxYieldChange * 100)}%` }"
                ></span>
              </span>
              <span class="yield-value">
                {{ card.value?.toFixed(2) }}%
                <span :class="tone(card.change_bp)" style="font-size: 9px">
                  {{ card.change_bp > 0 ? '+' : '' }}{{ card.change_bp?.toFixed(1) }}
                </span>
              </span>
            </button>
          </div>
        </section>
      </div>

      <section class="panel" style="margin-top: 13px">
        <div class="panel-head">
          <h2 class="panel-title">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z" />
            </svg>
            自定义指数
          </h2>
          <button class="btn btn-sm" @click="dialogOpen = true">新建指数 +</button>
        </div>

        <div v-if="!data.custom_indices.length" class="empty-state">
          把两个标的写成一条表达式，比如 <span class="mono">XAUUSD / WTIUSD</span>，就能得到金油比。
        </div>
        <div v-else class="custom-grid">
          <button
            v-for="card in data.custom_indices"
            :key="card.id"
            class="custom-card"
            @click="openCustom(card.id)"
          >
            <template v-if="!card.error">
              <div class="card-top">
                <span class="card-name">{{ card.name }}</span>
                <span class="chip" :class="tone(card.change_pct)">{{ fmtPct(card.change_pct) }}</span>
              </div>
              <div class="expr">{{ card.expression }}</div>
              <div class="custom-value">{{ fmtPrice(card.last) }}</div>
              <div class="pct-bar">
                <span class="pct-fill" :style="{ width: `${card.percentile ?? 0}%` }"></span>
              </div>
              <div class="pct-label">60 日分位 {{ card.percentile?.toFixed(0) ?? '—' }}%</div>
              <div class="custom-spark"><Sparkline :values="card.spark" /></div>
            </template>
            <template v-else>
              <div class="card-top">
                <span class="card-name">{{ card.name }}</span>
                <span class="chip down">不可用</span>
              </div>
              <div class="expr">{{ card.expression }}</div>
              <div class="expr-error">{{ card.error }}</div>
            </template>
          </button>
        </div>
      </section>

      <footer class="footer-note">
        <span>每 10 秒自动刷新 · 数据源：{{ sources || '—' }}</span>
        <span>演示数据仅用于离线体验</span>
      </footer>
    </template>

    <CustomIndexDialog
      :open="dialogOpen"
      @close="dialogOpen = false"
      @created="onCreated"
    />
  </div>
</template>
