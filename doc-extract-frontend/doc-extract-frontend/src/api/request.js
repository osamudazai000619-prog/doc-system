// Mock
// 默认启用本地 Mock，无需后端即可跑通全流程。
// 切换到真实后端时：
// 注释掉下面的 import { createMockAdapter } 那一行
// 注释掉 "启用 Mock" 区块的 3 行代码
// 在 vite.config.js 里配置 proxy 指向后端地址
import axios from 'axios'
import { ElMessage } from 'element-plus'

// ★ Mock 适配器（后端好了就删掉这两行）
// import { createMockAdapter } from './mockUpload'

// ------------------------------------------------------------
// baseURL
// ------------------------------------------------------------
const BASE_URL = '/api'

// ------------------------------------------------------------
// 创建 axios 实例
// ------------------------------------------------------------
const request = axios.create({
  baseURL: BASE_URL,
  // 提取接口含「计划+提取+兜底重试」多次 LLM 调用（单次后端上限 120s），
  // 前端超时需大于多次调用的串行总耗时
  timeout: 300000,
})

// ------------------------------------------------------------
// 启用 Mock（后端好了注释掉下面 3 行）
// ------------------------------------------------------------
// axios 1.x 后期版本中，defaults.adapter 可能是字符串（如 'xhr'）
// 用 axios.getAdapter(...) 可以自动转成真正的 adapter 函数
// const fallbackAdapter = axios.getAdapter(axios.defaults.adapter)
// request.defaults.adapter = createMockAdapter(fallbackAdapter)
// // ------------------------------------------------------------

// ------------------------------------------------------------
// 请求拦截器
// ------------------------------------------------------------
request.interceptors.request.use(
  (config) => {
    console.log(
      `[请求] ${config.method?.toUpperCase()} ${config.url}`,
      config.data || config.params || ''
    )
    return config
  },
  (error) => {
    console.error('[请求错误]', error)
    return Promise.reject(error)
  }
)

// ------------------------------------------------------------
// 响应拦截器
// ------------------------------------------------------------
request.interceptors.response.use(
  // 情况 A：HTTP 2xx
  (response) => {
    // 目前约定后端直接返回业务数据，不做 { code, message } 包裹
    return response.data
  },

  // 情况 B：HTTP 非 2xx
  (error) => {
    let message = '请求失败'

    if (error.response) {
      const status = error.response.status
      const map = {
        400: '请求参数错误 (400)',
        401: '未授权，请重新登录 (401)',
        403: '拒绝访问 (403)',
        404: '接口不存在 (404)',
        422: '参数校验失败，请检查输入是否符合要求（如字段数量是否超过上限）',
        500: '服务器错误 (500)',
        502: '网关错误 (502)',
        503: '服务不可用 (503)',
      }
      message = map[status] || `请求失败 (${status})`
    } else if (error.request) {
      message = '网络异常，请检查后端服务是否启动'
    } else {
      message = error.message || '请求失败'
    }

    ElMessage.error(message)
    return Promise.reject(error)
  }
)

export default request