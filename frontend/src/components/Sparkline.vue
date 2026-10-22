<script setup>
import { computed, useId } from 'vue'

const props = defineProps({
  values: { type: Array, default: () => [] },
  tone: { type: String, default: 'auto' },
  strokeWidth: { type: Number, default: 1.5 },
})

const gradientId = `spark-${useId().replace(/[^a-zA-Z0-9_-]/g, '')}`
const width = 100
const height = 32
const padding = 1.5

const points = computed(() => {
  const values = props.values.filter((value) => Number.isFinite(Number(value)))
  if (values.length < 2) return []
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  return values.map((value, index) => ({
    x: (index / (values.length - 1)) * width,
    y: height - padding - ((value - min) / span) * (height - padding * 2),
  }))
})

const direction = computed(() => {
  if (props.tone !== 'auto') return props.tone
  const values = props.values.filter((value) => Number.isFinite(Number(value)))
  if (values.length < 2) return 'flat'
  return values[values.length - 1] >= values[0] ? 'up' : 'down'
})

const stroke = computed(
  () => ({ up: '#f2555a', down: '#19b97a', flat: '#7d8b9d' })[direction.value],
)

const linePath = computed(() => {
  const list = points.value
  if (!list.length) return ''
  let path = `M ${list[0].x.toFixed(2)} ${list[0].y.toFixed(2)}`
  for (let index = 1; index < list.length; index += 1) {
    const previous = list[index - 1]
    const current = list[index]
    const middle = (previous.x + current.x) / 2
    path += ` C ${middle.toFixed(2)} ${previous.y.toFixed(2)} ${middle.toFixed(2)} ${current.y.toFixed(2)} ${current.x.toFixed(2)} ${current.y.toFixed(2)}`
  }
  return path
})

const areaPath = computed(() => {
  const list = points.value
  if (!list.length) return ''
  return `${linePath.value} L ${width} ${height} L 0 ${height} Z`
})
</script>

<template>
  <svg
    v-if="points.length"
    class="spark"
    :viewBox="`0 0 ${width} ${height}`"
    preserveAspectRatio="none"
    aria-hidden="true"
  >
    <defs>
      <linearGradient :id="gradientId" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" :stop-color="stroke" stop-opacity="0.22" />
        <stop offset="100%" :stop-color="stroke" stop-opacity="0" />
      </linearGradient>
    </defs>
    <path :d="areaPath" :fill="`url(#${gradientId})`" />
    <path
      :d="linePath"
      fill="none"
      :stroke="stroke"
      :stroke-width="strokeWidth"
      stroke-linecap="round"
      stroke-linejoin="round"
      vector-effect="non-scaling-stroke"
    />
  </svg>
  <div v-else class="spark spark-empty" aria-hidden="true"></div>
</template>
