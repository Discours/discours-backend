import { resolve } from 'path'
import { defineConfig } from 'vite'
import solidPlugin from 'vite-plugin-solid'

// Конфигурация для разных окружений
const isProd = process.env.NODE_ENV === 'production'

export default defineConfig({
  plugins: [solidPlugin()],
  base: '/',

  build: {
    target: 'esnext',
    outDir: 'dist',
    minify: isProd,
    sourcemap: !isProd,

    rollupOptions: {
      input: {
        main: resolve(__dirname, 'client/index.tsx')
      },

      output: {
        // Настройка выходных файлов
        entryFileNames: '[name].js',
        chunkFileNames: 'chunks/[name].[hash].js',
        assetFileNames: 'assets/[name].[hash][extname]',

        // Настройка разделения кода
        manualChunks: {
          vendor: ['solid-js', '@solidjs/router'],
          graphql: ['./client/graphql.ts'],
          auth: ['./client/auth.ts']
        }
      }
    },

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
    include: ['solid-js', '@solidjs/router'],
    exclude: []
  },

  // Настройка алиасов для путей
  resolve: {
    alias: {
      '@': resolve(__dirname, 'client')
    }
  }
})
