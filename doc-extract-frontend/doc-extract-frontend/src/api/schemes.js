// ============================================================
// schemes.js —— 方案模板相关接口
// ============================================================
import request from './request'

export function fetchSchemes() {
  return request.get('/schemes')
}

export function fetchSchemeDetail(id) {
  return request.get(`/schemes/${id}`)
}

export function saveScheme(data) {
  return request.post('/schemes', data)
}

export function deleteScheme(id) {
  return request.delete(`/schemes/${id}`)
}

export function fetchRecommendation(templateAssetId) {
  return request.get('/recommend', { params: { template_asset_id: templateAssetId } })
}
