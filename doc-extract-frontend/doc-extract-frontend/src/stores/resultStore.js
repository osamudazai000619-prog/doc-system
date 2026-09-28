// ============================================================
// resultStore.js —— 提取结果相关的状态管理
// 管理：
//   1. 完整的提取结果
//   2. 本次使用的提示词和字段（快照）
//   3. 提取中的 loading 状态
//   4. 用户是否已确认 / 是否有未保存的修改
// ============================================================

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useResultStore = defineStore('result', () => {

  // ============================================================
  // 一、状态
  // ============================================================

  /**
   * 提取结果
   * 结构：
   * [
   *   {
   *     source_file: 'a.txt',
   *     extracted_tables: [
   *       {
   *         table_category: '表1',
   *         records: [
   *           { '项目名称': 'XX', '负责人': '张三', ... },
   *           ...
   *         ]
   *       },
   *       ...
   *     ]
   *   },
   *   ...
   * ]
   */
  const results = ref([])

  /**
   * 是否正在提取
   */
  const extracting = ref(false)

  /**
   * 本次使用的提示词（快照）
   */
  const prompt = ref('')

  /**
   * 本次使用的字段（快照，只读用）
   */
  const fields = ref([])

  /**
   * 用户是否已确认（点了"确认无误，进入导出"）
   */
  const confirmed = ref(false)

  /**
   * 是否有未保存的修改
   * 用户编辑任何单元格后置为 true；重新提取或进入导出时置为 false
   */
  const dirty = ref(false)

  /**
   * 结果是否为空
   */
  const isEmpty = computed(() => results.value.length === 0)

  /**
   * 总记录数（跨文件、跨表）
   */
  const totalRecords = computed(() => {
    let sum = 0
    results.value.forEach((file) => {
      (file.extracted_tables || []).forEach((table) => {
        sum += (table.records || []).length
      })
    })
    return sum
  })

  /**
   * 总文件数
   */
  const totalFiles = computed(() => results.value.length)

  /**
   * 所有字段名（去重，用于表头）
   * 从结果里递归收集
   */
  const allFieldNames = computed(() => {
    const set = new Set()
    results.value.forEach((file) => {
      (file.extracted_tables || []).forEach((table) => {
        (table.records || []).forEach((record) => {
          Object.keys(record).forEach((k) => set.add(k))
        })
      })
    })
    return [...set]
  })

  /**
   * 异常字段数量统计
   * 统计值为"未找到"或"PARSE_ERROR"的单元格数
   */
  const abnormalCount = computed(() => {
    let count = 0
    results.value.forEach((file) => {
      (file.extracted_tables || []).forEach((table) => {
        (table.records || []).forEach((record) => {
          Object.values(record).forEach((val) => {
            const s = String(val || '')
            if (s === '未找到' || s === 'PARSE_ERROR') count++
          })
        })
      })
    })
    return count
  })



  function setResults(data) {
    results.value = Array.isArray(data) ? data : []
    confirmed.value = false
    dirty.value = false
  }

  /**
   * 修改某个单元格的值
   * @param {number} fileIndex   - results 数组的索引
   * @param {number} tableIndex  - extracted_tables 数组的索引
   * @param {number} recordIndex - records 数组的索引
   * @param {string} field       - 字段名
   * @param {any}    value       - 新值
   */
  function updateRecord(fileIndex, tableIndex, recordIndex, field, value) {
    const file = results.value[fileIndex]
    if (!file) return

    const table = (file.extracted_tables || [])[tableIndex]
    if (!table) return

    const record = (table.records || [])[recordIndex]
    if (!record) return

    record[field] = value
    dirty.value = true
  }


  function setPrompt(p) {
    prompt.value = p || ''
  }


  function setFields(f) {
    fields.value = Array.isArray(f) ? [...f] : []
  }


  function setConfirmed(val) {
    confirmed.value = !!val
    if (val) dirty.value = false
  }


  function setDirty(val) {
    dirty.value = !!val
  }

  function clearAll() {
    results.value = []
    extracting.value = false
    prompt.value = ''
    fields.value = []
    confirmed.value = false
    dirty.value = false
  }

  return {
    // state
    results,
    extracting,
    prompt,
    fields,
    confirmed,
    dirty,
    // getters
    isEmpty,
    totalRecords,
    totalFiles,
    allFieldNames,
    abnormalCount,
    // actions
    setResults,
    updateRecord,
    setPrompt,
    setFields,
    setConfirmed,
    setDirty,
    clearAll,
  }
})