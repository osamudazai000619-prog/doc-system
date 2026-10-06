<!-- ============================================================
     DocumentPreview.vue —— 文档正文预览组件
     两种模式：
       - mode="dialog"：弹窗显示（默认）
       - mode="inline"：内嵌在页面里
     ============================================================ -->

<template>
  <!-- ============================================================
       内嵌模式
       ============================================================ -->
  <div v-if="mode === 'inline'" class="preview-inline">
    <!-- 标题栏 -->
    <div class="preview-header">
      <div class="preview-title">
        <el-icon><Document /></el-icon>
        <span>{{ filename || '未选择文件' }}</span>
      </div>
      <div class="preview-stats">
        共 {{ content.length }} 字 · {{ lineCount }} 行
      </div>
    </div>

    <!-- 正文区 -->
    <div class="preview-content">
      <pre v-if="content">{{ content }}</pre>
      <el-empty v-else description="暂无内容" :image-size="80" />
    </div>
  </div>

  <!-- ============================================================
       弹窗模式
       ============================================================ -->
  <el-dialog
    v-else
    :model-value="visible"
    :title="filename || '文档预览'"
    width="70%"
    top="8vh"
    :close-on-click-modal="false"
    @update:model-value="handleVisibleChange"
  >
    <!-- 顶部统计 -->
    <div class="dialog-stats">
      共 {{ content.length }} 字 · {{ lineCount }} 行
    </div>

    <!-- 正文区 -->
    <div class="preview-content preview-content-dialog">
      <pre v-if="content">{{ content }}</pre>
      <el-empty v-else description="暂无内容" :image-size="80" />
    </div>

    <!-- 底部 -->
    <template #footer>
      <el-button @click="handleVisibleChange(false)">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { computed } from 'vue'

// ============================================================
// Props
// ============================================================
const props = defineProps({
  // 是否显示（弹窗模式用）
  visible: {
    type: Boolean,
    default: false,
  },
  // 文件名
  filename: {
    type: String,
    default: '',
  },
  // 正文内容
  content: {
    type: String,
    default: '',
  },
  // 模式：dialog / inline
  mode: {
    type: String,
    default: 'dialog',
    validator: (v) => ['dialog', 'inline'].includes(v),
  },
})

// ============================================================
// Emits
// ============================================================
const emit = defineEmits(['update:visible'])

// ============================================================
// 计算行数
// ============================================================
const lineCount = computed(() => {
  if (!props.content) return 0
  // 按换行符拆分
  return props.content.split('\n').length
})

// ============================================================
// 关闭弹窗时通知父组件
// ============================================================
function handleVisibleChange(val) {
  emit('update:visible', val)
}
</script>

<style scoped>
/* ==================== 内嵌模式 ==================== */
.preview-inline {
  border: 1px solid var(--de-border);
  border-radius: var(--de-r-xs);
  overflow: hidden;
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background-color: var(--de-surface-2);
  border-bottom: 1px solid var(--de-border);
}

.preview-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: var(--de-fs-3);
  font-weight: 600;
  color: var(--de-text-1);
}

.preview-stats {
  font-size: var(--de-fs-1);
  color: var(--de-text-3);
}

/* ==================== 弹窗模式 ==================== */
.dialog-stats {
  font-size: var(--de-fs-1);
  color: var(--de-text-3);
  margin-bottom: 8px;
  text-align: right;
}

.preview-content-dialog {
  max-height: 60vh;
}

/* ==================== 正文区（两种模式共用样式）==================== */
.preview-content {
  padding: 16px;
  background-color: var(--de-surface-2);
  overflow: auto;
  max-height: 400px;
}

.preview-content pre {
  margin: 0;
  font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
  font-size: var(--de-fs-2);
  line-height: 1.7;
  color: var(--de-text-1);
  /* 保留原始换行和空格 */
  white-space: pre-wrap;
  word-break: break-word;
}
</style>