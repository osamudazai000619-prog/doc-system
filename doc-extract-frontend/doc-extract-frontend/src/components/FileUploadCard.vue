<!-- ============================================================
     FileUploadCard.vue —— 通用文件上传卡片
     特性：
       1. 支持点击或拖拽上传
       2. 显示已选文件列表，可单个删除
       3. 支持一键清空
       4. 标题、提示、格式限制、是否多选均可配置
       5. 通过 emit 通知父组件，不直接操作 store
     ============================================================ -->

<template>
  <el-card class="upload-card" shadow="never">

    <!-- ============ 卡片头部：标题 + 卡片级操作 ============ -->
    <template #header>
      <div class="card-header">
        <div class="card-title">
          <el-icon><Folder /></el-icon>
          <span>{{ title }}</span>
          <el-tag v-if="files.length > 0" type="info" size="small" round>
            已选 {{ files.length }} 个
          </el-tag>
        </div>
        <div class="card-actions">
          <!-- 交给使用方插入卡片级操作（例如「从文件库选择模板」） -->
          <slot name="header-actions" />
          <el-button
            v-if="files.length > 0"
            type="danger"
            size="small"
            plain
            @click="handleClear"
          >
            清空
          </el-button>
        </div>
      </div>
    </template>

    <!-- ============ 上传区域 ============ -->
    <el-upload
      ref="uploadRef"
      class="upload-area"
      drag
      :accept="accept"
      :multiple="multiple"
      :auto-upload="false"
      :show-file-list="false"
      :on-change="handleFileChange"
    >
      <el-icon class="upload-icon"><UploadFilled /></el-icon>
      <div class="upload-text">
        将文件拖到此处，或<em>点击上传</em>
      </div>
      <div class="upload-tip">{{ tip }}</div>
    </el-upload>

    <!-- ============ 已选文件列表 ============ -->
    <div v-if="files.length > 0" class="file-list">
      <div
        v-for="file in files"
        :key="file.name"
        class="file-item"
      >
        <div class="file-item-left">
          <el-icon class="file-icon"><Document /></el-icon>
          <span class="file-name" :title="file.name">{{ file.name }}</span>
        </div>
        <el-button
          type="danger"
          size="small"
          text
          @click="handleRemove(file.name)"
        >
          <el-icon><Close /></el-icon>
        </el-button>
      </div>
    </div>

  </el-card>
</template>

<script setup>
import { ref } from 'vue'

// ============================================================
// Props 定义
// ============================================================
const props = defineProps({
  // 卡片标题
  title: {
    type: String,
    default: '上传文件',
  },
  // 上传区域下方的提示文字
  tip: {
    type: String,
    default: '',
  },
  // 文件类型限制（HTML accept 语法）
  accept: {
    type: String,
    default: '.txt,.md,.docx,.xlsx,.pdf',
  },
  // 是否允许多选
  multiple: {
    type: Boolean,
    default: true,
  },
  // 已选文件列表（由父组件传入）
  files: {
    type: Array,
    default: () => [],
  },
})

// ============================================================
// Emits 定义
// ============================================================
const emit = defineEmits(['add', 'remove', 'clear'])

// ============================================================
// el-upload 组件的引用
// ============================================================
// 我们需要它来清空内部的文件列表（show-file-list=false 时看不到，
// 但内部仍维护着，多次上传会累积）
const uploadRef = ref(null)

// ============================================================
// 事件处理
// ============================================================

/**
 * 用户选择文件后触发
 * 注意：el-upload 的 on-change 在"每次选一个文件"时都会触发，
 * 多选时会被调用多次，参数格式为 { file, fileList }
 */
function handleFileChange(file) {
  // file 是 el-upload 包装过的对象，真正的 File 在 file.raw
  const rawFile = file.raw
  if (!rawFile) return

  // 通知父组件：新文件来了
  emit('add', [rawFile])
}

/**
 * 删除单个文件
 */
function handleRemove(filename) {
  emit('remove', filename)
}

/**
 * 清空整张卡片
 */
function handleClear() {
  // 清空 el-upload 内部的列表
  if (uploadRef.value) {
    uploadRef.value.clearFiles()
  }
  emit('clear')
}
</script>

<style scoped>
/* ==================== 卡片 ==================== */
/* 卡片与拖拽区撑满父容器高度，避免页面下方出现大片空白 */
.upload-card {
  border-radius: var(--de-r-md);
  display: flex;
  flex-direction: column;
  height: 100%;
}
.upload-card :deep(.el-card__body) {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* ==================== 卡片头部 ==================== */
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  display: flex;
  align-items: center;
  gap: var(--de-s2);
  font-size: var(--de-fs-4);
  font-weight: 650;
  color: var(--de-text-1);
}
.card-title .el-icon { color: var(--de-primary); font-size: var(--de-fs-5); }

.card-actions {
  display: flex;
  align-items: center;
  gap: var(--de-s2);
}

/* ==================== 上传区域 ==================== */
.upload-area {
  width: 100%;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

/* 让 el-upload 的拖拽区域占满宽度与剩余高度 */
.upload-area :deep(.el-upload) {
  width: 100%;
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.upload-area :deep(.el-upload-dragger) {
  width: 100%;
  height: 100%;
  min-height: 180px;
  padding: var(--de-s6) var(--de-s4);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  border: 1.5px dashed var(--de-border-strong);
  border-radius: var(--de-r-md);
  background: var(--de-surface-2);
  transition: border-color 0.2s, background-color 0.2s;
}

/* hover 时切到品牌色 */
.upload-area :deep(.el-upload-dragger:hover) {
  border-color: var(--de-primary);
  background: var(--de-primary-soft);
}

.upload-icon {
  font-size: 46px;
  color: var(--de-primary);
  opacity: 0.85;
  margin-bottom: var(--de-s3);
}

.upload-text {
  font-size: var(--de-fs-3);
  color: var(--de-text-2);
}

.upload-text em {
  color: var(--de-primary);
  font-style: normal;
  font-weight: 650;
}

.upload-tip {
  font-size: var(--de-fs-1);
  color: var(--de-text-3);
  margin-top: var(--de-s2);
}

/* ==================== 已选文件列表 ==================== */
.file-list {
  margin-top: var(--de-s4);
  display: flex;
  flex-direction: column;
  gap: var(--de-s2);
}

.file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--de-s2) var(--de-s3);
  background: var(--de-surface-2);
  border: 1px solid var(--de-border);
  border-radius: var(--de-r-sm);
  transition: border-color 0.18s, background-color 0.18s;
}

.file-item:hover {
  border-color: var(--de-primary-line);
  background: var(--de-surface-1);
}

.file-item-left {
  display: flex;
  align-items: center;
  gap: var(--de-s2);
  overflow: hidden;
  flex: 1;
}

.file-icon {
  color: var(--de-primary);
  flex-shrink: 0;
}

.file-name {
  font-size: var(--de-fs-2);
  color: var(--de-text-1);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
