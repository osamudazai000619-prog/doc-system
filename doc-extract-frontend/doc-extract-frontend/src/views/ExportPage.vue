<!-- ============================================================
     ExportPage.vue —— 模板映射与导出页面（5.2 loading 优化）
     ============================================================ -->

<template>
  <div
    class="export-page"
    v-loading="isExporting"
    element-loading-text="正在生成文件，请稍候..."
  >

    <el-card class="intro-card" shadow="never">
      <div class="intro-content">
        <el-icon class="intro-icon"><UploadFilled /></el-icon>
        <div class="intro-text">
          <div class="intro-title">导出文件</div>
          <div class="intro-desc">
            这里将完成“模板字段映射 → 生成文件 → 下载文件”的流程。
            请将左侧的模板字段，映射到右侧的提取字段。
          </div>
        </div>
      </div>
    </el-card>

    <!-- 空状态 -->
    <el-card v-if="!hasTemplate" class="empty-card" shadow="never">
      <el-empty description="还没有可用的模板文件，请先返回上传页上传模板文件" :image-size="120">
        <el-button type="primary" @click="goUpload">返回上传页</el-button>
      </el-empty>
    </el-card>

    <template v-else>
      <!-- 模板文件列表 -->
      <el-card class="section-card" shadow="never">
        <template #header>
          <div class="section-header">
            <div class="section-title">
              <el-icon><Files /></el-icon>
              <span>模板文件</span>
              <el-tag type="info" size="small" round>共 {{ templateStatusList.length }} 个</el-tag>
            </div>
          </div>
        </template>
        <div class="template-list">
          <div v-for="item in templateStatusList" :key="item.filename" class="template-item">
            <el-icon class="template-icon"><Document /></el-icon>
            <span class="template-name" :title="item.filename">{{ item.filename }}</span>
            <el-tag :type="getStatusInfo(item.status).type" size="small" round>
              {{ getStatusInfo(item.status).text }}
            </el-tag>
          </div>
        </div>
      </el-card>

      <!-- 映射区域 -->
      <el-card class="section-card" shadow="never">
        <template #header>
          <div class="section-header">
            <div class="section-title">
              <el-icon><Postcard /></el-icon>
              <span>字段映射</span>
              <el-tag type="warning" size="small" round>模板字段 → 提取字段</el-tag>
            </div>
          </div>
        </template>

        <div class="mapping-tip">
          💡 请选择每个模板字段对应的提取字段。如果某个模板字段不需要填充，可以留空。
        </div>

        <div class="mapping-list">
          <template v-for="(table, ti) in templateTables" :key="table.name || ti">
            <div v-if="table.name" class="mapping-group-title">
              <el-icon><Grid /></el-icon>
              <span>{{ table.name }}</span>
              <el-tag size="small" round>{{ table.fields.length }} 个字段</el-tag>
            </div>
            <div
              v-for="tmplField in table.fields"
              :key="`${table.name || 't' + ti}::${tmplField}`"
              class="mapping-item"
            >
              <div class="mapping-label">
                <el-icon><Document /></el-icon>
                <span>{{ tmplField }}</span>
              </div>
              <el-icon class="mapping-arrow"><ArrowRight /></el-icon>
              <div class="mapping-select">
                <el-select
                  v-model="mapping[tmplField]"
                  placeholder="请选择提取字段"
                  clearable
                  :disabled="isExporting"
                  style="width: 100%"
                >
                  <el-option
                    v-for="extractField in extractFieldOptions"
                    :key="extractField"
                    :label="extractField"
                    :value="extractField"
                  />
                </el-select>
              </div>
            </div>
          </template>
        </div>
      </el-card>

      <div class="action-bar">
        <el-button size="large" :disabled="isExporting" @click="goResult">
          <el-icon><ArrowLeft /></el-icon>
          <span>上一步：核对结果</span>
        </el-button>

        <el-button
          type="primary"
          size="large"
          :disabled="!isMappingComplete || isExporting"
          :loading="isExporting"
          @click="handleExport"
        >
          <span>{{ isExporting ? '生成中...' : '生成文件' }}</span>
          <el-icon v-if="!isExporting"><Download /></el-icon>
        </el-button>
      </div>

      <!-- 生成结果：预览 / 下载 -->
      <el-card v-if="exportResult" class="section-card" shadow="never">
        <template #header>
          <div class="section-header">
            <div class="section-title">
              <el-icon><Document /></el-icon>
              <span>生成结果</span>
              <el-tag type="success" size="small" round>已生成</el-tag>
            </div>
          </div>
        </template>
        <div class="result-row">
          <span class="result-name" :title="exportResult.filename">
            {{ exportResult.filename }}
          </span>
          <div class="result-actions">
            <el-button :loading="previewLoading" @click="handlePreview">
              <el-icon><View /></el-icon>
              <span>预览</span>
            </el-button>
            <el-button
              type="primary"
              @click="triggerDownload(exportResult.downloadUrl, exportResult.filename)"
            >
              <el-icon><Download /></el-icon>
              <span>下载</span>
            </el-button>
          </div>
        </div>
      </el-card>

      <!-- 预览弹窗：展示生成文件本身的内容 -->
      <el-dialog
        v-model="previewVisible"
        :title="`文件预览：${previewFilename}`"
        width="80%"
        top="5vh"
      >
        <pre class="preview-content">{{ previewContent }}</pre>
      </el-dialog>
    </template>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useFileStore } from '@/stores/fileStore'
import { useResultStore } from '@/stores/resultStore'
import request from '@/api/request'

const router = useRouter()
const fileStore = useFileStore()
const resultStore = useResultStore()

// 解析模板内容 → 表格分组 [{ name, fields }]
// 后端两种标记：docx 为「[表格N]」，xlsx 为「[工作表] sheet名」；
// 标记之后紧跟的首行即该表表头（「 | 」分隔）。标记之前的标题/描述段落
// （如 docx 首行的文档标题）不是表头，绝不能当作字段。
function parseTemplateTables(content) {
  const lines = (content || '').split('\n').map((l) => l.trim()).filter(Boolean)
  const groups = []
  let current = null
  const startNew = (name) => {
    current = { name, fields: null }
    groups.push(current)
  }
  for (const line of lines) {
    const sheetMatch = line.match(/^\[工作表\]\s*(.*)$/)
    const tableMatch = line.match(/^\[表格\s*\d+\]\s*(.*)$/)
    if (sheetMatch) {
      startNew(sheetMatch[1] || `工作表${groups.length + 1}`)
      continue
    }
    if (tableMatch) {
      startNew(tableMatch[1] || `表格${groups.length + 1}`)
      continue
    }
    // 标记后的首行即表头；未进入任何分组前的普通段落直接忽略
    if (current && current.fields === null) {
      current.fields = line.split('|').map((s) => s.trim()).filter(Boolean)
    }
  }
  const valid = groups.filter((g) => g.fields && g.fields.length > 0)
  if (valid.length > 0) return valid

  // 兜底：txt/md 等无表格标记的模板，沿用旧逻辑（首个非标记行作为字段行）
  const headerLine = lines.find((l) => !l.startsWith('[')) || ''
  const fields = headerLine.split('|').map((s) => s.trim()).filter(Boolean)
  return fields.length > 0 ? [{ name: '', fields }] : []
}

const templateTables = computed(() => {
  const content = fileStore.templateParsedFiles[0]?.content || ''
  return parseTemplateTables(content)
})

// 映射契约为扁平 Dict[模板字段 -> 提取字段]：多个表表头相同时共用同一份映射，
// 因此字段按名去重（保序）
const templateFields = computed(() => {
  const seen = new Set()
  const result = []
  for (const table of templateTables.value) {
    for (const field of table.fields) {
      if (!seen.has(field)) {
        seen.add(field)
        result.push(field)
      }
    }
  }
  return result
})

const mapping = ref({})

watch(templateFields, (fields) => {
  const next = {}
  fields.forEach((f) => { next[f] = mapping.value[f] || '' })
  mapping.value = next
}, { immediate: true })

const extractFieldOptions = computed(() => {
  if (resultStore.fields && resultStore.fields.length > 0) {
    return resultStore.fields
  }
  return resultStore.allFieldNames || []
})

const isMappingComplete = computed(() => {
  return Object.values(mapping.value).some((val) => val !== '')
})

const hasTemplate = computed(() => {
  return fileStore.templateParsedFiles.length > 0
})

const templateStatusList = computed(() => {
  return fileStore.templateParsedFiles.map((item) => ({
    filename: item.filename,
    status: item.status,
    content: item.content,
  }))
})

function getStatusInfo(status) {
  const map = {
    success:     { text: '解析成功', type: 'success' },
    empty:       { text: '内容为空', type: 'warning' },
    unsupported: { text: '格式不支持', type: 'danger' },
    error:       { text: '解析失败', type: 'danger' },
    unknown:     { text: '未解析', type: 'info' },
  }
  return map[status] || { text: '未知', type: 'info' }
}

const isExporting = ref(false)
const exportResult = ref(null)      // { downloadUrl, filename }
const previewVisible = ref(false)
const previewLoading = ref(false)
const previewContent = ref('')
const previewFilename = ref('')

// 预览生成文件本身：从 download_url 提取 file_id，调 /preview 接口
async function handlePreview() {
  if (!exportResult.value) return
  const fileId = exportResult.value.downloadUrl.split('/').pop()
  previewLoading.value = true
  try {
    const res = await request.get(`/preview/${fileId}`)
    previewContent.value = res.content || '（文件内容为空）'
    previewFilename.value = res.filename || exportResult.value.filename
    previewVisible.value = true
  } catch (err) {
    console.error('[预览失败]', err)
  } finally {
    previewLoading.value = false
  }
}

async function handleExport() {
  // ★ 防重入：如果正在生成，直接 return
  if (isExporting.value) return

  if (!isMappingComplete.value) {
    ElMessage.warning('请至少映射一个字段')
    return
  }

  if (fileStore.templateParsedFiles.length === 0) {
    ElMessage.error('没有可用的模板文件，请返回上传页')
    return
  }

  // 后端契约要求 records 为单个 Dict[str, str]；
  // 前端展示层把多实体拆成了记录数组，发送前重组为"每条记录一个表条目"，
  // 后端 _collect_rows 逐条收集后仍按行填充，效果不变
  const confirmedData = resultStore.results.map((file) => ({
    source_file: file.source_file,
    extracted_tables: (file.extracted_tables || []).flatMap((table) =>
      (table.records || []).map((rec) => ({
        table_category: table.table_category || '',
        records: rec,
      }))
    ),
  }))

  const payload = {
    confirmed_data: confirmedData,
    template_name: fileStore.templateParsedFiles[0].filename,
    mapping: mapping.value,
  }

  console.log('[发起导出] 参数：', payload)

  isExporting.value = true
  try {
    const res = await request.post('/export', payload)
    const downloadUrl = res.download_url

    if (downloadUrl) {
      exportResult.value = {
        downloadUrl,
        filename: res.message?.replace(/^生成成功：/, '') || '提取结果文件',
      }
      ElMessage.success('生成成功，可预览或下载')
    } else {
      ElMessage.error('后端未返回下载链接')
    }
  } catch (err) {
    console.error('[导出失败]', err)
  } finally {
    isExporting.value = false
  }
}

function triggerDownload(url, filename) {
  // ★ 如果 url 是相对路径，拼上 /api 前缀
  // 因为 Vite 开发环境有代理，请求 /api/** 会被转发到后端
  // 生产环境会由 Nginx 处理，逻辑相同
  let fullUrl = url
  if (url && !/^https?:\/\//i.test(url)) {
    fullUrl = url.startsWith('/api') ? url : `/api${url}`
  }

  const link = document.createElement('a')
  link.href = fullUrl
  link.setAttribute('download', filename)
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
}

function goUpload() { router.push('/upload') }
function goResult() { router.push('/result') }
</script>

<style scoped>
.result-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.result-name {
  flex: 1;
  color: #303133;
  font-size: 14px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.result-actions {
  display: flex;
  gap: 10px;
  flex-shrink: 0;
}
.preview-content {
  margin: 0;
  max-height: 60vh;
  overflow: auto;
  font-size: 13px;
  line-height: 1.7;
  color: #303133;
  white-space: pre-wrap;
  word-break: break-all;
}
.export-page {
  padding: 16px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.intro-card { border-radius: 8px; }
.intro-content { display: flex; align-items: flex-start; gap: 12px; }
.intro-icon { font-size: 24px; color: #409eff; flex-shrink: 0; margin-top: 2px; }
.intro-title { font-size: 16px; font-weight: 600; color: #303133; margin-bottom: 6px; }
.intro-desc { font-size: 14px; color: #606266; line-height: 1.6; }
.empty-card { border-radius: 8px; }
.section-card { border-radius: 8px; }
.section-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; }
.section-title { display: flex; align-items: center; gap: 8px; font-size: 16px; font-weight: 600; color: #303133; }
.template-list { display: flex; flex-direction: column; gap: 8px; }
.template-item {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px; background-color: #f5f7fa;
  border-radius: 6px; font-size: 14px;
}
.template-item:hover { background-color: #ecf5ff; }
.template-icon { color: #409eff; flex-shrink: 0; }
.template-name { flex: 1; color: #303133; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.mapping-tip { font-size: 13px; color: #909399; margin-bottom: 16px; }
.mapping-list { display: flex; flex-direction: column; gap: 14px; }
.mapping-group-title {
  display: flex; align-items: center; gap: 8px;
  margin-top: 6px; padding: 6px 10px;
  font-size: 13px; font-weight: 600; color: #475569;
  background-color: #f1f5f9; border-left: 3px solid #409eff; border-radius: 4px;
}
.mapping-group-title .el-tag { margin-left: 4px; font-weight: 400; }
.mapping-item {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 16px; background-color: #fafafa; border-radius: 6px;
}
.mapping-label {
  display: flex; align-items: center; gap: 6px;
  width: 140px; font-size: 14px; font-weight: 600;
  color: #303133; flex-shrink: 0;
}
.mapping-arrow { color: #c0c4cc; flex-shrink: 0; }
.mapping-select { flex: 1; }
.action-bar { display: flex; justify-content: space-between; align-items: center; padding: 16px 0; }
</style>