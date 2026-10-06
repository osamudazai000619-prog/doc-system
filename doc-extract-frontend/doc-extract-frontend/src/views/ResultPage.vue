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
                :header-cell-style="{ background: 'var(--de-surface-2)', color: 'var(--de-text-1)', fontWeight: 600 }"
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
                      @dblclick="startEdit(fileIdx, tableIdx, $index, field, row[field])"
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
                        :title="String(row[field] ?? '')"
                      >
                        {{ row[field] }}
                      </span>
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
import { useResultStore } from '@/stores/resultStore'

// ============================================================
// 依赖
// ============================================================
const router = useRouter()
const resultStore = useResultStore()

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

function isAbnormal(value) {
  const s = String(value ?? '')
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

  if (String(oldValue ?? '') === String(newValue)) {
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
.intro-card { border-radius: var(--de-r-sm); }
.intro-content { display: flex; align-items: flex-start; gap: 12px; }
.intro-icon { font-size: var(--de-fs-7); color: var(--de-primary); flex-shrink: 0; margin-top: 2px; }
.intro-title { font-size: var(--de-fs-4); font-weight: 600; color: var(--de-text-1); margin-bottom: 6px; }
.intro-desc { font-size: var(--de-fs-3); color: var(--de-text-2); line-height: 1.6; margin-bottom: 10px; }
.intro-desc strong { color: var(--de-warning); }
.intro-desc kbd {
  display: inline-block; padding: 1px 6px; border: 1px solid var(--de-border-strong);
  border-bottom-width: 2px; border-radius: var(--de-r-xxs); font-size: var(--de-fs-1);
  font-family: Consolas, Monaco, monospace; background-color: var(--de-surface-2); color: var(--de-text-2);
}
.stats { display: flex; flex-wrap: wrap; gap: 8px; }

/* ==================== 工具栏 ==================== */
.toolbar-card { border-radius: var(--de-r-sm); }
.toolbar { display: flex; align-items: center; justify-content: space-between; }
.toolbar-left { display: flex; align-items: center; gap: 6px; font-size: var(--de-fs-3); color: var(--de-text-2); }
.toolbar-right { display: flex; gap: 8px; }

/* ==================== 文件卡片 ==================== */
.file-card { border-radius: var(--de-r-sm); }
.file-header {
  display: flex; align-items: center; justify-content: space-between;
  cursor: pointer; user-select: none;
}
.file-title { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.file-icon { color: var(--de-primary); font-size: var(--de-fs-5); }
.file-name { font-size: var(--de-fs-3); font-weight: 600; color: var(--de-text-1); }
.file-actions { display: flex; align-items: center; gap: 8px; }
.expand-hint { font-size: var(--de-fs-1); color: var(--de-text-3); }

/* 展开箭头：默认向右，展开时向下 */
.expand-icon {
  transition: transform 0.2s;
  color: var(--de-text-3);
}
.expand-icon.is-expanded {
  transform: rotate(90deg);
}

/* ==================== 表块 ==================== */
.table-list { display: flex; flex-direction: column; gap: 16px; }
.table-block { background-color: var(--de-surface-2); border-radius: var(--de-r-xs); padding: 12px; }
.table-header {
  display: flex; align-items: center; gap: 8px; margin-bottom: 10px;
  font-size: var(--de-fs-3); font-weight: 600; color: var(--de-text-2);
}
.table-name { flex: 1; }

/* ==================== 单元格 ==================== */
.cell-wrapper {
  min-height: 22px; padding: 2px 4px; border-radius: var(--de-r-xxs);
  cursor: cell; transition: background-color 0.15s;
}
.cell-wrapper:hover { background-color: var(--de-primary-soft); }
.cell-text {
  display: block; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap;
}
.cell-abnormal { color: var(--de-danger); font-weight: 600; }
.cell-abnormal-bg { background-color: rgba(248, 113, 113, 0.12); }
.cell-modified-bg { background-color: rgba(251, 191, 36, 0.12); }

/* ==================== 底部操作栏 ==================== */
.action-bar {
  display: flex; justify-content: space-between; align-items: center;
  padding: 16px 0;
}
</style>