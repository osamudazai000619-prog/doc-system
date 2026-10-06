import { createApp } from 'vue'
import { createPinia } from 'pinia'
import piniaPluginPersistedstate from 'pinia-plugin-persistedstate'  // ★ 新增
import router from './router'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'   // ★ Element Plus 深色主题变量
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import App from './App.vue'
import './style.css'                                  // ★ 必须最后导入，才能覆盖组件库默认样式

// 全站启用深色主题（Element Plus 靠 html.dark 这个类切换）
document.documentElement.classList.add('dark')

const pinia = createPinia()
pinia.use(piniaPluginPersistedstate)  // ★ 挂载插件

const app = createApp(App)
app.use(pinia)
app.use(router)
app.use(ElementPlus)

for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

app.mount('#app')