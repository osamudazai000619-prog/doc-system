<!-- ============================================================
     ExtractPage.vue —— 字段设置与提示词（5.3 交互优化）
     ============================================================ -->

<template>
  <div
    class="extract-page"
    v-loading="resultStore.extracting"
    element-loading-text="AI 正在提取信息，请稍候..."
  >

    <!-- 顶部说明 -->
    <el-card class="intro-card" shadow="never">
      <div class="intro-content">
        <el-icon class="intro-icon"><Setting /></el-icon>
        <div class="intro-text">
          <div class="intro-title">设置提取字段与提示词</div>
          <div class="intro-desc">
            选择需要从文档中提取的字段，并可输入提示词引导大语言模型。
            字段和提示词<strong>至少填写一项</strong>。
            已在上一步选择方案的，字段与提示词已自动填入，可直接修改。
          </div>
        </div>
      </div>
    </el-card>

    <!-- ==================================================
         字段设置卡（标题左 + 已选字段下）
         ================================================== -->
    <el-card class="section-card" shadow="never">
      <template #header>
        <div class="section-header">
          <div class="section-title">
            <el-icon><Postcard /></el-icon>
            <span>提取字段</span>
            <el-tag
              :type="fieldStore.fieldCount > 0 ? 'success' : 'info'"
              size="small"
              round
            >
              {{ fieldStore.fieldCount }} / {{ fieldStore.maxFields }}
            </el-tag>
          </div>
          <el-button
            type="primary"
            size="small"
            :disabled="resultStore.extracting"
            @click="dialogVisible = true"
          >
            <el-icon><Setting /></el-icon>
            <span>设置字段</span>
          </el-button>
        </div>
      </template>

      <!-- 已选字段标签 -->
      <div v-if="fieldStore.fieldCount > 0" class="field-tags">
        <el-tag
          v-for="f in fieldStore.fields"
          :key="f"
          closable
          size="large"
          effect="dark"
          type="success"
          :disable-transitions="false"
          @close="handleRemoveField(f)"
        >
          {{ f }}
        </el-tag>
      </div>

      <!-- 空状态：虚线框，引导用户点击 -->
      <div
        v-else
        class="empty-hint-box"
        @click="dialogVisible = true"
      >
        <el-icon><Plus /></el-icon>
        <span>点击此处或右上角"设置字段"添加字段</span>
      </div>
    </el-card>

    <!-- ==================================================
         提示词卡
         ================================================== -->
    <el-card class="section-card" shadow="never">
      <template #header>
        <div class="section-header">
          <div class="section-title">
            <el-icon><ChatLineSquare /></el-icon>
            <span>提示词</span>
            <el-tag size="small" type="info" round>可选</el-tag>
          </div>
          <span class="char-count">{{ prompt.length }} 字</span>
        </div>
      </template>

      <el-input
        v-model="prompt"
        type="textarea"
        :rows="4"
        maxlength="500"
        show-word-limit
        :disabled="resultStore.extracting"
        placeholder="请输入提示词，例如：请从文档中提取项目名称和负责人信息，未找到的填&quot;未找到&quot;。"
      />
    </el-card>

    <!-- ==================================================
         待处理文档列表
         ================================================== -->
    <el-card class="section-card" shadow="never">
      <template #header>
        <div class="section-header">
          <div class="section-title">
            <el-icon><Files /></el-icon>
            <span>待处理文档</span>
            <el-tag
              :type="validDocs.length > 0 ? 'success' : 'danger'"
              size="small"
              round
            >
              {{ validDocs.length }} 个
            </el-tag>
          </div>
        </div>
      </template>

      <div v-if="validDocs.length > 0" class="doc-list">
        <div
          v-for="doc in validDocs"
          :key="doc.filename"
          class="doc-item"
        >
          <el-icon class="doc-icon"><Document /></el-icon>
          <span class="doc-name">{{ doc.filename }}</span>
          <span class="doc-size">{{ doc.content.length }} 字</span>
        </div>
      </div>

      <el-empty
        v-else
        description="没有可处理的目标文档，请返回上一步上传"
        :image-size="80"
      >
        <el-button type="primary" @click="goBack">
          返回上传页
        </el-button>
      </el-empty>
    </el-card>

    <!-- ==================================================
         底部操作栏
         ================================================== -->
    <div class="action-bar">
      <el-button size="large" :disabled="resultStore.extracting" @click="goBack">
        <el-icon><ArrowLeft /></el-icon>
        <span>上一步：上传文档</span>
      </el-button>

      <el-button
        type="primary"
        size="large"
        :disabled="!canExtract || resultStore.extracting"
        :loading="resultStore.extracting"
        @click="handleExtract"
      >
        <span>{{ resultStore.extracting ? '提取中...' : '开始提取' }}</span>
        <el-icon v-if="!resultStore.extracting"><ArrowRight /></el-icon>
      </el-button>
    </div>

    <FieldSettingDialog v-model:visible="dialogVisible" />

  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'

import { useFileStore } from '@/stores/fileStore'
import { useFieldStore } from '@/stores/fieldStore'
import { useResultStore } from '@/stores/resultStore'
import FieldSettingDialog from '@/components/FieldSettingDialog.vue'
import request from '@/api/request'

// ============================================================
// 依赖
// ============================================================
const router = useRouter()
const fileStore = useFileStore()
const fieldStore = useFieldStore()
const resultStore = useResultStore()

// ============================================================
// 本地状态
// ============================================================
const dialogVisible = ref(false)
// 提示词初始值取 resultStore 快照：一阶段选方案/一键填充/草稿恢复时已写入 store
const prompt = ref(resultStore.prompt || '')

// ============================================================
// 计算属性
// ============================================================
const validDocs = computed(() => fileStore.validTargetFiles)

const canExtract = computed(() => {
  if (validDocs.value.length === 0) return false
  const hasField = fieldStore.fieldCount > 0
  const hasPrompt = prompt.value.trim().length > 0
  return hasField || hasPrompt
})

// ============================================================
// 交互
// ============================================================
// ★ 删除字段：二次确认
async function handleRemoveField(field) {
  try {
    await ElMessageBox.confirm(
      `确定要移除字段「${field}」吗？`,
      '提示',
      {
        type: 'warning',
        confirmButtonText: '移除',
        cancelButtonText: '取消',
      }
    )
    fieldStore.removeField(field)
    ElMessage.success(`已移除「${field}」`)
  } catch {
    // 用户取消，什么都不做
  }
}

function goBack() {
  router.push('/upload')
}

async function handleExtract() {
  // ★ 防重入
  if (resultStore.extracting) return

  if (validDocs.value.length === 0) {
    ElMessage.error('没有可处理的目标文档')
    return
  }

  const hasField = fieldStore.fieldCount > 0
  const hasPrompt = prompt.value.trim().length > 0

  if (!hasField && !hasPrompt) {
    ElMessage.warning('请至少设置一个字段或输入提示词')
    return
  }

  const payload = {
    prompt: prompt.value.trim(),
    fields: [...fieldStore.fields],
    documents: validDocs.value.map((d) => ({
      filename: d.filename,
      content: d.content,
    })),
    scheme_id: resultStore.schemeId ? String(resultStore.schemeId) : '',
  }

  console.log('[发起提取] 参数：', {
    prompt: payload.prompt,
    fields: payload.fields,
    documentCount: payload.documents.length,
  })

  resultStore.extracting = true

  try {
    const data = await request.post('/extract', payload)

    resultStore.setResults(data)
    resultStore.setPrompt(payload.prompt)
    resultStore.setFields(payload.fields)
    // 后端已为本次提取落任务历史，task_id 随响应带回（每条 item 相同）
    resultStore.setTaskId(data?.[0]?.task_id || '')

    ElMessage.success(`提取完成，共 ${resultStore.totalRecords} 条记录`)

    router.push('/result')
  } catch (err) {
    console.error('[提取失败]', err)
  } finally {
    resultStore.extracting = false
  }
}
</script>

<style scoped>
.extract-page {
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
.intro-desc { font-size: var(--de-fs-3); color: var(--de-text-2); line-height: 1.6; }
.intro-desc strong { color: var(--de-warning); }

/* ==================== 通用 section 卡片 ==================== */
.section-card { border-radius: var(--de-r-sm); }
.section-header { display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px; }
.section-title { display: flex; align-items: center; gap: 8px; font-size: var(--de-fs-4); font-weight: 600; color: var(--de-text-1); }
.char-count { font-size: var(--de-fs-1); color: var(--de-text-3); }

/* ==================== 字段标签区 ==================== */
.field-tags {
  min-height: 48px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
  padding: 4px 0;
}
.field-tags .el-tag {
  cursor: default;
}

/* ==================== 空状态虚线框 ==================== */
.empty-hint-box {
  width: 100%;
  border: 2px dashed var(--de-border-strong);
  border-radius: var(--de-r-xs);
  padding: 24px 16px;
  text-align: center;
  color: var(--de-text-3);
  font-size: var(--de-fs-3);
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s, background-color 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
}
.empty-hint-box:hover {
  border-color: var(--de-primary);
  color: var(--de-primary);
  background-color: var(--de-primary-soft);
}

/* ==================== 文档列表 ==================== */
.doc-list { display: flex; flex-direction: column; gap: 8px; }
.doc-item {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px; background-color: var(--de-surface-2);
  border-radius: var(--de-r-xs); font-size: var(--de-fs-3);
}
.doc-item:hover { background-color: var(--de-primary-soft); }
.doc-icon { color: var(--de-primary); flex-shrink: 0; }
.doc-name { flex: 1; color: var(--de-text-1); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.doc-size { font-size: var(--de-fs-1); color: var(--de-text-3); flex-shrink: 0; }

/* ==================== 底部操作栏 ==================== */
.action-bar { display: flex; justify-content: space-between; align-items: center; padding: 16px 0; }
</style>