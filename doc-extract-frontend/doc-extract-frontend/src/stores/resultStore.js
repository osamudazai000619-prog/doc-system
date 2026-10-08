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

// ------------------------------------------------------------
// 单元格统一为 { value, source, context, risk } 结构。
// 后端返回的 segments（逐段溯源）仅在拆行时用于回填各行来源，拆行后即剥离：
// 若随每行保留，2542 行 × 2542 段的引用会被 deep watch / JSON.stringify
// 放大成千万级对象遍历，直接卡死页面。兼容 dict 单元格与旧纯字符串两种形态。
// ------------------------------------------------------------
export function cellValue(cell) {
  if (cell && typeof cell === 'object') return String(cell.value ?? '')
  return String(cell ?? '')
}

export function normalizeCell(cell) {
  if (cell && typeof cell === 'object') {
    return {
      value: cell.value ?? '',
      source: cell.source ?? null,
      context: cell.context ?? null,
      segments: Array.isArray(cell.segments) ? cell.segments : null,
      risk: Array.isArray(cell.risk) ? cell.risk : [],
    }
  }
  return {
    value: cell ?? '',
    source: null,
    context: null,
    segments: null,
    risk: [],
  }
}

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
   * 本次提取落库的任务历史 id（后端提取响应带回；导出时回传用于产物关联）
   */
  const taskId = ref('')

  /**
   * 当前选中的方案 id（一阶段选择，提取时随 payload 上送；空为未选）
   */
  const schemeId = ref(null)

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
            const s = cellValue(val)
            if (s === '未找到' || s === 'PARSE_ERROR') count++
          })
        })
      })
    })
    return count
  })



  function normalizeRecords(raw) {
    // records 统一为「记录对象数组」，并把每个单元格归一化为带溯源的结构
    const arr = Array.isArray(raw)
      ? raw.filter((r) => r && typeof r === 'object')
      : (raw && typeof raw === 'object') ? [raw] : []
    return arr.map((rec) => {
      const out = {}
      Object.keys(rec).forEach((k) => { out[k] = normalizeCell(rec[k]) })
      return out
    })
  }

  /**
   * 分号列表拆分：当一条记录的所有字段都是等长的分号分隔列表
   * （LLM 把多实体文档挤进单条记录的常见形态），拆成 N 条记录。
   * 字段值数量不一致时按最大长度拆，缺失位补"未找到"；
   * 只有一个分号字段而其余为单值时，单值广播到每一行。
   */
  function stripSegments(recs) {
    return recs.map((rec) => {
      const out = {}
      Object.keys(rec).forEach((k) => {
        const c = rec[k] || {}
        out[k] = {
          value: c.value ?? '',
          source: c.source ?? null,
          context: c.context ?? null,
          risk: Array.isArray(c.risk) ? c.risk : [],
        }
      })
      return out
    })
  }

  function splitSemicolonRecords(records) {
    if (records.length !== 1) return stripSegments(records)
    const record = records[0]
    const keys = Object.keys(record)
    if (keys.length === 0) return stripSegments(records)

    const splitByKey = {}
    let maxLen = 1
    keys.forEach((k) => {
      const parts = cellValue(record[k])
        .split(/[；;]/)
        .map((s) => s.trim())
      splitByKey[k] = parts
      if (parts.length > maxLen) maxLen = parts.length
    })
    // 没有任何字段含分号列表，原样返回（仍剥离 segments）
    if (maxLen <= 1) return stripSegments(records)

    // 拆分后每段克隆原单元格并替换 value；若后端提供了逐段溯源 segments，
    // 第 i 行取 segments[i] 的 source/context，避免所有行共用首段来源造成错指
    const rows = []
    for (let i = 0; i < maxLen; i++) {
      const row = {}
      keys.forEach((k) => {
        const base = normalizeCell(record[k])
        const parts = splitByKey[k]
        let seg
        if (parts.length === 1) seg = parts[0]          // 单值字段广播
        else if (i < parts.length) seg = parts[i]
        else seg = '未找到'                              // 长度不齐的缺失位
        const segTrace = Array.isArray(base.segments) ? base.segments[i] : null
        row[k] = {
          value: seg,
          source: segTrace ? (segTrace.source ?? null) : base.source,
          context: segTrace ? (segTrace.context ?? null) : base.context,
          risk: Array.isArray(base.risk) ? base.risk : [],
        }
      })
      rows.push(row)
    }
    return rows
  }

  function setResults(data) {
    const list = Array.isArray(data) ? data : []
    results.value = list.map((file) => ({
      source_file: file?.source_file || 'unknown',
      extracted_tables: (Array.isArray(file?.extracted_tables) ? file.extracted_tables : []).map(
        (table) => ({
          table_category: table?.table_category || '',
          records: splitSemicolonRecords(normalizeRecords(table?.records)),
        })
      ),
    }))
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

    // 编辑只改 value，保留原溯源（source/context/risk），不带回 segments
    const prev = normalizeCell(record[field])
    record[field] = {
      value: String(value ?? ''),
      source: prev.source,
      context: prev.context,
      risk: prev.risk,
    }
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


  function setTaskId(id) {
    taskId.value = id ? String(id) : ''
  }


  function setSchemeId(id) {
    schemeId.value = id || null
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
    taskId.value = ''
    schemeId.value = null
  }

  return {
    // state
    results,
    extracting,
    prompt,
    fields,
    confirmed,
    dirty,
    taskId,
    schemeId,
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
    setTaskId,
    setSchemeId,
    setDirty,
    clearAll,
  }
})