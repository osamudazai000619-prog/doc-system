// ============================================================
// history.js —— 历史任务相关接口
// ============================================================
import request from './request'

export function fetchHistoryList(page = 1, size = 20) {
  return request.get('/history', { params: { page, size } })
}

export function fetchHistoryDetail(taskId) {
  return request.get(`/history/${taskId}`)
}
