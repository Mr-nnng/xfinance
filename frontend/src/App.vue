<script setup>
import AppHeader from './components/AppHeader.vue'
import ToastStack from './components/ToastStack.vue'
</script>

<template>
  <div class="app-shell">
    <AppHeader />
    <main>
      <router-view v-slot="{ Component }">
        <transition name="page" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
    <footer class="app-footer">
      <span>xfinance · 个人本地工具</span>
      <a href="https://www.tradingview.com/" target="_blank" rel="noreferrer">
        图表由 TradingView Lightweight Charts 驱动
      </a>
    </footer>
    <ToastStack />
  </div>
</template>
