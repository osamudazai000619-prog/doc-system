// ============================================================
// 路由配置文件
// 4 个页面 + 根路径重定向 + 步骤条联动守卫
// ============================================================

import { createRouter, createWebHistory } from 'vue-router'

import UploadPage from '../views/UploadPage.vue'
import ExtractPage from '../views/ExtractPage.vue'
import ResultPage from '../views/ResultPage.vue'
import ExportPage from '../views/ExportPage.vue'
import SchemePage from '../views/SchemePage.vue'

import { useFileStore } from '@/stores/fileStore'
import { useResultStore } from '@/stores/resultStore'
import { ElMessage } from 'element-plus'

//路由
const routes = [
  { path: '/', redirect: '/upload' },
  { path: '/upload',  name: 'Upload',  component: UploadPage },
  { path: '/extract', name: 'Extract', component: ExtractPage },
  { path: '/result',  name: 'Result',  component: ResultPage },
  { path: '/export',  name: 'Export',  component: ExportPage },
  { path: '/schemes', name: 'Schemes', component: SchemePage },
  { path: '/:pathMatch(.*)*', redirect: '/upload' },
]

// -------- 创建 router 实例 --------
const router = createRouter({
  history: createWebHistory(),
  routes,
})


router.beforeEach((to, from, next) => {
  const fileStore = useFileStore()
  const resultStore = useResultStore()

  // -------- 访问 /extract 的校验 --------
  if (to.path === '/extract') {
    if (fileStore.validTargetFiles.length === 0) {
      ElMessage.warning('请先上传并解析至少 1 个目标文档')
      return next('/upload')
    }
  }

  // -------- 访问 /result 的校验 --------
  if (to.path === '/result') {
    if (resultStore.results.length === 0) {
      ElMessage.warning('请先发起提取')
      return next('/extract')
    }
  }

  // -------- 访问 /export 的校验 --------
  if (to.path === '/export') {
    if (resultStore.results.length === 0) {
      ElMessage.warning('请先完成提取并核对结果')
      return next('/result')
    }
    if (!resultStore.confirmed) {
      ElMessage.warning('请先在核对页确认结果')
      return next('/result')
    }
  }

  // 其他情况放行
  next()
})

export default router