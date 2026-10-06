<!-- ============================================================
     ResultPage.vue —— 提取结果核对（5.4 大表格优化）
     功能：
       1. 文件卡片折叠/展开
       2. 顶部"全部展开/全部折叠"
       3. 双击单元格可编辑
       4. 回车/失焦保存，Esc 取消
       5. 已修改单元格黄色背景
       6. 未找到 / PARSE_ERROR 标红
       7. 确认后跳转到 /export
     ============================================================ -->

<template>
  <div class="result-page">

    <!-- ==================================================
         顶部说明卡
         ================================================== -->
    <el-card class="intro-card" shadow="never">
      <div class="intro-content">
        <el-icon class="intro-icon"><DocumentChecked /></el-icon>
        <div class="intro-text">
          <div class="intro-title">提取结果核对</div>
          <div class="intro-desc">
            请核对以下提取结果。<strong>双击</strong>任意单元格可编辑，按
            <kbd>Enter</kbd> 保存，按 <kbd>Esc</kbd> 取消。
            标红的"未找到"或"PARSE_ERROR"表示需要人工确认。
          </div>
          <div class="stats">
            <el-tag type="info" size="small" round>
              共 {{ resultStore.totalFiles }} 个文件
            </el-tag>
            <el-tag type="success" size="small" round>
              {{ resultStore.totalRecords }} 条记录
            </el-tag>
            <el-tag
              v-if="resultStore.abnormalCount > 0"
              type="danger"
              size="small"
              round
            >
              {{ resultStore.abnormalCount }} 处异常待确认
            </el-tag>
            <el-tag v-else type="success" size="small" round>
              无异常
            </el-tag>
            <el-tag
              v-if="modifiedCount > 0"
              type="warning"
              size="small"
              round
            >
              已修改 {{ modifiedCount }} 处
            </el-tag>
          </div>
        </div>
      </div>
    </el-card>

    <!-- ==================================================
         结果为空
         ================================================== -->
    <el-card v-if="resultStore.isEmpty" shadow="never">
      <el-empty description="暂无提取结果，请返回上一步发起提取" :image-size="120">
        <el-button type="primary" @click="goExtract">
          返回设置字段
        </el-button>
      </el-empty>
    </el-card>

    <!-- ==================================================
         结果列表
         ================================================== -->
    <template v-else>
      <!-- 顶部操作栏：全部展开 / 全部折叠 -->
      <el-card class="toolbar-card" shadow="never">
        <div class="toolbar">
          <div class="toolbar-left">
            <el-icon><Operation /></el-icon>
            <span>共 {{ resultStore.totalFiles }} 个文件</span>
          </div>
          <div class="toolbar-right">
            <el-button size="small" @click="expandAll">
              <el-icon><Expand /></el-icon>
              <span>全部展开</span>
            </el-button>
            <el-button size="small" @click="collapseAll">
              <el-icon><Fold /></el-icon>
              <span>全部折叠</span>
            </el-button>
            <el-button
              type="success"
              size="small"
              :loading="exportingTrace"
              :disabled="resultStore.isEmpty"
              @click="handleExportTrace"
            >
              <el-icon><Download /></el-icon>
              <span>导出溯源报告</span>
            </el-button>
          </div>
        </div>
      </el-card>

      <!-- 文件卡片列表 -->
      <el-card
        v-for="(file, fileIdx) in resultStore.results"
        :key="fileIdx"
        class="file-card"
        shadow="never"
      >
        <!-- 文件标题（可点击折叠） -->
        <template #header>
          <div class="file-header" @click="toggleFile(fileIdx)">
            <div class="file-title">
              <el-icon class="expand-icon" :class="{ 'is-expanded': isExpanded(fileIdx) }">
                <ArrowRight />
              </el-icon>
              <el-icon class="file-icon"><Document /></el-icon>
              <span class="file-name">{{ file.source_file }}</span>
              <el-tag size="small" type="info" round>
                {{ countFileRecords(file) }} 条记录
              </el-tag>
              <el-tag
                v-if="countFileAbnormal(file) > 0"
                size="small"
                type="danger"
                round
              >
                {{ countFileAbnormal(file) }} 处异常
              </el-tag>
            </div>
            <div class="file-actions">
              <span class="expand-hint">
                {{ isExpanded(fileIdx) ? '点击折叠' : '点击展开' }}
              </span>
            </div>
          </div>
        </template>

        <!-- 折叠内容 -->
        <div v-show="isExpanded(fileIdx)">
          <div class="table-list">
            <div
              v-for="(table, tableIdx) in file.extracted_tables"
              :key="tableIdx"
              class="table-block"
            >
              <!-- 表标题 -->
              <div class="table-header">
                <el-icon><Grid /></el-icon>
                <span class="table-name">
                  {{ table.table_category || `表${tableIdx + 1}` }}
                </span>
                <el-tag size="small" type="info" round>
                  {{ (table.records || []).length }} 条
                </el-tag>
              </div>

              <!-- 表格 -->
              <el-table
                v-if="table.records && table.records.length > 0"
                :data="table.records"
                stripe
                border
                size="small"
                style="width: 100%"
                :header-cell-style="{ background: '#f5f7fa', color: '#303133', fontWeight: 600 }"
                :cell-class-name="() => 'editable-cell'"
              >
                <!-- 序号列 -->
                <el-table-column
                  type="index"
                  label="序号"
                  width="60"
                  align="center"
                />

                <!-- 动态字段列 -->
                <el-table-column
                  v-for="field in getAllFields(table)"
                  :key="field"
                  :label="field"
                  :prop="field"
                  min-width="120"
                  show-overflow-tooltip
                >
                  <template #default="{ row, $index }">
                    <div
                      class="cell-wrapper"
                      :class="{
                        'cell-abnormal-bg': isAbnormal(row[field]) && !isEditing(fileIdx, tableIdx, $index, field),
                        'cell-modified-bg': isModified(fileIdx, tableIdx, $index, field),
                      }"
                      @dblclick="startEdit(fileIdx, tableIdx, $index, field, cellValue(row[field]))"
                    >
                      <!-- 编辑态 -->
                      <el-input
                        v-if="isEditing(fileIdx, tableIdx, $index, field)"
                        ref="editInputRef"
                        v-model="editValue"
                        size="small"
                        @blur="commitEdit(fileIdx, tableIdx, $index, field)"
                        @keyup.enter="commitEdit(fileIdx, tableIdx, $index, field)"
                        @keyup.esc="cancelEdit"
                      />
                      <!-- 只读态 -->
                      <span
                        v-else
                        :class="['cell-text', { 'cell-abnormal': isAbnormal(row[field]) }]"
                        :title="cellValue(row[field])"
                      >
                        {{ cellValue(row[field]) }}
                      </span>
                    </div>
                  </template>
                </el-table-column>

                <!-- 溯源信息列 -->
                <el-table-column label="溯源信息" min-width="280" align="left">
                  <template #default="{ row }">
                    <div class="trace-cell">
                      <div
                        v-for="field in getAllFields(table)"
                        :key="field"
                        class="trace-row"
                      >
                        <span class="trace-field">{{ field }}</span>
                        <div class="trace-body">
                          <!-- 来源段落：悬停显示原文片段（≤100 字） -->
                          <el-tooltip
                            v-if="contextText(row[field])"
                            :content="contextText(row[field])"
                            placement="top"
                            :show-after="300"
                          >
                            <span
                              class="trace-source"
                              :class="{ 'trace-source-empty': !srcOf(row[field]) }"
                            >{{ sourceText(row[field]) }}</span>
                          </el-tooltip>
                          <span
                            v-else
                            class="trace-source trace-source-empty"
                          >{{ sourceText(row[field]) }}</span>
                          <!-- 置信度进度条（<50% 标红） + 风险标签 -->
                          <div class="trace-meta">
                            <el-progress
                              v-if="confPct(row[field]) !== null"
                              :percentage="confPct(row[field])"
                              :stroke-width="6"
                              :status="confPct(row[field]) < 50 ? 'exception' : ''"
                            />
                            <el-tag
                              v-for="r in riskList(row[field])"
                              :key="r.key"
                              size="small"
                              effect="dark"
                              :class="['risk-tag', `risk-tag-${r.key}`]"
                            >{{ r.label }}</el-tag>
                          </div>
                        </div>
                      </div>
                      <span v-if="getAllFields(table).length === 0" class="trace-empty">—</span>
                    </div>
                  </template>
                </el-table-column>
              </el-table>

              <!-- 表为空 -->
              <el-empty
                v-else
                description="该表无记录"
                :image-size="60"
              />
            </div>

            <!-- 文件下没有表 -->
            <el-empty
              v-if="!file.extracted_tables || file.extracted_tables.length === 0"
              description="该文件无提取结果"
              :image-size="60"
            />
          </div>
        </div>
      </el-card>
    </template>

    <!-- ==================================================
         底部操作栏
         ================================================== -->
    <div class="action-bar">
      <el-button size="large" @click="goExtract">
        <el-icon><ArrowLeft /></el-icon>
        <span>上一步：设置字段</span>
      </el-button>

      <el-button
        type="primary"
        size="large"
        :disabled="resultStore.isEmpty"
        @click="handleNext"
      >
        <span>确认无误，下一步</span>
        <el-icon><ArrowRight /></el-icon>
      </el-button>
    </div>

  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useResultStore, cellValue } from '@/stores/resultStore'
import { exportTraceReport } from '@/api/extract'

// ============================================================
// 依赖
// ============================================================
const router = useRouter()
const resultStore = useResultStore()

// ============================================================
// 溯源信息展示辅助（单元格为 {value,source,context,confidence,risk}）
// ============================================================
const RISK_LABELS = {
  not_found: '未找到',
  low_confidence: '低置信度',
  conflict: '冲突',
  no_source: '无来源',
}

function srcOf(cell) {
  return (cell && cell.source) || null
}
function sourceText(cell) {
  const s = srcOf(cell)
  if (!s) return '无来源'
  const parts = []
  if (s.para_id != null) parts.push(`段落 #${s.para_id}`)
  if (s.page != null) parts.push(`第 ${s.page} 页`)
  if (s.start != null && s.end != null) parts.push(`偏移 ${s.start}-${s.end}`)
  return parts.length ? parts.join('，') : '无来源'
}
function contextText(cell) {
  const c = (cell && cell.context) || ''
  if (!c) return ''
  return c.length > 100 ? c.slice(0, 100) + '…' : c
}
function confPct(cell) {
  const c = cell && cell.confidence
  return typeof c === 'number' ? Math.round(c * 100) : null
}
function riskList(cell) {
  const r = (cell && cell.risk) || []
  return r.filter((k) => RISK_LABELS[k]).map((k) => ({ key: k, label: RISK_LABELS[k] }))
}

// 导出溯源报告
const exportingTrace = ref(false)
async function handleExportTrace() {
  if (exportingTrace.value || resultStore.isEmpty) return
  exportingTrace.value = true
  try {
    const blob = await exportTraceReport(resultStore.results)
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.setAttribute('download', `溯源报告_${Date.now()}.pdf`)
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(url)
    ElMessage.success('溯源报告已导出')
  } catch (err) {
    console.error('[导出溯源报告失败]', err)
    ElMessage.error('导出溯源报告失败')
  } finally {
    exportingTrace.value = false
  }
}

// ============================================================
// 折叠状态：用 Set 存已展开的文件索引
// ============================================================
const expandedFiles = ref(new Set())

// 首次渲染时，默认展开第一个文件
if (resultStore.results.length > 0) {
  expandedFiles.value.add(0)
}

function isExpanded(fileIdx) {
  return expandedFiles.value.has(fileIdx)
}

function toggleFile(fileIdx) {
  const set = new Set(expandedFiles.value)
  if (set.has(fileIdx)) {
    set.delete(fileIdx)
  } else {
    set.add(fileIdx)
  }
  expandedFiles.value = set
}

function expandAll() {
  const set = new Set()
  resultStore.results.forEach((_, idx) => set.add(idx))
  expandedFiles.value = set
}

function collapseAll() {
  expandedFiles.value = new Set()
}

// ============================================================
// 编辑相关状态
// ============================================================
const editingKey = ref(null)
const editValue = ref('')
const editInputRef = ref(null)
const modifiedKeys = ref(new Set())
const modifiedCount = computed(() => modifiedKeys.value.size)

// ============================================================
// 工具函数
// ============================================================
function getAllFields(table) {
  const set = new Set()
  ;(table.records || []).forEach((record) => {
    Object.keys(record).forEach((k) => set.add(k))
  })
  return [...set]
}

function isAbnormal(cell) {
  const s = cellValue(cell)
  return s === '未找到' || s === 'PARSE_ERROR'
}

function countFileRecords(file) {
  let sum = 0
  ;(file.extracted_tables || []).forEach((t) => {
    sum += (t.records || []).length
  })
  return sum
}

function countFileAbnormal(file) {
  let count = 0
  ;(file.extracted_tables || []).forEach((t) => {
    (t.records || []).forEach((record) => {
      Object.values(record).forEach((v) => {
        if (isAbnormal(v)) count++
      })
    })
  })
  return count
}

function makeCellKey(fileIdx, tableIdx, recordIdx, field) {
  return `${fileIdx}-${tableIdx}-${recordIdx}-${field}`
}

function isEditing(fileIdx, tableIdx, recordIdx, field) {
  return editingKey.value === makeCellKey(fileIdx, tableIdx, recordIdx, field)
}

function isModified(fileIdx, tableIdx, recordIdx, field) {
  return modifiedKeys.value.has(makeCellKey(fileIdx, tableIdx, recordIdx, field))
}

// ============================================================
// 编辑操作
// ============================================================
async function startEdit(fileIdx, tableIdx, recordIdx, field, currentValue) {
  if (editingKey.value && editingKey.value !== makeCellKey(fileIdx, tableIdx, recordIdx, field)) {
    editingKey.value = null
  }

  editingKey.value = makeCellKey(fileIdx, tableIdx, recordIdx, field)
  editValue.value = String(currentValue ?? '')

  await nextTick()
  const inputRef = Array.isArray(editInputRef.value) ? editInputRef.value[0] : editInputRef.value
  if (inputRef?.focus) {
    inputRef.focus()
  }
}

function commitEdit(fileIdx, tableIdx, recordIdx, field) {
  if (!isEditing(fileIdx, tableIdx, recordIdx, field)) return

  const newValue = editValue.value
  const oldValue = resultStore.results[fileIdx]
    ?.extracted_tables?.[tableIdx]
    ?.records?.[recordIdx]?.[field]

  if (cellValue(oldValue) === String(newValue)) {
    editingKey.value = null
    return
  }

  resultStore.updateRecord(fileIdx, tableIdx, recordIdx, field, newValue)
  modifiedKeys.value.add(makeCellKey(fileIdx, tableIdx, recordIdx, field))
  editingKey.value = null
}

function cancelEdit() {
  editingKey.value = null
}

// ============================================================
// 交互
// ============================================================
function goExtract() {
  router.push('/extract')
}

function handleNext() {
  resultStore.setConfirmed(true)
  ElMessage.success('已确认结果，即将进入导出页')
  router.push('/export')
}
</script>

<style scoped>
.result-page {
  padding: 16px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ==================== 顶部说明卡 ==================== */
.intro-card { border-radius: 8px; }
.intro-content { display: flex; align-items: flex-start; gap: 12px; }
.intro-icon { font-size: 24px; color: #409eff; flex-shrink: 0; margin-top: 2px; }
.intro-title { font-size: 16px; font-weight: 600; color: #303133; margin-bottom: 6px; }
.intro-desc { font-size: 14px; color: #606266; line-height: 1.6; margin-bottom: 10px; }
.intro-desc strong { color: #e6a23c; }
.intro-desc kbd {
  display: inline-block; padding: 1px 6px; border: 1px solid #dcdfe6;
  border-bottom-width: 2px; border-radius: 3px; font-size: 12px;
  font-family: Consolas, Monaco, monospace; background-color: #f5f7fa; color: #606266;
}
.stats { display: flex; flex-wrap: wrap; gap: 8px; }

/* ==================== 工具栏 ==================== */
.toolbar-card { border-radius: 8px; }
.toolbar { display: flex; align-items: center; justify-content: space-between; }
.toolbar-left { display: flex; align-items: center; gap: 6px; font-size: 14px; color: #606266; }
.toolbar-right { display: flex; gap: 8px; }

/* ==================== 文件卡片 ==================== */
.file-card { border-radius: 8px; }
.file-header {
  display: flex; align-items: center; justify-content: space-between;
  cursor: pointer; user-select: none;
}
.file-title { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.file-icon { color: #409eff; font-size: 18px; }
.file-name { font-size: 15px; font-weight: 600; color: #303133; }
.file-actions { display: flex; align-items: center; gap: 8px; }
.expand-hint { font-size: 12px; color: #909399; }

/* 展开箭头：默认向右，展开时向下 */
.expand-icon {
  transition: transform 0.2s;
  color: #909399;
}
.expand-icon.is-expanded {
  transform: rotate(90deg);
}

/* ==================== 表块 ==================== */
.table-list { display: flex; flex-direction: column; gap: 16px; }
.table-block { background-color: #fafafa; border-radius: 6px; padding: 12px; }
.table-header {
  display: flex; align-items: center; gap: 8px; margin-bottom: 10px;
  font-size: 14px; font-weight: 600; color: #606266;
}
.table-name { flex: 1; }

/* ==================== 单元格 ==================== */
.cell-wrapper {
  min-height: 22px; padding: 2px 4px; border-radius: 3px;
  cursor: cell; transition: background-color 0.15s;
}
.cell-wrapper:hover { background-color: #f0f7ff; }
.cell-text {
  display: block; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap;
}
.cell-abnormal { color: #f56c6c; font-weight: 600; }
.cell-abnormal-bg { background-color: #fef0f0; }
.cell-modified-bg { background-color: #fdf6ec; }

/* ==================== 溯源信息列 ==================== */
.trace-cell { display: flex; flex-direction: column; gap: 6px; }
.trace-row { display: flex; flex-direction: column; gap: 3px; padding: 3px 0; border-bottom: 1px dashed #ebeef5; }
.trace-row:last-child { border-bottom: none; }
.trace-field { font-size: 12px; font-weight: 600; color: #303133; }
.trace-body { display: flex; flex-direction: column; gap: 3px; }
.trace-source { font-size: 12px; color: #409eff; cursor: default; }
.trace-source-empty { color: #909399; }
.trace-meta { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.trace-meta .el-progress { flex: 1; min-width: 70px; }
.trace-empty { color: #c0c4cc; font-size: 12px; }

/* 风险标签配色 */
.risk-tag { margin-right: 0; }
.risk-tag-not_found { background-color: #f56c6c !important; border-color: #f56c6c !important; color: #fff !important; }
.risk-tag-low_confidence { background-color: #e6a23c !important; border-color: #e6a23c !important; color: #fff !important; }
.risk-tag-conflict { background-color: #c9a227 !important; border-color: #c9a227 !important; color: #fff !important; }
.risk-tag-no_source { background-color: #409eff !important; border-color: #409eff !important; color: #fff !important; }

/* ==================== 底部操作栏 ==================== */
.action-bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 0;
}
</style>