// src/api/extract.js
import request from './request'

/**
 * 获取模板表头
 */
export function getTemplateHeaders() {
  return request.get('/extract/template-headers')
}
