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

    <!-- ============ 卡片头部：标题 + 清空按钮 ============ -->
    <template #header>
      <div class="card-header">
        <div class="card-title">
          <el-icon><Folder /></el-icon>
          <span>{{ title }}</span>
          <el-tag v-if="files.length > 0" type="info" size="small" round>
            已选 {{ files.length }} 个
          </el-tag>
        </div>
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
.upload-card {
  border-radius: 8px;
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
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

/* ==================== 上传区域 ==================== */
.upload-area {
  width: 100%;
}

/* 让 el-upload 的拖拽区域占满宽度 */
.upload-area :deep(.el-upload) {
  width: 100%;
}

.upload-area :deep(.el-upload-dragger) {
  width: 100%;
  padding: 32px 16px;
  border-radius: 6px;
  transition: border-color 0.2s, background-color 0.2s;
}

/* hover 时加深边框 */
.upload-area :deep(.el-upload-dragger:hover) {
  border-color: #409eff;
  background-color: #f0f9ff;
}

.upload-icon {
  font-size: 48px;
  color: #c0c4cc;
  margin-bottom: 12px;
}

.upload-text {
  font-size: 14px;
  color: #606266;
}

.upload-text em {
  color: #409eff;
  font-style: normal;
}

.upload-tip {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
}

/* ==================== 文件列表 ==================== */
.file-list {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.file-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background-color: #f5f7fa;
  border-radius: 4px;
  transition: background-color 0.2s;
}

.file-item:hover {
  background-color: #ecf5ff;
}

.file-item-left {
  display: flex;
  align-items: center;
  gap: 8px;
  overflow: hidden;   /* 溢出裁剪，让文件名太长时显示省略号 */
  flex: 1;
}

.file-icon {
  color: #409eff;
  flex-shrink: 0;
}

.file-name {
  font-size: 14px;
  color: #303133;
  white-space: nowrap;      /* 不换行 */
  overflow: hidden;         /* 超出隐藏 */
  text-overflow: ellipsis;  /* 显示省略号 */
}
</style>