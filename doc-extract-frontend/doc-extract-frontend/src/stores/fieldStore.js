// ============================================================
// fieldStore.js —— 字段相关的状态管理
// ============================================================

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

// ============================================================
// 8 组预设字段
// ============================================================
export const PRESET_GROUPS = [
  { key: 'name',         label: '名称类',     icon: 'Postcard',       fields: ['项目名称', '单位名称', '机构名称', '职位名称'] },
  { key: 'organization', label: '单位类',     icon: 'OfficeBuilding', fields: ['主办单位', '承办单位', '协办单位'] },
  { key: 'person',       label: '人员类',     icon: 'User',           fields: ['姓名', '负责人', '联系人', '申请人', '法定代表人'] },
  { key: 'date',         label: '日期类',     icon: 'Calendar',       fields: ['日期', '报名截止日期', '开始日期', '结束日期', '发布时间'] },
  { key: 'amount',       label: '金额类',     icon: 'Money',          fields: ['金额', '预算金额', '合同金额', '报价', '单价'] },
  { key: 'address',      label: '地址类',     icon: 'Location',       fields: ['地址', '通讯地址', '办公地址', '注册地址'] },
  { key: 'contact',      label: '联系方式类', icon: 'Phone',          fields: ['联系电话', '手机号码', '邮箱', '传真'] },
  { key: 'text',         label: '简短文本类', icon: 'Document',       fields: ['项目简介', '备注', '说明', '职位描述'] },
]

// ============================================================
// Store
// ============================================================
export const useFieldStore = defineStore('field', () => {

  const fields = ref([])
  const maxFields = 10

  const fieldCount = computed(() => fields.value.length)
  const isFull = computed(() => fields.value.length >= maxFields)
  const remaining = computed(() => maxFields - fields.value.length)

  function hasField(name) {
    return fields.value.includes(name)
  }

  function addField(name) {
    const trimmed = (name || '').trim()
    if (!trimmed) return { ok: false, msg: '字段名不能为空' }
    if (fields.value.includes(trimmed)) return { ok: false, msg: `字段 "${trimmed}" 已存在` }
    if (fields.value.length >= maxFields) return { ok: false, msg: `最多只能设置 ${maxFields} 个字段` }
    fields.value.push(trimmed)
    return { ok: true, msg: '' }
  }

  function removeField(name) {
    fields.value = fields.value.filter((f) => f !== name)
  }

  function setFields(arr) {
    if (!Array.isArray(arr)) return
    const cleaned = [...new Set(arr.map((s) => (s || '').trim()).filter(Boolean))]
    fields.value = cleaned.slice(0, maxFields)
  }

  function clearFields() {
    fields.value = []
  }

  return {
    fields,
    maxFields,
    fieldCount,
    isFull,
    remaining,
    hasField,
    addField,
    removeField,
    setFields,
    clearFields,
  }
})