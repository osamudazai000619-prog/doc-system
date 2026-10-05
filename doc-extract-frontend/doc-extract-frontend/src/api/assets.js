// ============================================================
// assets.js —— 文件资产库相关接口
// ============================================================
import request from './request'

export function fetchAssets(role = 'template') {
  return request.get('/assets', { params: { role } })
}

export function loadAsset(assetId) {
  return request.post(`/assets/${assetId}/load`)
}
