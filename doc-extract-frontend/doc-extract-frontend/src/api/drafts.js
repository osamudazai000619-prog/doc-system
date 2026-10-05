// ============================================================
// drafts.js —— 草稿箱相关接口
// ============================================================
import request from './request'

export function fetchDrafts() {
  return request.get('/drafts')
}

export function saveDraft(data) {
  return request.post('/drafts', data)
}

export function fetchDraftDetail(id) {
  return request.get(`/drafts/${id}`)
}

export function deleteDraft(id) {
  return request.delete(`/drafts/${id}`)
}
