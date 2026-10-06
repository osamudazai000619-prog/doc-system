<!-- ============================================================
     FileStatusTable.vue —— 文件解析状态表格
     作用：
       1. 显示后端返回的每个文件的解析状态
       2. 状态用彩色标签区分
       3. 支持点击"查看正文"触发预览
     ============================================================ -->

<template>
  <el-card class="status-card" shadow="never">

    <!-- ============ 卡片头部 ============ -->
    <template #header>
      <div class="card-header">
        <div class="card-title">
          <el-icon><DataAnalysis /></el-icon>
          <span>文件解析状态</span>
        </div>
        <el-tag v-if="files.length > 0" type="info" size="small" round>
          共 {{ files.length }} 个
        </el-tag>
      </div>
    </template>

    <!-- ============ 表格 ============ -->
    <el-table
      :data="files"
      stripe
      border
      style="width: 100%"
      :header-cell-style="{ background: 'var(--de-surface-2)', color: 'var(--de-text-1)', fontWeight: 600 }"
    >
      <!-- 序号列 -->
      <el-table-column
        type="index"
        label="序号"
        width="70"
        align="center"
      />

      <!-- 文件名列 -->
      <el-table-column
        prop="filename"
        label="文件名"
        min-width="200"
        show-overflow-tooltip
      >
        <template #default="{ row }">
          <div class="filename-cell">
            <el-icon class="file-icon"><Document /></el-icon>
            <span>{{ row.filename }}</span>
          </div>
        </template>
      </el-table-column>

      <!-- 文件类型列 -->
      <el-table-column
        prop="role"
        label="文件类型"
        width="110"
        align="center"
      >
        <template #default="{ row }">
          <el-tag
            :type="getRoleInfo(row.role).type"
            effect="plain"
            size="small"
            round
          >
            {{ getRoleInfo(row.role).text }}
          </el-tag>
        </template>
      </el-table-column>

      <!-- 状态列：error 时直接显示后端返回的报错原因，其余显示状态标签 -->
      <el-table-column
        prop="status"
        label="状态"
        min-width="180"
      >
        <template #default="{ row }">
          <span
            v-if="row.status === 'error'"
            class="error-text"
            :title="row.error"
          >
            <el-icon><WarningFilled /></el-icon>
            {{ row.error || '解析失败' }}
          </span>
          <el-tag
            v-else
            :type="getStatusInfo(row.status).type"
            effect="light"
            round
          >
            {{ getStatusInfo(row.status).text }}
          </el-tag>
        </template>
      </el-table-column>

      <!-- 操作列 -->
      <el-table-column
        label="操作"
        width="140"
        align="center"
      >
        <template #default="{ row }">
          <!-- 只有 success 才有正文可看 -->
          <el-button
            v-if="row.status === 'success'"
            type="primary"
            size="small"
            text
            @click="handlePreview(row)"
          >
            <el-icon><View /></el-icon>
            <span>查看正文</span>
          </el-button>
          <span v-else class="no-action">—</span>
        </template>
      </el-table-column>

      <!-- 空状态 -->
      <template #empty>
        <el-empty description="暂无文件" :image-size="80" />
      </template>
    </el-table>

  </el-card>
</template>

<script setup>
// ============================================================
// Props 定义
// ============================================================
defineProps({
  // 上传返回的文件列表：[{ filename, status, content, role, error }]
  files: {
    type: Array,
    default: () => [],
  },
})

// ============================================================
// Emits 定义
// ============================================================
const emit = defineEmits(['preview'])

// ============================================================
// 状态映射：把 status 字符串转成"文字 + 颜色"
// ============================================================
function getStatusInfo(status) {
  const map = {
    success:     { text: '解析成功', type: 'success' },
    empty:       { text: '内容为空', type: 'warning' },
    unsupported: { text: '格式不支持', type: 'danger' },
    error:       { text: '解析失败', type: 'danger' },
  }
  // 未知状态给一个灰色兜底
  return map[status] || { text: '未知', type: 'info' }
}

// ============================================================
// 文件角色映射：把后端返回的 role 转成"文字 + 标签颜色"
// ============================================================
function getRoleInfo(role) {
  const map = {
    target:   { text: '目标文档', type: 'primary' },
    template: { text: '模板文件', type: 'warning' },
  }
  return map[role] || { text: '未知', type: 'info' }
}

// ============================================================
// 点击"查看正文" → 通知父组件
// ============================================================
function handlePreview(row) {
  emit('preview', row)
}
</script>

<style scoped>
.status-card {
  border-radius: var(--de-r-sm);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.card-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: var(--de-fs-4);
  font-weight: 600;
  color: var(--de-text-1);
}

.filename-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}

.file-icon {
  color: var(--de-primary);
  flex-shrink: 0;
}

.no-action {
  color: var(--de-text-3);
}

/* error 状态：报错原因顶替状态标签，红色 + 省略号 + 悬停看全文 */
.error-text {
  display: flex;
  align-items: center;
  gap: 4px;
  color: var(--de-danger);
  font-size: var(--de-fs-2);
  line-height: 1.4;
}
.error-text .el-icon {
  flex-shrink: 0;
}
.error-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>