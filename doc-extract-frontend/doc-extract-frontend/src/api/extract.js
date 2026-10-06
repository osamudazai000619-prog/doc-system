// src/api/extract.js
import request from './request'

/**
 * 获取模板表头
 */
export function getTemplateHeaders() {
  return request.get('/extract/template-headers')
}

/**
 * 字段自动匹配：模板字段与提取字段归一化精确同名者一一对应
 * @param {string[]} templateFields 模板字段列表
 * @param {string[]} extractFields 提取字段列表
 * @returns {{ mapping: Object, matched: number, total: number }}
 */
export function autoMatchFields(templateFields, extractFields) {
  return request.post('/extract/auto-match-fields', {
    template_fields: templateFields,
    extract_fields: extractFields,
  })
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
