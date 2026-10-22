<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { get, post } from '../api'
import { fmtPct, fmtPrice, tone } from '../utils'
import LineChart from '../components/LineChart.vue'
import CorrelationHeatmap from '../components/CorrelationHeatmap.vue'

const active = ref('dca')
const numeraires = ref([])

const tabs = [
  ['dca', '定投回测'],
  ['correlation', '相关性'],
  ['compound', '复利计算'],
]

const dcaForm = ref({
  symbol: 'SH600519',
  start: defaultStart(),
  amount: 1000,
  day: 5,
  fee: 0.1,
  numeraire: 'CNY',
})
const dcaResult = ref(null)
const dcaLoading = ref(false)
const dcaError = ref('')

const corrForm = ref({
  symbols: 'SH600519,SZ300750,SH510300,XAUUSD',
  window: 120,
  numeraire: 'CNY',
})
const corrResult = ref(null)
const corrLoading = ref(false)
const corrError = ref('')

const compForm = ref({ principal: 100000, monthly: 2000, rate: 8, years: 10 })
const compResult = ref(null)
const compLoading = ref(false)
const compError = ref('')

const groups = computed(() => {
  const groups = {}
  for (const item of numeraires.value) {
    ;(groups[item.group] ||= []).push(item)
  }
  return groups
})

function defaultStart() {
  const date = new Date()
  date.setFullYear(date.getFullYear() - 3)
  return date.toISOString().slice(0, 10)
}

async function loadNumeraires() {
  try {
    const response = await get('/meta/numeraires')
    numeraires.value = response.data
  } catch {
    numeraires.value = [
      { id: 'CNY', label: '人民币', group: '法币', unit: '元' },
      { id: 'USD', label: '美元', group: '法币', unit: '美元' },
    ]
  }
}

async function runDca() {
  dcaLoading.value = true
  dcaError.value = ''
  try {
    const response = await get('/tools/dca', {
      symbol: dcaForm.value.symbol,
      start: dcaForm.value.start,
      amount: dcaForm.value.amount,
      day: dcaForm.value.day,
      fee: dcaForm.value.fee,
      numeraire: dcaForm.value.numeraire,
    })
    dcaResult.value = response.data
  } catch (error) {
    dcaError.value = error.message
    dcaResult.value = null
  } finally {
    dcaLoading.value = false
  }
}

async function runCorrelation() {
  corrLoading.value = true
  corrError.value = ''
  try {
    const response = await get('/tools/correlation', {
      symbols: corrForm.value.symbols,
      window: corrForm.value.window,
      numeraire: corrForm.value.numeraire,
    })
    corrResult.value = response.data
  } catch (error) {
    corrError.value = error.message
    corrResult.value = null
  } finally {
    corrLoading.value = false
  }
}

async function runCompound() {
  compLoading.value = true
  compError.value = ''
  try {
    const response = await post('/tools/compound', {
      principal: compForm.value.principal,
      monthly: compForm.value.monthly,
      annual_rate_pct: compForm.value.rate,
      years: compForm.value.years,
    })
    compResult.value = response.data
  } catch (error) {
    compError.value = error.message
    compResult.value = null
  } finally {
    compLoading.value = false
  }
}

const dcaSeries = computed(() => {
  if (!dcaResult.value) return []
  return [
    {
      name: '累计投入',
      color: '#7f8ea3',
      dashed: true,
      data: dcaResult.value.points.map((point) => ({ time: point.time, value: point.invested })),
    },
    {
      name: '持仓市值',
      color: '#f0b35b',
      area: true,
      data: dcaResult.value.points.map((point) => ({ time: point.time, value: point.value })),
    },
  ]
})

const compoundSeries = computed(() => {
  if (!compResult.value) return []
  const startYear = new Date().getFullYear()
  return [
    {
      name: '累计投入',
      color: '#7f8ea3',
      dashed: true,
      data: compResult.value.points.map((point) => ({
        time: `${startYear + point.year}-12-31`,
        value: point.contributions,
      })),
    },
    {
      name: '账户价值',
      color: '#f0b35b',
      area: true,
      data: compResult.value.points.map((point) => ({
        time: `${startYear + point.year}-12-31`,
        value: point.value,
      })),
    },
  ]
})

const recentPurchases = computed(() => [...(dcaResult.value?.purchases || [])].reverse().slice(0, 24))

watch(active, (tab) => {
  if (tab === 'correlation' && !corrResult.value && !corrLoading.value) runCorrelation()
  if (tab === 'compound' && !compResult.value && !compLoading.value) runCompound()
})

onMounted(async () => {
  await loadNumeraires()
  await runDca()
})
</script>

<template>
  <div class="page">
    <header class="page-head">
      <div>
        <p class="eyebrow">Toolbox</p>
        <h1 class="page-title">工具箱</h1>
        <p class="page-sub">把行情数据压成三个问题：定投赚了多少、几个标的是否同涨同跌、复利需要多久。</p>
      </div>
    </header>

    <div class="tool-tabs">
      <button
        v-for="[key, label] in tabs"
        :key="key"
        :class="{ active: active === key }"
        @click="active = key"
      >
        {{ label }}
      </button>
    </div>

    <template v-if="active === 'dca'">
      <div class="tool-layout">
        <section class="panel tool-form">
          <div class="panel-head">
            <h2 class="panel-title">定投回测</h2>
            <span class="panel-sub">按月扣款</span>
          </div>
          <div class="field">
            <label>标的</label>
            <input v-model="dcaForm.symbol" class="input mono" placeholder="SH600519" />
          </div>
          <div class="form-grid">
            <div class="field">
              <label>开始日期</label>
              <input v-model="dcaForm.start" class="input" type="date" />
            </div>
            <div class="field">
              <label>每期金额</label>
              <input v-model.number="dcaForm.amount" class="input mono" type="number" min="1" />
            </div>
            <div class="field">
              <label>扣款日</label>
              <input v-model.number="dcaForm.day" class="input mono" type="number" min="1" max="28" />
            </div>
            <div class="field">
              <label>费率 %</label>
              <input v-model.number="dcaForm.fee" class="input mono" type="number" min="0" max="5" step="0.05" />
            </div>
          </div>
          <div class="field">
            <label>计价</label>
            <select v-model="dcaForm.numeraire" class="select">
              <optgroup v-for="(items, group) in groups" :key="group" :label="group">
                <option v-for="item in items" :key="item.id" :value="item.id">{{ item.label }}</option>
              </optgroup>
            </select>
          </div>
          <button class="btn btn-primary" :disabled="dcaLoading" @click="runDca">
            {{ dcaLoading ? '回测中…' : '开始回测' }}
          </button>
          <p class="tool-hint">
            每月在指定日期后的第一个交易日买入，按所选计价物计算份额与市值。最大回撤按标的区间价格计算。跨计价物回测可以观察“存股票”与“存黄金”的差别。
          </p>
        </section>

        <section class="panel">
          <div v-if="dcaError" class="banner error"><span>{{ dcaError }}</span></div>
          <template v-if="dcaResult">
            <div class="metrics-grid">
              <div class="metric"><span>累计投入</span><strong>{{ fmtPrice(dcaResult.metrics.invested) }}</strong></div>
              <div class="metric"><span>期末价值</span><strong>{{ fmtPrice(dcaResult.metrics.final_value) }}</strong></div>
              <div class="metric">
                <span>总收益</span>
                <strong :class="tone(dcaResult.metrics.profit)">{{ fmtPct(dcaResult.metrics.return_pct) }}</strong>
              </div>
              <div class="metric">
                <span>年化 XIRR</span>
                <strong>{{ dcaResult.metrics.xirr_pct === null ? '—' : fmtPct(dcaResult.metrics.xirr_pct) }}</strong>
              </div>
            </div>
            <LineChart :series="dcaSeries" :height="280" />
            <div class="panel-head" style="margin-top: 18px">
              <h3 class="panel-title" style="font-size: 12px">最近买入</h3>
              <span class="panel-sub">
                {{ dcaResult.meta.name }} · {{ dcaResult.metrics.purchases }} 次 · 标的回撤
                {{ fmtPct(-dcaResult.metrics.max_drawdown_pct) }}
              </span>
            </div>
            <div class="table-scroll">
              <table class="data-table">
                <thead>
                  <tr><th>日期</th><th>买入价</th><th>金额</th><th>份额</th></tr>
                </thead>
                <tbody>
                  <tr v-for="purchase in recentPurchases" :key="purchase.time">
                    <td>{{ purchase.time }}</td>
                    <td>{{ fmtPrice(purchase.price) }}</td>
                    <td>{{ fmtPrice(purchase.amount) }}</td>
                    <td>{{ fmtPrice(purchase.units, 4) }}</td>
                  </tr>
                </tbody>
              </table>
            </div>
          </template>
          <div v-else-if="dcaLoading" class="chart-empty" style="height: 300px">正在回测…</div>
        </section>
      </div>
    </template>

    <template v-else-if="active === 'correlation'">
      <div class="tool-layout">
        <section class="panel tool-form">
          <div class="panel-head">
            <h2 class="panel-title">相关性矩阵</h2>
            <span class="panel-sub">日收益率</span>
          </div>
          <div class="field">
            <label>标的（逗号分隔，2-8 个）</label>
            <textarea v-model="corrForm.symbols" class="input mono" rows="2"></textarea>
          </div>
          <div class="form-grid">
            <div class="field">
              <label>窗口（交易日）</label>
              <select v-model.number="corrForm.window" class="select">
                <option :value="60">60</option>
                <option :value="120">120</option>
                <option :value="250">250</option>
                <option :value="500">500</option>
              </select>
            </div>
            <div class="field">
              <label>计价</label>
              <select v-model="corrForm.numeraire" class="select">
                <optgroup v-for="(items, group) in groups" :key="group" :label="group">
                  <option v-for="item in items" :key="item.id" :value="item.id">{{ item.label }}</option>
                </optgroup>
              </select>
            </div>
          </div>
          <button class="btn btn-primary" :disabled="corrLoading" @click="runCorrelation">
            {{ corrLoading ? '计算中…' : '计算相关性' }}
          </button>
          <p class="tool-hint">
            先把每个标的价格换算成所选计价物，再取共同交易日的日收益率。矩阵越大越接近 1（同向），越接近 -1 越反向。
          </p>
        </section>

        <section class="panel">
          <div v-if="corrError" class="banner error"><span>{{ corrError }}</span></div>
          <template v-if="corrResult">
            <div class="panel-head">
              <h3 class="panel-title" style="font-size: 12px">相关系数</h3>
              <span class="panel-sub">
                {{ corrResult.start }} → {{ corrResult.end }} · {{ corrResult.window }} 个交易日 ·
                {{ corrResult.numeraire.label }}
              </span>
            </div>
            <CorrelationHeatmap :symbols="corrResult.symbols" :matrix="corrResult.matrix" />
          </template>
          <div v-else-if="corrLoading" class="chart-empty" style="height: 300px">正在计算…</div>
        </section>
      </div>
    </template>

    <template v-else>
      <div class="tool-layout">
        <section class="panel tool-form">
          <div class="panel-head">
            <h2 class="panel-title">复利计算器</h2>
            <span class="panel-sub">按月复利</span>
          </div>
          <div class="form-grid">
            <div class="field">
              <label>初始本金</label>
              <input v-model.number="compForm.principal" class="input mono" type="number" min="0" />
            </div>
            <div class="field">
              <label>每月追加</label>
              <input v-model.number="compForm.monthly" class="input mono" type="number" min="0" />
            </div>
            <div class="field">
              <label>年化收益率 %</label>
              <input v-model.number="compForm.rate" class="input mono" type="number" step="0.1" />
            </div>
            <div class="field">
              <label>年数</label>
              <input v-model.number="compForm.years" class="input mono" type="number" min="1" max="60" />
            </div>
          </div>
          <button class="btn btn-primary" :disabled="compLoading" @click="runCompound">
            {{ compLoading ? '计算中…' : '计算' }}
          </button>
          <p class="tool-hint">
            用来估算长期定投的复利效果。结果不构成投资建议，也没有考虑税费与通胀。
          </p>
        </section>

        <section class="panel">
          <div v-if="compError" class="banner error"><span>{{ compError }}</span></div>
          <template v-if="compResult">
            <div class="metrics-grid">
              <div class="metric"><span>期末价值</span><strong>{{ fmtPrice(compResult.final_value) }}</strong></div>
              <div class="metric"><span>累计投入</span><strong>{{ fmtPrice(compResult.contributions) }}</strong></div>
              <div class="metric"><span>利息贡献</span><strong style="color: var(--accent)">{{ fmtPrice(compResult.interest) }}</strong></div>
              <div class="metric">
                <span>利息占比</span>
                <strong>{{ fmtPct((compResult.interest / compResult.final_value) * 100) }}</strong>
              </div>
            </div>
            <LineChart :series="compoundSeries" :height="300" />
          </template>
          <div v-else-if="compLoading" class="chart-empty" style="height: 300px">正在计算…</div>
        </section>
      </div>
    </template>

    <footer class="footer-note">
      <span>所有工具都在服务端用同一套计价函数计算，结果可复现。</span>
      <span>xfinance</span>
    </footer>
  </div>
</template>
