import { reactive } from 'vue'

const state = reactive({ items: [] })
let nextId = 1

export function useToast() {
  function push(message, tone = 'info') {
    const id = nextId++
    state.items.push({ id, message, tone })
    window.setTimeout(() => remove(id), 3200)
  }
  function remove(id) {
    const index = state.items.findIndex((item) => item.id === id)
    if (index >= 0) state.items.splice(index, 1)
  }
  return { toasts: state, push, remove }
}
