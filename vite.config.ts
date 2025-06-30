import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import solidPlugin from 'vite-plugin-solid'

// Конфигурация для разных окружений
const isProd = process.env.NODE_ENV === 'production'

export default defineConfig({
  plugins: [solidPlugin()],

  build: {
    target: 'esnext',
    outDir: 'dist',
    assetsDir: 'assets',
    emptyOutDir: true,
    sourcemap: !isProd,
    minify: isProd ? 'terser' : false,
    cssMinify: isProd ? 'lightningcss' : false,

    // Оптимизация сборки
    cssCodeSplit: true,
    assetsInlineLimit: 4096,
    chunkSizeWarningLimit: 500
  },

  // Настройка dev сервера
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/graphql': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  },

  // Оптимизация зависимостей
  optimizeDeps: {
    include: ['solid-js'],
    exclude: []
  },

  // Настройка алиасов для путей
  resolve: {
    alias: {
      '~': resolve(__dirname, 'panel')
    }
  }
})
