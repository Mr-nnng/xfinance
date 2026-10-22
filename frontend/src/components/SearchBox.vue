<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { get } from '../api'
import { kindLabel } from '../utils'

const router = useRouter()
const query = ref('')
const results = ref([])
const open = ref(false)
const active = ref(0)
const loading = ref(false)
const error = ref('')
const input = ref(null)
const root = ref(null)
let debounceTimer = null
let controller = null


const showDropdown = computed(() => open.value && (query.value.length > 0))

function scheduleSearch() {
  window.clearTimeout(debounceTimer)
  const text = query.value.trim()
  if (!text) {
    results.value = []
    loading.value = false
    return
  }
  loading.value = true
  debounceTimer = window.setTimeout(() => search(text), 180)
}

async function search(text) {
  controller?.abort()
  controller = new AbortController()
  try {
    const response = await get('/search', { q: text, limit: 10 }, controller.signal)
    if (query.value.trim() !== text) return
    results.value = response.data
    active.value = 0
    error.value = ''
  } catch (requestError) {
    if (requestError.name !== 'AbortError') {
      error.value = requestError.message
      results.value = []
    }
  } finally {
    loading.value = false
  }
}

function choose(item) {
  if (!item) return
  open.value = false
  query.value = ''
  results.value = []
  router.push(`/s/${item.symbol}`)
}

function onKeydown(event) {
  if (event.key === 'ArrowDown') {
    event.preventDefault()
    active.value = Math.min(active.value + 1, results.value.length - 1)
  } else if (event.key === 'ArrowUp') {
    event.preventDefault()
    active.value = Math.max(active.value - 1, 0)
  } else if (event.key === 'Enter') {
    event.preventDefault()
    choose(results.value[active.value])
  } else if (event.key === 'Escape') {
    open.value = false
    input.value?.blur()
  }
}

function onGlobalKeydown(event) {
  const tag = document.activeElement?.tagName
  const typing = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
  if ((event.key === '/' && !typing) || (event.key.toLowerCase() === 'k' && (event.metaKey || event.ctrlKey))) {
    event.preventDefault()
    input.value?.focus()
    input.value?.select()
  }
}

function onDocumentClick(event) {
  if (!root.value?.contains(event.target)) open.value = false
}

watch(query, () => {
  open.value = true
  scheduleSearch()
})

onMounted(() => {
  document.addEventListener('keydown', onGlobalKeydown)
  document.addEventListener('click', onDocumentClick)
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onGlobalKeydown)
  document.removeEventListener('click', onDocumentClick)
  controller?.abort()
  window.clearTimeout(debounceTimer)
})
</script>

<template>
  <div ref="root" class="search-box">
    <div class="search-input-wrap">
      <span class="search-icon">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
      </span>
      <input
        ref="input"
        v-model="query"
        type="search"
        placeholder="搜索代码 / 名称，例如 600519、黄金"
        aria-label="搜索标的"
        autocomplete="off"
        @focus="open = true"
        @keydown="onKeydown"
      />
      <span class="search-kbd">/</span>
    </div>

    <transition name="fade">
      <div v-if="showDropdown" class="search-results">
        <div v-if="loading" class="search-empty">搜索中…</div>
        <div v-else-if="error" class="search-empty">{{ error }}</div>
        <div v-else-if="!results.length" class="search-empty">没有找到 “{{ query }}”</div>
        <template v-else>
          <button
            v-for="(item, index) in results"
            :key="item.symbol"
            class="search-result"
            :class="{ active: index === active }"
            @mousedown.prevent="choose(item)"
            @mouseenter="active = index"
          >
            <span class="code">{{ item.symbol }}</span>
            <span class="name">{{ item.name }}</span>
            <span class="kind">{{ kindLabel(item.kind) }}</span>
          </button>
        </template>
      </div>
    </transition>
  </div>
</template>
