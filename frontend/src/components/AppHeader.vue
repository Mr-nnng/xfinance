<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { get } from '../api'
import SearchBox from './SearchBox.vue'

const route = useRoute()
const status = ref(null)
const error = ref(false)
let timer = null

const mode = computed(() => status.value?.data_mode || 'auto')
const market = computed(() => status.value?.market || { label: '连接中', is_open: false })
const modeLabel = computed(() => (mode.value === 'live' ? 'LIVE' : mode.value === 'demo' ? 'DEMO' : 'AUTO'))
const overviewActive = computed(() => ['overview', 'instrument', 'custom-index'].includes(route.name))

async function load() {
  try {
    const response = await get('/meta/status')
    status.value = response.data
    error.value = false
  } catch {
    error.value = true
  }
}

function schedule() {
  timer = window.setTimeout(async () => {
    if (!document.hidden) await load()
    schedule()
  }, 30000)
}

onMounted(() => {
  load()
  schedule()
})

onBeforeUnmount(() => window.clearTimeout(timer))
</script>

<template>
  <header class="app-header">
    <div class="header-inner">
      <router-link to="/" class="brand" aria-label="xfinance 首页">
        <span class="brand-mark">x</span>
        <span>
          <span class="brand-name">xfinance</span>
          <span class="brand-sub">Hard-money lens</span>
        </span>
      </router-link>

      <nav class="nav">
        <router-link to="/" :class="{ 'nav-active': overviewActive }">总览</router-link>
        <router-link to="/tools">工具箱</router-link>
      </nav>
      <span class="mode-chip mobile-mode" :class="mode">{{ modeLabel }}</span>

      <div class="header-right">
        <SearchBox />
        <div class="market-status" :title="market.as_of || '正在连接后端'">
          <span class="status-dot" :class="{ open: market.is_open, offline: error }"></span>
          <span>{{ market.label }}</span>
          <span class="mode-chip" :class="mode">{{ modeLabel }}</span>
        </div>
      </div>
    </div>
  </header>
</template>
