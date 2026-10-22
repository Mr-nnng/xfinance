import { createRouter, createWebHistory } from 'vue-router'
import OverviewView from './views/OverviewView.vue'

const routes = [
  { path: '/', name: 'overview', component: OverviewView },
  {
    path: '/s/:symbol',
    name: 'instrument',
    component: () => import('./views/InstrumentView.vue'),
  },
  {
    path: '/i/:id',
    name: 'custom-index',
    component: () => import('./views/CustomIndexView.vue'),
  },
  {
    path: '/tools',
    name: 'tools',
    component: () => import('./views/ToolsView.vue'),
  },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export default createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0 }
  },
})
