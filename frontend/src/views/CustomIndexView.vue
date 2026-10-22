<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { del, get } from '../api'
import { fmtPct, fmtPrice, kindLabel, tone } from '../utils'
import { useToast } from '../composables/useToast'
import PriceChart from '../components/PriceChart.vue'

const route = useRoute()
const router = useRouter()
const { push } = useToast()
const indexId = computed(() => route.params.id)
const payload = ref(null)
const loading = ref(true)
const error = ref('')
const range = ref('1y')
const windowSize = ref(60)
const deleting = ref(false)
let controller = null

const rangeOptions = [
  ['6m', '6月'],
  ['1y', '1年'],
  ['3y', '3年'],
  ['5y', '5年'],
  ['max', '全部'],
]
const windowOptions = [20, 60, 120, 250]

const meta = computed(() => payload.value?.meta)
const stats = computed(() => payload.value?.stats)

async function load() {
  controller?.abort()
  controller = new AbortController()
  loading.value = true
  error.value = ''
  try {
    const response = await get(
      `/custom-indices/${indexId.value}/chart`,
      { range: range.value, window: windowSize.value },
      controller.signal,
    )
    payload.value = response.data
    document.title = `${response.data.meta.name} · xfinance`
  } catch (requestError) {
    if (requestError.name !== 'AbortError') {
      error.value = requestError.message
      payload.value = null
    }
  } finally {
    loading.value = false
  }
}

async function remove() {
  if (!window.confirm(`删除自定义指数“${meta.value?.name}”？`)) return
  deleting.value = true
  try {
    await del(`/custom-indices/${indexId.value}`)
    push('自定义指数已删除', 'success')
    router.push('/')
  } catch (requestError) {
    push(requestError.message, 'error')
  } finally {
    deleting.value = false
  }
}

watch([range, windowSize], load)
watch(
  () => route.params.id,
  () => load(),
)

onMounted(load)
onBeforeUnmount(() => {
  controller?.abort()
  document.title = 'xfinance · 任意标的 × 任意硬通货'
})
</script>

<template>
  <div class="page">
    <button class="back-link" @click="router.push('/')">
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
        <path d="M15 18l-6-6 6-6" />
      </svg>
      返回总览
    </button>

    <div v-if="error" class="banner error" style="margin-top: 16px">
      <span>{{ error }}</span>
      <button class="btn btn-sm" @click="load">重试</button>
    </div>

    <template v-if="meta">
      <div class="custom-head" style="margin-top: 10px">
        <div>
          <p class="eyebrow">Custom index</p>
          <h1 class="page-title">{{ meta.name }}</h1>
          <div class="detail-sub">自定义指数 · 表达式结果</div>
          <div class="expression-display">{{ meta.expression }}</div>
          <div class="ref-list">
            <span v-for="reference in payload.references" :key="reference.symbol" class="ref-chip">
              <b>{{ kindLabel(reference.kind) }}</b>{{ reference.symbol }} · {{ reference.name }}
            </span>
            <span class="ref-chip"><b>basis</b>{{ meta.basis }}</span>
          </div>
        </div>
        <div class="detail-quote">
          <div class="detail-price">{{ fmtPrice(stats?.last) }}</div>
          <div class="detail-delta" :class="tone(stats?.change_pct)">{{ fmtPct(stats?.change_pct) }}</div>
          <div style="margin-top: 10px">
            <button class="btn btn-sm btn-danger" :disabled="deleting" @click="remove">
              {{ deleting ? '删除中…' : '删除指数' }}
            </button>
          </div>
        </div>
      </div>

      <div class="metrics-grid">
        <div class="metric"><span>最新</span><strong>{{ fmtPrice(stats?.last) }}</strong></div>
        <div class="metric"><span>{{ windowSize }} 日分位</span><strong>{{ stats?.percentile?.toFixed(0) }}%</strong></div>
        <div class="metric"><span>区间涨跌</span><strong :class="tone(stats?.change_pct)">{{ fmtPct(stats?.change_pct) }}</strong></div>
        <div class="metric"><span>区间高低</span><strong style="font-size: 13px">{{ fmtPrice(stats?.high) }} / {{ fmtPrice(stats?.low) }}</strong></div>
      </div>

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
            <span class="toolbar-label">分位窗口</span>
            <div class="seg">
              <button
                v-for="size in windowOptions"
                :key="size"
                :class="{ active: windowSize === size }"
                @click="windowSize = size"
              >
                {{ size }}d
              </button>
            </div>
          </div>
          <div class="toolbar-right">
            <span class="panel-sub">分位线在下方独立面板</span>
          </div>
        </div>

        <div v-if="loading && !payload" class="chart-empty">正在计算表达式…</div>
        <PriceChart
          v-else-if="payload?.bars?.length"
          :bars="payload.bars"
          :indicators="{}"
          :percentile="payload.percentile"
          chart-type="line"
          :show-volume="false"
          :show-macd="false"
          :show-rsi="false"
          :show-kdj="false"
          :title="meta.name"
          :unit="meta.basis === '%' ? '%' : '比值'"
          :percentile-name="`${windowSize}日分位`"
        />
        <div v-else class="chart-empty">表达式没有可用数据</div>

        <div class="chart-note">
          价格序列先折算为美元，收益率序列保持百分比 · 当前区间 {{ payload?.bars?.length || 0 }} 个点
        </div>
      </section>

      <section class="panel" style="margin-top: 13px">
        <div class="panel-head">
          <h2 class="panel-title">分位分布</h2>
          <span class="panel-sub">{{ windowSize }} 日滚动窗口 · 当前 {{ stats?.percentile?.toFixed(0) }}%</span>
        </div>
        <div class="pct-bar" style="height: 6px">
          <span class="pct-fill" :style="{ width: `${stats?.percentile ?? 0}%` }"></span>
        </div>
        <div class="tool-hint" style="margin-top: 9px">
          0% 表示处在窗口最低位，100% 表示处在最高位。当前值在最近 {{ windowSize }} 个交易日中的相对位置。
        </div>
      </section>
    </template>

    <div v-else-if="loading" class="skeleton" style="height: 320px; margin-top: 20px"></div>

    <div v-else-if="!error" class="empty-state" style="margin-top: 20px">没有找到这个指数。</div>
  </div>
</template>
