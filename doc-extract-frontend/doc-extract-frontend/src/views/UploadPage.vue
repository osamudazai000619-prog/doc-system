<!-- ============================================================
     UploadPage.vue —— 上传文档页面（正式版 + 5.2 loading 优化）
     ============================================================ -->

<template>
  <div class="upload-page">

    <!-- 顶部说明卡 -->
    <el-card class="intro-card" shadow="never">
      <div class="intro-content">
        <el-icon class="intro-icon"><InfoFilled /></el-icon>
        <div class="intro-text">
          <div class="intro-title">上传文档</div>
          <div class="intro-desc">
            请先上传<strong>目标文档</strong>（要提取信息的文件）和
            <strong>模板文件</strong>（要填充的 Word 或 Excel）。
            支持格式：docx / txt / md / xlsx / pdf。
          </div>
        </div>
      </div>
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

      <FileUploadCard
        title="模板文件"
        tip="支持 .docx / .xlsx，可多选"
        accept=".docx,.xlsx"
        :files="fileStore.templateFiles"
        @add="onAddTemplate"
        @remove="onRemoveTemplate"
        @clear="onClearTemplate"
      />
    </div>

    <!-- 操作按钮区 -->
    <el-card class="action-card" shadow="never">
      <div class="action-bar">

        <div class="action-left">
          <el-button
            type="success"
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

          <span v-if="!canUpload" class="hint">
            请至少选择一个目标文档
          </span>
          <span v-else-if="uploading" class="hint hint-info">
            模拟上传中，请稍候……
          </span>
          <span v-else-if="fileStore.hasUploaded" class="hint hint-success">
            解析完成，共 {{ fileStore.validTargetFiles.length }} 个目标文档可用
          </span>
        </div>

        <div class="action-right">
          <el-button
            type="primary"
            :disabled="!canGoNext || uploading"
            @click="handleNext"
          >
            <span>下一步：设置字段</span>
            <el-icon><ArrowRight /></el-icon>
          </el-button>
        </div>

      </div>
    </el-card>

    <!-- 文件解析状态表格（带 loading 遮罩） -->
    <div
      v-if="fileStore.hasUploaded"
      v-loading="uploading"
      element-loading-text="正在解析文档..."
    >
      <FileStatusTable
        :files="fileStore.allFiles"
        @preview="handlePreview"
      />
    </div>

    <!-- 内嵌预览区 -->
    <div v-if="previewFile" class="preview-wrapper">
      <div class="preview-header-bar">
        <div class="preview-label">
          <el-icon><View /></el-icon>
          <span>正文预览</span>
        </div>
        <el-button
          type="primary"
          text
          size="small"
          @click="previewFile = null"
        >
          <el-icon><Close /></el-icon>
          <span>关闭预览</span>
        </el-button>
      </div>
      <DocumentPreview
        mode="inline"
        :filename="previewFile.filename"
        :content="previewFile.content"
      />
    </div>

  </div>
</template>

<script setup>
import request from '@/api/request'
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { useFileStore } from '@/stores/fileStore'
import FileUploadCard from '@/components/FileUploadCard.vue'
import FileStatusTable from '@/components/FileStatusTable.vue'
import DocumentPreview from '@/components/DocumentPreview.vue'

// ============================================================
// 依赖初始化
// ============================================================
const router = useRouter()
const fileStore = useFileStore()

// ============================================================
// 本地状态
// ============================================================
const uploading = ref(false)
const previewFile = ref(null)

// ============================================================
// 计算属性
// ============================================================
const canUpload = computed(() => fileStore.targetFiles.length > 0)
const canGoNext = computed(() => fileStore.validTargetFiles.length > 0)

// ============================================================
// 目标文档相关操作
// ============================================================
function onAddTarget(files) {
  fileStore.addFile('target', files)
}

function onRemoveTarget(filename) {
  fileStore.removeFile('target', filename)
}

function onClearTarget() {
  fileStore.targetFiles.splice(0)
}

// ============================================================
// 模板文件相关操作
// ============================================================
function onAddTemplate(files) {
  fileStore.addFile('template', files)
}

function onRemoveTemplate(filename) {
  fileStore.removeFile('template', filename)
}

function onClearTemplate() {
  fileStore.templateFiles.splice(0)
}

// ============================================================
// 上传并解析（带防重入）
// ============================================================
async function handleUpload() {
  // ★ 防重入：如果正在上传，直接 return
  if (uploading.value) return

  uploading.value = true

  try {
    const formData = new FormData()

    fileStore.targetFiles.forEach((file) => {
      formData.append('target_files', file)
    })

    fileStore.templateFiles.forEach((file) => {
      formData.append('template_files', file)
    })

    const data = await request.post('/upload', formData)
    fileStore.setAllFiles(data)

    const successCount = data.filter((f) => f.status === 'success').length
    const otherCount = data.length - successCount

    if (otherCount > 0) {
      ElMessage.warning(
        `解析完成：成功 ${successCount} 个，其他 ${otherCount} 个（请查看状态表）`
      )
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

// ============================================================
// 清空所有
// ============================================================
async function handleClearAll() {
  try {
    await ElMessageBox.confirm(
      '确定要清空所有已上传的文件和解析结果吗？',
      '提示',
      {
        type: 'warning',
        confirmButtonText: '确定清空',
        cancelButtonText: '取消',
      }
    )
    fileStore.clearAll()
    previewFile.value = null
    ElMessage.success('已清空')
  } catch {
    // 用户取消，什么都不做
  }
}

// ============================================================
// 点击"查看正文"
// ============================================================
function handlePreview(file) {
  previewFile.value = file
  setTimeout(() => {
    const el = document.querySelector('.preview-wrapper')
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }, 50)
}

// ============================================================
// 下一步
// ============================================================
function handleNext() {
  if (!canGoNext.value) {
    ElMessage.warning('请先上传并解析至少 1 个目标文档')
    return
  }
  router.push('/extract')
}
</script>

<style scoped>
.upload-page {
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
.intro-desc { font-size: 14px; color: #606266; line-height: 1.6; }
.intro-desc strong { color: #409eff; }

/* ==================== 两个上传卡片并排 ==================== */
.upload-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
@media (max-width: 900px) {
  .upload-row { grid-template-columns: 1fr; }
}

/* ==================== 操作按钮区 ==================== */
.action-card { border-radius: 8px; }
.action-bar { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; }
.action-left { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.action-right { display: flex; align-items: center; gap: 12px; }

.hint { font-size: 13px; color: #909399; }
.hint-info { color: #409eff; }
.hint-success { color: #67c23a; }

/* ==================== 预览区 ==================== */
.preview-wrapper { display: flex; flex-direction: column; gap: 8px; }
.preview-header-bar {
  display: flex; align-items: center; justify-content: space-between;
  padding: 8px 16px; background-color: #ecf5ff;
  border-radius: 6px; border: 1px solid #d9ecff;
}
.preview-label { display: flex; align-items: center; gap: 6px; font-size: 14px; font-weight: 600; color: #409eff; }
</style>