<script setup>
import { useToast } from '../composables/useToast'

const { toasts, remove } = useToast()
</script>

<template>
  <transition-group name="fade" tag="div" class="toast-stack">
    <button
      v-for="toast in toasts.items"
      :key="toast.id"
      class="toast"
      :class="toast.tone"
      @click="remove(toast.id)"
    >
      {{ toast.message }}
    </button>
  </transition-group>
</template>
