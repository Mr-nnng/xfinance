import { loadEnv } from 'vite'

/**
 * Dev-only bridge to FastAPI.
 *
 * Vite serves the Vue app; this plugin forwards /api to the backend so the
 * browser sees one origin and no CORS. Production serves the built assets
 * from FastAPI itself.
 */
export default function fastapiPlugin(options = {}) {
  let target = options.target || 'http://127.0.0.1:28473'

  return {
    name: 'vite-plugin-fastapi',
    enforce: 'pre',
    config(_config, { mode }) {
      const env = loadEnv(mode, process.cwd(), '')
      target =
        options.target ||
        process.env.FASTAPI_URL ||
        process.env.VITE_FASTAPI_URL ||
        env.VITE_FASTAPI_URL ||
        target
      return {
        server: {
          proxy: {
            '/api': {
              target,
              changeOrigin: true,
              ws: false,
            },
          },
        },
        define: {
          __FASTAPI_TARGET__: JSON.stringify(target),
        },
      }
    },
    configureServer(server) {
      server.config.logger.info(`  FastAPI proxy: /api -> ${target}`)
    },
  }
}
