import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// https://vitejs.dev/config/
export default defineConfig({
  server: {
    host: '0.0.0.0',
    fs: {
      // 
      allow: ['/config/GivTCP/allsettings.json'],
    },
  },
  plugins: [
    vue(),
  ],
  // Relative asset paths, so the build works at any base path (direct on 8099/8098 or under HA ingress)
  base: './',
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    }
  }
})
