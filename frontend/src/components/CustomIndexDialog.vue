<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { post } from '../api'
import { fmtPrice, kindLabel } from '../utils'
import Sparkline from './Sparkline.vue'

const props = defineProps({ open: { type: Boolean, default: false } })
const emit = defineEmits(['close', 'created'])

const name = ref('')
const expression = ref('')
const validation = ref({ status: 'idle', message: '', data: null })
const submitting = ref(false)
const submitError = ref('')
const nameInput = ref(null)
let timer = null
let controller = null

const examples = ['XAUUSD / WTIUSD', 'XAUUSD / XAGUSD', 'SH600519 / XAUUSD', 'UST10Y - UST2Y']

const canCreate = computed(
  () => validation.value.status === 'ok' && name.value.trim().length > 0 && !submitting.value,
)
const previewValues = computed(() =>
  (validation.value.data?.preview || []).map((point) => point.value),
)

function reset() {
  name.value = ''
  expression.value = ''
  validation.value = { status: 'idle', message: '', data: null }
  submitError.value = ''
  submitting.value = false
}

function close() {
  emit('close')
}

async function validate(text) {
  const value = text.trim()
  if (!value) {
    validation.value = { status: 'idle', message: '', data: null }
    return
  }
  controller?.abort()
  controller = new AbortController()
  validation.value = { status: 'loading', message: '正在校验…', data: null }
  try {
    const response = await post('/custom-indices/validate', { expression: value }, controller.signal)
    validation.value = { status: 'ok', message: '', data: response.data }
  } catch (error) {
    if (error.name === 'AbortError') return
    validation.value = { status: 'error', message: error.message, data: null }
  }
}

async function submit() {
  if (!canCreate.value) return
  submitting.value = true
  submitError.value = ''
  try {
    await post('/custom-indices', {
      name: name.value.trim(),
      expression: expression.value.trim(),
    })
    emit('created')
  } catch (error) {
    submitError.value = error.message
  } finally {
    submitting.value = false
  }
}

function useExample(example) {
  expression.value = example
}

watch(expression, (value) => {
  submitError.value = ''
  window.clearTimeout(timer)
  if (!value.trim()) {
    validation.value = { status: 'idle', message: '', data: null }
    return
  }
  timer = window.setTimeout(() => validate(value), 350)
})

watch(
  () => props.open,
  async (open) => {
    document.body.style.overflow = open ? 'hidden' : ''
    if (open) {
      reset()
      await nextTick()
      nameInput.value?.focus()
    }
  },
)

function onKeydown(event) {
  if (event.key === 'Escape' && props.open) close()
}

onMounted(() => document.addEventListener('keydown', onKeydown))
onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
  controller?.abort()
  window.clearTimeout(timer)
})
</script>

<template>
  <Teleport to="body">
    <transition name="fade">
      <div v-if="open" class="modal-backdrop" @click.self="close">
        <div class="modal-card" role="dialog" aria-modal="true" aria-labelledby="new-index-title">
          <div class="modal-head">
            <div>
              <h2 id="new-index-title">新建自定义指数</h2>
              <p>用四则运算组合行情序列。价格按各标的原币计算，不做汇率折算；跨币种含义由你自己判断。</p>
            </div>
            <button class="icon-btn" aria-label="关闭" @click="close">
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M6 6l12 12M18 6 6 18" />
              </svg>
            </button>
          </div>

          <div class="field">
            <label for="index-name">名称</label>
            <input
              id="index-name"
              ref="nameInput"
              v-model="name"
              class="input"
              maxlength="40"
              placeholder="例如：金油比"
            />
          </div>

          <div class="field" style="margin-top: 13px">
            <label for="index-expression">表达式</label>
            <input
              id="index-expression"
              v-model="expression"
              class="input mono"
              maxlength="512"
              placeholder="XAUUSD / WTIUSD"
              spellcheck="false"
            />
            <div class="example-row">
              <button
                v-for="example in examples"
                :key="example"
                type="button"
                class="example-chip"
                @click="useExample(example)"
              >
                {{ example }}
              </button>
            </div>
          </div>

          <div class="expr-preview">
            <div class="expr-preview-head">
              <span>预览</span>
              <span v-if="validation.status === 'ok'">
                {{ validation.data.references.length }} 个引用 · 基准 {{ validation.data.basis === 'native' ? '原币' : validation.data.basis }}
              </span>
            </div>

            <div v-if="validation.status === 'loading'" class="tool-hint">正在校验表达式…</div>
            <div v-else-if="validation.status === 'error'" class="expr-error">
              {{ validation.message }}
            </div>
            <div v-else-if="validation.status === 'ok'">
              <div class="ref-list">
                <span
                  v-for="reference in validation.data.references"
                  :key="reference.symbol"
                  class="ref-chip"
                >
                  <b>{{ kindLabel(reference.kind) }}</b>{{ reference.symbol }} · {{ reference.name }}
                </span>
              </div>
              <Sparkline :values="previewValues" />
              <div class="expr-preview-head" style="margin-top: 6px">
                <span>最新</span>
                <span>{{ fmtPrice(validation.data.last) }} {{ validation.data.basis === '%' ? '%' : '' }}</span>
              </div>
            </div>
            <div v-else class="tool-hint">输入表达式后自动校验，可引用 <span class="mono">XAUUSD</span> 这样的序列或 <span class="mono">@名称</span> 引用已有指数。</div>
          </div>

          <div v-if="submitError" class="expr-error">{{ submitError }}</div>

          <div class="modal-actions">
            <button class="btn btn-ghost" @click="close">取消</button>
            <button class="btn btn-primary" :disabled="!canCreate" @click="submit">
              {{ submitting ? '创建中…' : '创建指数' }}
            </button>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>
