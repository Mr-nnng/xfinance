<script setup>
const props = defineProps({
  symbols: { type: Array, default: () => [] },
  matrix: { type: Object, default: () => ({}) },
})

function cellStyle(row, column) {
  if (row === column) {
    return { background: 'rgba(255,255,255,0.035)', color: 'var(--faint)' }
  }
  const value = roundValue(props.matrix[row]?.[column])
  const alpha = Math.min(0.65, 0.04 + Math.abs(value) * 0.5)
  const color = value >= 0 ? `rgba(242, 85, 90, ${alpha})` : `rgba(25, 185, 122, ${alpha})`
  return {
    background: color,
    color: Math.abs(value) > 0.55 ? '#f7f9fb' : 'var(--muted)',
  }
}

function roundValue(raw) {
  const value = Number(raw ?? 0)
  return Math.abs(value) < 0.005 ? 0 : value
}

function display(row, column) {
  return roundValue(props.matrix[row]?.[column]).toFixed(2)
}

function labelStyle(size) {
  return { gridTemplateColumns: `112px repeat(${size}, minmax(58px, 1fr))` }
}
</script>

<template>
  <div class="heatmap-wrap">
    <div class="heatmap" :style="labelStyle(symbols.length)">
      <div></div>
      <div v-for="item in symbols" :key="`h-${item.symbol}`" class="heat-head" :title="item.name">
        {{ item.symbol }}
      </div>
      <template v-for="row in symbols" :key="`r-${row.symbol}`">
        <div class="heat-label" :title="`${row.name} ${row.symbol}`">{{ row.name }}</div>
        <div
          v-for="column in symbols"
          :key="`${row.symbol}-${column.symbol}`"
          class="heat-cell"
          :style="cellStyle(row.symbol, column.symbol)"
          :title="`${row.name} × ${column.name}: ${display(row.symbol, column.symbol)}`"
        >
          {{ display(row.symbol, column.symbol) }}
        </div>
      </template>
    </div>
    <div class="heat-legend">
      <span>-1 反向</span>
      <i></i>
      <span>+1 同向</span>
      <span style="margin-left: auto">日收益率 · Pearson</span>
    </div>
  </div>
</template>
