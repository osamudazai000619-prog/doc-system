// src/api/extract.js
import request from './request'

/**
 * 获取模板表头
 */
export function getTemplateHeaders() {
  return request.get('/extract/template-headers')
}

/**
 * 导出溯源报告 PDF
 * 入参为提取结果列表（与 /extract 返回结构一致），返回 Blob
 */
export function exportTraceReport(results) {
  return request.post('/export/trace-report', results, {
    responseType: 'blob',
  })
}
