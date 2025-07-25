import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import solidPlugin from 'vite-plugin-solid'

// Читаем версию из package.json
const currentDir = process.cwd()
const packageJsonPath = resolve(currentDir, 'package.json')
const packageJson = JSON.parse(readFileSync(packageJsonPath, 'utf-8'))
const version = packageJson.version

// Конфигурация для разных окружений
const isProd = process.env.NODE_ENV === 'production'

export default defineConfig({
  plugins: [solidPlugin()],

  // Определяем переменные окружения
  define: {
    __APP_VERSION__: JSON.stringify(version)
  },

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
