<!-- ============================================================
     UploadPage.vue —— 上传文档页面（阶段二：从文件库选模板 + 推荐填充）
     ============================================================ -->

<template>
  <div class="upload-page">

    <el-card class="intro-card" shadow="never">
      <div class="intro-content">
        <el-icon class="intro-icon"><InfoFilled /></el-icon>
        <div class="intro-text">
          <div class="intro-title">上传文档</div>
          <div class="intro-desc">
            可先<strong>选择方案</strong>一键填入模板、提取字段与提示词；
            也可以直接上传<strong>目标文档</strong>（要提取信息的文件）和
            <strong>模板文件</strong>（要填充的 Word 或 Excel）。
            支持格式：docx / txt / md / xlsx / pdf。
          </div>
        </div>
      </div>
    </el-card>

    <!-- ==================================================
         选择方案（可选）：一键填入模板文件 + 提取字段 + 提示词
         ================================================== -->
    <el-card class="scheme-card" shadow="never">
      <template #header>
        <div class="scheme-header">
          <div class="scheme-title">
            <el-icon><Collection /></el-icon>
            <span>选择方案</span>
            <el-tag size="small" type="info" round>可选</el-tag>
          </div>
          <div class="scheme-actions">
            <el-button
              v-if="hasHistory"
              size="small"
              text
              type="primary"
              :loading="redoLoading"
              @click="redoLastTask"
            >
              <el-icon><RefreshLeft /></el-icon>
              <span>重做上次任务</span>
            </el-button>
            <el-button size="small" text type="primary" @click="router.push('/schemes')">
              <el-icon><SetUp /></el-icon>
              <span>管理方案</span>
            </el-button>
          </div>
        </div>
      </template>
      <el-select
        v-model="selectedSchemeId"
        placeholder="从已有方案一键填入模板、字段和提示词（也可不选，手动上传）"
        clearable
        :loading="schemesLoading"
        style="width: 100%"
        @change="onSchemeChange"
      >
        <el-option
          v-for="s in schemeOptions"
          :key="s.id"
          :label="s.name + (s.template_name ? ' — ' + s.template_name : '')"
          :value="s.id"
        >
          <span class="scheme-option-name">
            {{ s.name }}{{ s.template_name ? ' — ' + s.template_name : '' }}
          </span>
          <span v-if="s.healthy === false" class="scheme-option-bad">模板已失效</span>
        </el-option>
      </el-select>
    </el-card>

    <!-- 两个上传卡片并排 -->
    <div class="upload-row">
      <FileUploadCard
        title="目标文档"
        tip="支持 .docx / .txt / .md / .xlsx / .pdf，可多选"
        accept=".txt,.md,.docx,.xlsx,.pdf"
        :files="fileStore.targetFiles"
        @add="onAddTarget"
        @remove="onRemoveTarget"
        @clear="onClearTarget"
      />

      <div class="template-section">
        <FileUploadCard
          title="模板文件"
          tip="支持 .docx / .xlsx，可多选"
          accept=".docx,.xlsx"
          :files="fileStore.templateFiles"
          @add="onAddTemplate"
          @remove="onRemoveTemplate"
          @clear="onClearTemplate"
        >
          <!-- 从文件库选模板：属于「模板文件」卡片自己的操作，放进卡片头部 -->
          <template #header-actions>
            <el-button size="small" text type="primary" @click="openAssetPicker">
              <el-icon><FolderOpened /></el-icon>
              <span>从文件库选择</span>
            </el-button>
          </template>
        </FileUploadCard>
        <!-- 推荐提示条 -->
        <el-alert
          v-if="recommend"
          :title="recommendTitle"
          type="info"
          :closable="false"
          show-icon
          class="recommend-alert"
        >
          <template #default>
            <el-button size="small" type="primary" @click="acceptRecommend">
              一键填充
            </el-button>
            <el-button size="small" text @click="recommend = null">忽略</el-button>
          </template>
        </el-alert>
      </div>
    </div>

    <!-- 操作按钮区 -->
    <el-card class="action-card" shadow="never">
      <div class="action-bar">
        <div class="action-left">
          <el-button
            type="primary"
            :disabled="!canUpload || uploading"
            :loading="uploading"
            @click="handleUpload"
          >
            <el-icon v-if="!uploading"><Upload /></el-icon>
            <span>{{ uploading ? '上传中...' : '上传并解析' }}</span>
          </el-button>

          <el-button
            type="danger"
            plain
            :disabled="!fileStore.hasUploaded || uploading"
            @click="handleClearAll"
          >
            <el-icon><Delete /></el-icon>
            <span>清空所有</span>
          </el-button>

          <span v-if="!canUpload" class="hint">请至少选择一个目标文档</span>
          <span v-else-if="uploading" class="hint hint-info">模拟上传中，请稍候……</span>
          <span v-else-if="fileStore.hasUploaded" class="hint hint-success">
            解析完成，共 {{ fileStore.validTargetFiles.length }} 个目标文档可用
          </span>
        </div>
        <div class="action-right">
          <el-button
            type="primary"
            plain
            :disabled="!canGoNext || uploading"
            @click="handleNext"
          >
            <span>下一步：设置字段</span>
            <el-icon><ArrowRight /></el-icon>
          </el-button>
        </div>
      </div>
    </el-card>

    <!-- 文件解析状态表格 -->
    <div v-if="fileStore.hasUploaded" v-loading="uploading" element-loading-text="正在解析文档...">
      <FileStatusTable :files="fileStore.allFiles" @preview="handlePreview" />
    </div>

    <!-- 内嵌预览区 -->
    <div v-if="previewFile" class="preview-wrapper">
      <div class="preview-header-bar">
        <div class="preview-label">
          <el-icon><View /></el-icon>
          <span>正文预览</span>
        </div>
        <el-button type="primary" text size="small" @click="previewFile = null">
          <el-icon><Close /></el-icon>
          <span>关闭预览</span>
        </el-button>
      </div>
      <DocumentPreview mode="inline" :filename="previewFile.filename" :content="previewFile.content" />
    </div>

    <!-- 文件库选择弹窗 -->
    <el-dialog v-model="assetPickerVisible" title="从文件库选择模板" width="520px">
      <el-input
        v-model="assetKeyword"
        placeholder="搜索文件名..."
        size="small"
        clearable
        prefix-icon="Search"
        class="asset-search"
      />
      <el-empty v-if="filteredAssets.length === 0" description="暂无可用的模板文件" :image-size="60" />
      <div v-for="a in filteredAssets" :key="a.id" class="asset-row">
        <div class="asset-info">
          <el-icon><Document /></el-icon>
          <span class="asset-name" :title="a.original_name">{{ a.original_name }}</span>
          <span class="asset-meta">{{ a.ext }} · {{ formatSize(a.size) }}</span>
        </div>
        <el-button size="small" type="primary" @click="selectAsset(a)">选择</el-button>
      </div>
    </el-dialog>

  </div>
</template>

<script setup>
import request from '@/api/request'
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { useFileStore } from '@/stores/fileStore'
import { useResultStore } from '@/stores/resultStore'
import { useFieldStore } from '@/stores/fieldStore'
import { fetchAssets, loadAsset } from '@/api/assets'
import { fetchSchemes, fetchRecommendation } from '@/api/schemes'
import { fetchHistoryList, fetchHistoryDetail } from '@/api/history'
import FileUploadCard from '@/components/FileUploadCard.vue'
import FileStatusTable from '@/components/FileStatusTable.vue'
import DocumentPreview from '@/components/DocumentPreview.vue'

const router = useRouter()
const fileStore = useFileStore()
const resultStore = useResultStore()
const fieldStore = useFieldStore()

const uploading = ref(false)
const previewFile = ref(null)

const canUpload = computed(() => fileStore.targetFiles.length > 0)
const canGoNext = computed(() => fileStore.validTargetFiles.length > 0)

// ======== 选择方案（一阶段入口，填入模板/字段/提示词） ========
const selectedSchemeId = ref(resultStore.schemeId || null)
const schemeOptions = ref([])
const schemesLoading = ref(false)

// ======== 重做上次任务（从最近一条已完成历史还原配置，不带入旧文档） ========
const hasHistory = ref(false)
const redoLoading = ref(false)

onMounted(async () => {
  schemesLoading.value = true
  try {
    const [schemeRes] = await Promise.all([
      fetchSchemes(),
      fetchHistoryList(1, 1).then((res) => {
        hasHistory.value = (res.total || 0) > 0
      }).catch(() => {}),
    ])
    schemeOptions.value = schemeRes.items || []
  } catch {
    // 方案列表加载失败不阻断上传主流程
  } finally {
    schemesLoading.value = false
  }
})

async function redoLastTask() {
  if (redoLoading.value) return
  redoLoading.value = true
  try {
    const listRes = await fetchHistoryList(1, 1)
    const last = (listRes.items || [])[0]
    if (!last) {
      hasHistory.value = false
      ElMessage.info('还没有已完成的历史任务')
      return
    }
    try {
      await ElMessageBox.confirm(
        `将载入上次任务「${last.title || last.template_name || '未命名'}」的模板、字段与提示词，`
        + '当前未上传的配置会被替换（旧文档不会带入）。',
        '重做上次任务',
        { type: 'info', confirmButtonText: '载入配置', cancelButtonText: '取消' },
      )
    } catch {
      return  // 用户取消
    }

    const detail = await fetchHistoryDetail(last.id)
    // 清空工作区（含目标文档原始 File），再按历史快照还原配置
    fileStore.clearAll()
    resultStore.clearAll()
    fieldStore.setFields(detail.fields || [])
    resultStore.setFields(detail.fields || [])
    resultStore.setPrompt(detail.prompt || '')
    resultStore.setSchemeId(null)
    selectedSchemeId.value = null
    recommend.value = null
    if (detail.template_asset_id) {
      try {
        const item = await loadAsset(detail.template_asset_id)
        fileStore.upsertParsedFile(item)
      } catch {
        // 模板资产可能已被清理：字段/提示词仍可用，提示用户重传模板
        ElMessage.warning('上次的模板文件已不存在，字段与提示词已载入，请重新上传模板')
      }
    }
    previewFile.value = null
    ElMessage.success('已还原上次任务配置，请上传新的目标文档')
  } catch {
    // 拦截器已统一提示
  } finally {
    redoLoading.value = false
  }
}

// 选中方案 → 一键填入：模板文件（从文件库拉取解析结果）+ 提取字段 + 提示词；
// 字段与提示词写入 store，二阶段页面进入时直接带出，可继续修改
async function onSchemeChange(id) {
  resultStore.setSchemeId(id || null)
  if (!id) return
  const scheme = schemeOptions.value.find((s) => s.id === id)
  if (!scheme) return
  fieldStore.setFields(scheme.fields || [])
  resultStore.setFields(scheme.fields || [])
  resultStore.setPrompt(scheme.prompt || '')
  if (scheme.template_asset_id) {
    try {
      const item = await loadAsset(scheme.template_asset_id)
      fileStore.upsertParsedFile(item)
    } catch {
      // 拦截器已提示（如模板文件已被删除）；字段与提示词填充不受影响
    }
  }
  ElMessage.success(`已应用方案「${scheme.name}」：模板/字段/提示词已填入，可继续修改`)
}

// ======== 目标文档 ========
function onAddTarget(files) { fileStore.addFile('target', files) }
function onRemoveTarget(filename) { fileStore.removeFile('target', filename) }
function onClearTarget() { fileStore.targetFiles.splice(0) }

// ======== 模板文件 ========
function onAddTemplate(files) { fileStore.addFile('template', files) }
function onRemoveTemplate(filename) { fileStore.removeFile('template', filename) }
function onClearTemplate() { fileStore.templateFiles.splice(0) }

// ======== 上传并解析 ========
async function handleUpload() {
  if (uploading.value) return
  uploading.value = true
  try {
    const formData = new FormData()
    fileStore.targetFiles.forEach((file) => formData.append('target_files', file))
    fileStore.templateFiles.forEach((file) => formData.append('template_files', file))
    const data = await request.post('/upload', formData)
    fileStore.setAllFiles(data)
    // 模板上传成功后检查推荐
    const tmpl = data.find((f) => f.role === 'template' && f.status === 'success')
    if (tmpl && tmpl.asset_id) {
      checkRecommend(tmpl.asset_id)
    }
    const successCount = data.filter((f) => f.status === 'success').length
    const otherCount = data.length - successCount
    if (otherCount > 0) {
      ElMessage.warning(`解析完成：成功 ${successCount} 个，其他 ${otherCount} 个（请查看状态表）`)
    } else if (successCount > 0) {
      ElMessage.success(`解析完成：全部成功，共 ${successCount} 个`)
    }
  } catch (err) {
    console.error('[上传失败]', err)
    ElMessage.error('上传失败，请重试')
  } finally {
    uploading.value = false
  }
}

// ======== 清空 ========
async function handleClearAll() {
  try {
    await ElMessageBox.confirm('确定要清空所有已上传的文件和解析结果吗？', '提示', {
      type: 'warning', confirmButtonText: '确定清空', cancelButtonText: '取消',
    })
    fileStore.clearAll()
    previewFile.value = null
    recommend.value = null
    selectedSchemeId.value = null
    resultStore.setSchemeId(null)
    ElMessage.success('已清空')
  } catch {}
}

// ======== 预览 ========
function handlePreview(file) {
  previewFile.value = file
  setTimeout(() => {
    const el = document.querySelector('.preview-wrapper')
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, 50)
}

// ======== 下一步 ========
function handleNext() {
  if (!canGoNext.value) {
    ElMessage.warning('请先上传并解析至少 1 个目标文档')
    return
  }
  router.push('/extract')
}

// ======== 从文件库选择 ========
const assetPickerVisible = ref(false)
const assetKeyword = ref('')
const assetList = ref([])

function openAssetPicker() {
  assetPickerVisible.value = true
  assetKeyword.value = ''
  fetchAssets('template').then((res) => {
    assetList.value = res.items || []
  }).catch(() => {})
}

const filteredAssets = computed(() => {
  const kw = assetKeyword.value.trim().toLowerCase()
  if (!kw) return assetList.value
  return assetList.value.filter((a) => a.original_name.toLowerCase().includes(kw))
})

function formatSize(size) {
  if (!size) return '0 B'
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

async function selectAsset(a) {
  try {
    const item = await loadAsset(a.id)
    fileStore.upsertParsedFile(item)
    assetPickerVisible.value = false
    ElMessage.success(`已选择模板「${item.filename}」`)
    // 检查推荐
    if (item.asset_id) checkRecommend(item.asset_id)
  } catch {
    // 拦截器已提示
  }
}

// ======== 推荐 ========
const recommend = ref(null)

async function checkRecommend(assetId) {
  try {
    const res = await fetchRecommendation(assetId)
    if (res) recommend.value = res
  } catch {
    // 静默失败
  }
}

const recommendTitle = computed(() => {
  if (!recommend.value) return ''
  const date = recommend.value.used_at
  if (recommend.value.source === 'scheme') {
    return `该模板有已保存的方案「${recommend.value.scheme_name || ''}」${date ? '（' + date + ' 用过）' : ''}`
  }
  return `该模板 ${date ? date : '之前'} 曾使用过，可直接填充上次配置`
})

function acceptRecommend() {
  if (!recommend.value) return
  resultStore.setPrompt(recommend.value.prompt || '')
  fieldStore.setFields(recommend.value.fields || [])
  recommend.value = null
  ElMessage.success('已填充上次使用的提示词和字段')
}
</script>

<style scoped>
.upload-page {
  padding: var(--de-s5) var(--de-s6);
  display: flex;
  flex-direction: column;
  gap: var(--de-s4);
  min-height: 100%;
}

/* ---------- 说明卡 ---------- */
.intro-card { border-radius: var(--de-r-md); }
.intro-content { display: flex; align-items: flex-start; gap: var(--de-s3); }
.intro-icon {
  display: grid;
  place-items: center;
  width: 38px;
  height: 38px;
  flex: none;
  font-size: var(--de-fs-5);
  border-radius: var(--de-r-sm);
  color: var(--de-primary);
  background: var(--de-primary-soft);
}
.intro-title {
  font-size: var(--de-fs-4);
  font-weight: 650;
  color: var(--de-text-1);
  margin-bottom: var(--de-s1);
}
.intro-desc { font-size: var(--de-fs-3); color: var(--de-text-2); line-height: 1.7; }
.intro-desc strong { color: var(--de-primary); font-weight: 650; }

/* ---------- 方案选择卡 ---------- */
.scheme-card { border-radius: var(--de-r-md); }
.scheme-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; }
.scheme-title { display: flex; align-items: center; gap: 8px; font-size: var(--de-fs-4); font-weight: 600; color: var(--de-text-1); }
.scheme-actions { display: flex; align-items: center; gap: 4px; }
.scheme-option-name { float: left; }
.scheme-option-bad { float: right; color: var(--de-danger); font-size: var(--de-fs-1); }

/* ---------- 两个上传卡片并排 ---------- */
.upload-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--de-s4);
  flex: 1;
  min-height: 0;
  align-items: stretch;
}
@media (max-width: 900px) { .upload-row { grid-template-columns: 1fr; } }

.template-section {
  display: flex;
  flex-direction: column;
  gap: var(--de-s2);
  min-height: 0;
}
.template-section > .upload-card { flex: 1; min-height: 0; }
.recommend-alert { margin-top: var(--de-s1); }

/* ---------- 操作区 ---------- */
.action-card { border-radius: var(--de-r-md); }
.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--de-s3);
}
.action-left { display: flex; align-items: center; gap: var(--de-s3); flex-wrap: wrap; }
.action-right { display: flex; align-items: center; gap: var(--de-s3); }

.hint { font-size: var(--de-fs-2); color: var(--de-text-3); }
.hint-info { color: var(--de-primary); }
.hint-success { color: var(--de-success); }

/* ---------- 正文预览 ---------- */
.preview-wrapper { display: flex; flex-direction: column; gap: var(--de-s2); }
.preview-header-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--de-s2) var(--de-s4);
  border-radius: var(--de-r-sm);
  background: var(--de-primary-soft);
  border: 1px solid var(--de-primary-line);
}
.preview-label {
  display: flex;
  align-items: center;
  gap: var(--de-s1);
  font-size: var(--de-fs-3);
  font-weight: 650;
  color: var(--de-primary);
}

/* ---------- 文件库弹窗 ---------- */
.asset-search { margin-bottom: var(--de-s3); }
.asset-row {
  display: flex;
  align-items: center;
  gap: var(--de-s2);
  padding: var(--de-s3);
  background: var(--de-surface-2);
  border: 1px solid var(--de-border);
  border-radius: var(--de-r-sm);
  margin-bottom: var(--de-s2);
  transition: border-color 0.15s, background-color 0.15s;
}
.asset-row:hover {
  border-color: var(--de-primary-line);
  background: var(--de-surface-1);
}
.asset-info { flex: 1; min-width: 0; display: flex; align-items: center; gap: var(--de-s2); }
.asset-info .el-icon { color: var(--de-primary); font-size: var(--de-fs-4); }
.asset-name {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: var(--de-fs-2);
  color: var(--de-text-1);
}
.asset-meta { font-size: var(--de-fs-1); color: var(--de-text-3); flex-shrink: 0; }
</style>
