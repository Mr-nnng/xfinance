<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  CandlestickSeries,
  CrosshairMode,
  HistogramSeries,
  LineSeries,
  LineStyle,
  createChart,
} from 'lightweight-charts'
import { fmtCompact, fmtPct, fmtPrice, formatChartDate, formatChartTick, tone } from '../utils'

const props = defineProps({
  bars: { type: Array, default: () => [] },
  indicators: { type: Object, default: () => ({}) },
  percentile: { type: Array, default: null },
  chartType: { type: String, default: 'candlestick' },
  showVolume: { type: Boolean, default: true },
  showMacd: { type: Boolean, default: false },
  showRsi: { type: Boolean, default: false },
  showKdj: { type: Boolean, default: false },
  title: { type: String, default: '' },
  unit: { type: String, default: '' },
  height: { type: Number, default: 420 },
  percentileName: { type: String, default: '分位' },
})

const container = ref(null)
const hoverTime = ref(null)
let chart = null
let mainSeries = null

const paneHeights = computed(() => {
  let extra = 0
  if (props.showVolume) extra += 72
  if (props.showMacd && props.indicators?.macd) extra += 120
  if (props.showRsi && props.indicators?.rsi) extra += 92
  if (props.showKdj && props.indicators?.kdj) extra += 92
  if (props.percentile) extra += 92
  return props.height + extra
})

const paneLabels = computed(() => {
  const labels = []
  let top = props.height + 5
  if (props.showVolume) {
    labels.push({ text: '成交量', top })
    top += 72
  }
  if (props.showMacd && props.indicators?.macd) {
    labels.push({ text: 'MACD', top })
    top += 120
  }
  if (props.showRsi && props.indicators?.rsi) {
    labels.push({ text: `RSI ${props.indicators.rsi.period}`, top })
    top += 92
  }
  if (props.showKdj && props.indicators?.kdj) {
    labels.push({ text: 'KDJ', top })
    top += 92
  }
  if (Array.isArray(props.percentile) && props.percentile.length) {
    labels.push({ text: props.percentileName, top })
    top += 92
  }
  return labels
})

const hoverIndex = computed(() => {
  if (!hoverTime.value || !props.bars.length) return props.bars.length - 1
  const index = props.bars.findIndex((bar) => bar.time === hoverTime.value)
  return index >= 0 ? index : props.bars.length - 1
})

const legendBar = computed(() => props.bars[hoverIndex.value] || null)
const previousBar = computed(() => props.bars[hoverIndex.value - 1] || null)
const legendChange = computed(() => {
  if (!legendBar.value) return 0
  const reference = previousBar.value?.close ?? legendBar.value.open
  if (!reference) return 0
  return (legendBar.value.close / reference - 1) * 100
})

const maLegend = computed(() => {
  const list = props.indicators?.ma || []
  if (!list.length || !legendBar.value) return []
  return list.map((item) => ({
    label: `MA${item.period}`,
    value: item.values[hoverIndex.value],
  }))
})

const precision = computed(() => {
  const last = Math.abs(Number(props.bars.at(-1)?.close ?? 1))
  if (last >= 100) return { precision: 2, minMove: 0.01 }
  if (last >= 1) return { precision: 3, minMove: 0.001 }
  if (last >= 0.01) return { precision: 5, minMove: 0.00001 }
  return { precision: 7, minMove: 0.0000001 }
})

const maColors = ['#f0b35b', '#6aa9ff', '#c084fc', '#34d399']

function timeKey(time) {
  if (!time) return null
  if (typeof time === 'string') return time
  if (typeof time === 'number') {
    return new Date(time * 1000).toISOString().slice(0, 10)
  }
  if (time.year) {
    return `${time.year}-${String(time.month).padStart(2, '0')}-${String(time.day).padStart(2, '0')}`
  }
  return null
}

function lineData(values) {
  if (!Array.isArray(values) || !props.bars.length) return []
  const output = []
  for (let index = 0; index < props.bars.length; index += 1) {
    const value = values[index]
    if (value === null || value === undefined || !Number.isFinite(Number(value))) continue
    output.push({ time: props.bars[index].time, value: Number(value) })
  }
  return output
}

function addLine(paneIndex, options, values) {
  const series = chart.addSeries(LineSeries, options, paneIndex)
  series.setData(lineData(values))
  return series
}

function build() {
  destroy()
  if (!container.value || !props.bars.length) return
  chart = createChart(container.value, {
    autoSize: true,
    layout: {
      background: { type: 'solid', color: 'transparent' },
      textColor: '#8b9bb0',
      fontFamily: "'JetBrains Mono', 'SFMono-Regular', ui-monospace, monospace",
      fontSize: 11,
      attributionLogo: false,
      panes: {
        enableResize: false,
        separatorColor: '#1b2735',
        separatorHoverColor: 'rgba(240, 179, 91, 0.2)',
      },
    },
    grid: {
      vertLines: { color: 'rgba(255, 255, 255, 0.028)' },
      horzLines: { color: 'rgba(255, 255, 255, 0.05)' },
    },
    crosshair: {
      mode: CrosshairMode.Normal,
      vertLine: {
        color: 'rgba(240, 179, 91, 0.4)',
        width: 1,
        style: LineStyle.Dashed,
        labelBackgroundColor: '#1d2836',
      },
      horzLine: {
        color: 'rgba(240, 179, 91, 0.28)',
        width: 1,
        style: LineStyle.Dashed,
        labelBackgroundColor: '#1d2836',
      },
    },
    rightPriceScale: {
      visible: true,
      borderVisible: false,
      entireTextOnly: true,
    },
    timeScale: {
      borderVisible: false,
      rightOffset: 2,
      barSpacing: 6,
      minBarSpacing: 2,
      timeVisible: false,
      secondsVisible: false,
      tickMarkFormatter: formatChartTick,
    },
    handleScroll: { mouseWheel: true, pressedMouseMove: true },
    handleScale: { axisPressedMouseMove: true, mouseWheel: true, pinch: true },
    localization: {
      locale: 'zh-CN',
      priceFormatter: (value) => fmtPrice(value),
      timeFormatter: formatChartDate,
    },
  })

  const common = {
    priceFormat: { type: 'price', ...precision.value },
    lastValueVisible: false,
    priceLineVisible: false,
  }

  if (props.chartType === 'line') {
    mainSeries = chart.addSeries(
      LineSeries,
      {
        ...common,
        color: '#f0b35b',
        lineWidth: 2,
        crosshairMarkerVisible: true,
        crosshairMarkerRadius: 3,
        crosshairMarkerBorderColor: '#0d131a',
        crosshairMarkerBackgroundColor: '#f0b35b',
      },
      0,
    )
    mainSeries.setData(lineData(props.bars.map((bar) => bar.close)))
  } else {
    mainSeries = chart.addSeries(
      CandlestickSeries,
      {
        ...common,
        upColor: '#f2555a',
        downColor: '#19b97a',
        wickUpColor: 'rgba(242, 85, 90, 0.72)',
        wickDownColor: 'rgba(25, 185, 122, 0.72)',
        borderVisible: false,
      },
      0,
    )
    mainSeries.setData(
      props.bars.map((bar) => ({
        time: bar.time,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
      })),
    )
  }

  ;(props.indicators?.ma || []).forEach((item, index) => {
    addLine(
      0,
      {
        ...common,
        color: maColors[index % maColors.length],
        lineWidth: 1,
        lastValueVisible: false,
        priceLineVisible: false,
      },
      item.values,
    )
  })

  if (props.indicators?.boll) {
    const boll = props.indicators.boll
    addLine(0, { ...common, color: 'rgba(147, 161, 179, 0.55)', lineWidth: 1, lineStyle: LineStyle.Dashed }, boll.upper)
    addLine(0, { ...common, color: 'rgba(147, 161, 179, 0.55)', lineWidth: 1, lineStyle: LineStyle.Dashed }, boll.lower)
    addLine(0, { ...common, color: 'rgba(147, 161, 179, 0.8)', lineWidth: 1 }, boll.mid)
  }

  let pane = 1
  const heights = []

  if (props.showVolume) {
    const volume = chart.addSeries(
      HistogramSeries,
      {
        priceFormat: { type: 'custom', formatter: (value) => fmtCompact(value), minMove: 1 },
        lastValueVisible: false,
        priceLineVisible: false,
      },
      pane,
    )
    volume.setData(
      props.bars.map((bar) => ({
        time: bar.time,
        value: bar.volume || 0,
        color: bar.close >= bar.open ? 'rgba(242, 85, 90, 0.55)' : 'rgba(25, 185, 122, 0.5)',
      })),
    )
    volume.priceScale().applyOptions({ scaleMargins: { top: 0.15, bottom: 0 } })
    heights.push([pane, 72])
    pane += 1
  }

  if (props.showMacd && props.indicators?.macd) {
    const macd = props.indicators.macd
    const histogram = chart.addSeries(
      HistogramSeries,
      { priceFormat: { type: 'price', precision: 4, minMove: 0.0001 }, lastValueVisible: false, priceLineVisible: false },
      pane,
    )
    histogram.setData(
      lineData(macd.hist).map((point) => ({
        ...point,
        color: point.value >= 0 ? 'rgba(242, 85, 90, 0.55)' : 'rgba(25, 185, 122, 0.5)',
      })),
    )
    addLine(pane, { ...common, color: '#f0b35b', lineWidth: 1 }, macd.dif)
    addLine(pane, { ...common, color: '#6aa9ff', lineWidth: 1 }, macd.dea)
    heights.push([pane, 120])
    pane += 1
  }

  if (props.showRsi && props.indicators?.rsi) {
    const rsi = chart.addSeries(
      LineSeries,
      {
        ...common,
        color: '#c084fc',
        lineWidth: 1.5,
        priceFormat: { type: 'price', precision: 1, minMove: 0.1 },
        autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }),
      },
      pane,
    )
    rsi.setData(lineData(props.indicators.rsi.values))
    rsi.createPriceLine({ price: 70, color: 'rgba(255,255,255,0.16)', lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: false, title: '' })
    rsi.createPriceLine({ price: 30, color: 'rgba(255,255,255,0.16)', lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: false, title: '' })
    heights.push([pane, 92])
    pane += 1
  }

  if (props.showKdj && props.indicators?.kdj) {
    const kdj = props.indicators.kdj
    const kSeries = addLine(pane, { ...common, color: '#f0b35b', lineWidth: 1 }, kdj.k)
    kSeries.createPriceLine({ price: 80, color: 'rgba(255,255,255,0.12)', lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: false, title: '' })
    kSeries.createPriceLine({ price: 20, color: 'rgba(255,255,255,0.12)', lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: false, title: '' })
    addLine(pane, { ...common, color: '#6aa9ff', lineWidth: 1 }, kdj.d)
    addLine(pane, { ...common, color: '#c084fc', lineWidth: 1 }, kdj.j)
    heights.push([pane, 92])
    pane += 1
  }

  if (Array.isArray(props.percentile) && props.percentile.length) {
    const series = chart.addSeries(
      LineSeries,
      {
        ...common,
        color: '#6aa9ff',
        lineWidth: 1.5,
        priceFormat: { type: 'price', precision: 0, minMove: 1 },
        autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }),
      },
      pane,
    )
    series.setData(lineData(props.percentile))
    series.createPriceLine({ price: 50, color: 'rgba(255,255,255,0.14)', lineWidth: 1, lineStyle: LineStyle.Dashed, axisLabelVisible: false, title: '' })
    heights.push([pane, 92])
    pane += 1
  }

  chart.timeScale().fitContent()
  requestAnimationFrame(() => {
    if (!chart) return
    const panes = chart.panes()
    if (panes[0]) panes[0].setStretchFactor(props.height)
    for (const [index, height] of heights) {
      if (panes[index]) panes[index].setStretchFactor(height)
    }
    if (container.value && container.value.clientWidth < 620 && props.bars.length > 80) {
      chart.timeScale().setVisibleLogicalRange({
        from: props.bars.length - 80,
        to: props.bars.length + 1,
      })
    }
  })

  chart.subscribeCrosshairMove((param) => {
    if (!param.point || !param.time) {
      hoverTime.value = null
      return
    }
    hoverTime.value = timeKey(param.time)
  })
}

function destroy() {
  if (chart) {
    chart.remove()
    chart = null
  }
  mainSeries = null
  hoverTime.value = null
}

onMounted(async () => {
  await nextTick()
  build()
})

onBeforeUnmount(destroy)

watch(
  () => [
    props.bars,
    props.indicators,
    props.percentile,
    props.chartType,
    props.showVolume,
    props.showMacd,
    props.showRsi,
    props.showKdj,
  ],
  async () => {
    await nextTick()
    build()
  },
  { deep: true },
)
</script>

<template>
  <div class="chart-wrap">
    <div class="chart-legend">
      <span class="legend-title">{{ title }}</span>
      <span class="legend-unit">{{ unit }}</span>
      <template v-if="legendBar">
        <span v-if="chartType === 'candlestick'" class="legend-ohlc">
          <span>开 <b>{{ fmtPrice(legendBar.open) }}</b></span>
          <span>高 <b>{{ fmtPrice(legendBar.high) }}</b></span>
          <span>低 <b>{{ fmtPrice(legendBar.low) }}</b></span>
          <span>收 <b>{{ fmtPrice(legendBar.close) }}</b></span>
        </span>
        <span v-else class="legend-ohlc">
          <span>收 <b>{{ fmtPrice(legendBar.close) }}</b></span>
        </span>
        <span :class="tone(legendChange)">{{ fmtPct(legendChange) }}</span>
        <span v-if="showVolume" class="legend-ohlc">
          <span>量 <b>{{ fmtCompact(legendBar.volume) }}</b></span>
        </span>
        <span v-for="item in maLegend" :key="item.label" class="legend-ohlc" :style="{ color: item.value === null ? '#617184' : undefined }">
          <span>{{ item.label }} <b>{{ item.value === null ? '—' : fmtPrice(item.value) }}</b></span>
        </span>
        <span class="legend-ohlc" style="margin-left: auto">{{ formatChartDate(legendBar.time) }}</span>
      </template>
    </div>
    <div class="chart-plot">
      <div class="pane-labels">
        <span v-for="label in paneLabels" :key="label.text" :style="{ top: `${label.top}px` }">
          {{ label.text }}
        </span>
      </div>
      <div ref="container" class="chart-host" :style="{ height: `${paneHeights}px` }"></div>
    </div>
  </div>
</template>
