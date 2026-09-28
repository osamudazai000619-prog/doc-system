import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],

  // ★ 路径别名：让 '@/xxx' 指向 'src/xxx'
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },

  // ★ 开发服务器配置
  server: {
    port: 5173,
    // 代理：把 /api/** 转发到后端
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',  // ★ 后端的真实地址
        changeOrigin: true,
        // 如果后端接口不带 /api 前缀，用下面这行把前缀去掉：
        // rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})