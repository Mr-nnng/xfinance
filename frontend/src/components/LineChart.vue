<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  AreaSeries,
  CrosshairMode,
  LineSeries,
  LineStyle,
  createChart,
} from 'lightweight-charts'
import { fmtPrice, formatChartDate, formatChartTick } from '../utils'

const props = defineProps({
  series: { type: Array, default: () => [] },
  height: { type: Number, default: 260 },
  formatter: { type: Function, default: null },
})

const container = ref(null)
let chart = null

const latest = computed(() =>
  props.series.map((item) => ({
    name: item.name,
    color: item.color,
    value: item.data.at(-1)?.value,
  })),
)

function format(value) {
  return props.formatter ? props.formatter(value) : fmtPrice(value)
}

function build() {
  destroy()
  if (!container.value || !props.series.length) return
  chart = createChart(container.value, {
    autoSize: true,
    layout: {
      background: { type: 'solid', color: 'transparent' },
      textColor: '#8b9bb0',
      fontFamily: "'JetBrains Mono', 'SFMono-Regular', ui-monospace, monospace",
      fontSize: 11,
      attributionLogo: false,
    },
    grid: {
      vertLines: { color: 'rgba(255,255,255,0.025)' },
      horzLines: { color: 'rgba(255,255,255,0.045)' },
    },
    crosshair: {
      mode: CrosshairMode.Normal,
      vertLine: { color: 'rgba(240,179,91,0.35)', width: 1, style: LineStyle.Dashed, labelBackgroundColor: '#1d2836' },
      horzLine: { color: 'rgba(240,179,91,0.25)', width: 1, style: LineStyle.Dashed, labelBackgroundColor: '#1d2836' },
    },
    rightPriceScale: { borderVisible: false, entireTextOnly: true },
    timeScale: {
      borderVisible: false,
      rightOffset: 2,
      barSpacing: 6,
      minBarSpacing: 2,
      tickMarkFormatter: formatChartTick,
    },
    localization: {
      locale: 'zh-CN',
      priceFormatter: format,
      timeFormatter: formatChartDate,
    },
  })

  for (const item of props.series) {
    if (item.area) {
      const series = chart.addSeries(AreaSeries, {
        lineColor: item.color,
        lineWidth: 2,
        topColor: `${item.color}33`,
        bottomColor: `${item.color}00`,
        priceLineVisible: false,
        lastValueVisible: false,
        priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
      })
      series.setData(item.data)
    } else {
      const series = chart.addSeries(LineSeries, {
        color: item.color,
        lineWidth: 1.5,
        lineStyle: item.dashed ? LineStyle.Dashed : LineStyle.Solid,
        priceLineVisible: false,
        lastValueVisible: false,
        priceFormat: { type: 'price', precision: 2, minMove: 0.01 },
      })
      series.setData(item.data)
    }
  }
  chart.timeScale().fitContent()
}

function destroy() {
  if (chart) {
    chart.remove()
    chart = null
  }
}

onMounted(async () => {
  await nextTick()
  build()
})

onBeforeUnmount(destroy)

watch(
  () => [props.series, props.height],
  async () => {
    await nextTick()
    build()
  },
  { deep: true },
)
</script>

<template>
  <div class="line-chart">
    <div class="chart-legend" style="padding: 0 0 8px">
      <span v-for="item in latest" :key="item.name" class="legend-ohlc" style="margin-right: 14px">
        <span class="badge-dot" :style="{ background: item.color }"></span>
        <span>{{ item.name }} <b>{{ format(item.value) }}</b></span>
      </span>
    </div>
    <div ref="container" :style="{ height: `${height}px` }" class="chart-host"></div>
  </div>
</template>
