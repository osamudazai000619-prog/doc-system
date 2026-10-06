<!-- ============================================================
     TaskDetailDialog.vue —— 历史任务详情弹窗
     竖长表单式布局：配置快照 + 源文件预览（点击展开）+ 产物下载
     用法：<TaskDetailDialog v-model:visible="x" :task-id="id" />
     ============================================================ -->

<template>
  <el-dialog
    :model-value="visible"
    title="任务详情"
    width="560px"
    top="5vh"
    @update:model-value="$emit('update:visible', $event)"
  >
    <div v-if="detail" class="detail-body" v-loading="loading">

      <el-form label-width="72px" label-position="left" class="detail-form">
        <el-form-item label="时间">
          <span class="form-text">{{ detail.created_at }}</span>
        </el-form-item>
        <el-form-item label="模板">
          <span class="form-text">{{ detail.template_name || '（无模板）' }}</span>
        </el-form-item>
        <el-form-item label="规模">
          <span class="form-text">
            {{ detail.stats?.file_count ?? 0 }} 文件 / {{ detail.stats?.record_count ?? 0 }} 记录
          </span>
        </el-form-item>
        <el-form-item label="提取字段">
          <div>
            <el-tag v-for="f in detail.fields" :key="f" size="small" class="field-tag">{{ f }}</el-tag>
            <span v-if="!detail.fields?.length" class="more">（未设置字段）</span>
          </div>
        </el-form-item>
        <el-form-item v-if="detail.prompt" label="提示词">
          <pre class="prompt-box">{{ detail.prompt }}</pre>
        </el-form-item>
      </el-form>

      <!-- 源文件：点击“预览”才展开该文件的提取结果 -->
      <div class="detail-block">
        <div class="block-title">源文件（{{ detail.results?.length || 0 }}）</div>
        <div v-for="(file, fi) in detail.results" :key="fi" class="file-block">
          <div class="file-row">
            <el-icon><Document /></el-icon>
            <span class="file-row-name" :title="file.source_file">{{ file.source_file }}</span>
            <el-button size="small" text type="primary" @click="togglePreview(fi)">
              {{ previewIndex === fi ? '收起' : '预览' }}
            </el-button>
          </div>
          <div v-if="previewIndex === fi" class="file-preview">
            <el-table
              v-for="(table, ti) in file.extracted_tables" :key="ti"
              :data="normalizeRecords(table.records)"
              size="small" border class="result-table"
            >
              <el-table-column
                v-for="col in collectColumns([table])"
                :key="col" :prop="col" :label="col || table.table_category" min-width="110" show-overflow-tooltip
              />
            </el-table>
            <el-empty
              v-if="!(file.extracted_tables || []).length"
              description="该文件无提取结果" :image-size="48"
            />
          </div>
        </div>
        <el-empty
          v-if="!(detail.results || []).length"
          description="无源文件" :image-size="48"
        />
      </div>

      <!-- 导出产物 -->
      <div class="detail-block" v-if="detail.exports?.length">
        <div class="block-title">导出产物</div>
        <div v-for="e in detail.exports" :key="e.file_id" class="export-row">
          <el-icon><Document /></el-icon>
          <span class="export-name" :title="e.filename">{{ e.filename }}</span>
          <span class="export-time">{{ e.created_at }}</span>
          <el-button size="small" type="primary" @click="download(e.file_id, e.filename)">
            <el-icon><Download /></el-icon>
            <span>下载</span>
          </el-button>
        </div>
      </div>

    </div>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { fetchHistoryDetail } from '@/api/history'

const props = defineProps({
  visible: Boolean,
  taskId: { type: [Number, String], default: null },
})
defineEmits(['update:visible'])

const loading = ref(false)
const detail = ref(null)
const previewIndex = ref(-1)  // 当前展开预览的源文件下标，-1 表示全部收起

function togglePreview(fi) {
  previewIndex.value = previewIndex.value === fi ? -1 : fi
}

async function load() {
  if (!props.taskId) return
  loading.value = true
  detail.value = null
  previewIndex.value = -1
  try {
    detail.value = await fetchHistoryDetail(props.taskId)
  } finally {
    loading.value = false
  }
}

// 弹窗打开且有 taskId 时加载详情
watch(
  () => [props.visible, props.taskId],
  ([v]) => { if (v) load() }
)

// 契约 records 为 Dict[str, str]，容错兼容数组形态
function normalizeRecords(records) {
  if (Array.isArray(records)) return records.filter((r) => r && typeof r === 'object')
  if (records && typeof records === 'object') return [records]
  return []
}

function collectColumns(tables) {
  const seen = []
  ;(tables || []).forEach((t) => {
    normalizeRecords(t.records).forEach((rec) => {
      Object.keys(rec).forEach((k) => { if (!seen.includes(k)) seen.push(k) })
    })
  })
  return seen
}

function download(fileId, filename) {
  const link = document.createElement('a')
  link.href = `/api/download/${fileId}`
  link.setAttribute('download', filename || '导出文件')
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}
</script>

<style scoped>
.detail-body { display: flex; flex-direction: column; gap: 16px; }
.detail-form :deep(.el-form-item) { margin-bottom: 10px; }
.detail-form :deep(.el-form-item__label) { font-weight: 600; color: #606266; }
.form-text { font-size: 13px; color: #303133; word-break: break-all; }
.field-tag { margin-right: 6px; margin-bottom: 2px; }
.more { font-size: 12px; color: #909399; }
.detail-block .block-title { font-size: 14px; font-weight: 600; color: #303133; margin-bottom: 8px; }
.file-block { margin-bottom: 8px; }
.file-row {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; background: #f5f7fa; border-radius: 6px;
}
.file-row-name {
  flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-size: 13px; color: #303133;
}
.file-preview { margin-top: 6px; }
.result-table { margin-bottom: 10px; }
.prompt-box {
  margin: 0; padding: 10px; background: #f8fafc; border-radius: 6px;
  font-size: 13px; line-height: 1.7; color: #303133;
  white-space: pre-wrap; word-break: break-all; max-height: 160px; overflow: auto;
}
.export-row {
  display: flex; align-items: center; gap: 8px;
  padding: 8px 12px; background: #f5f7fa; border-radius: 6px; margin-bottom: 8px;
}
.export-name {
  flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  font-size: 13px; color: #303133;
}
.export-time { font-size: 12px; color: #909399; flex-shrink: 0; }
</style>
