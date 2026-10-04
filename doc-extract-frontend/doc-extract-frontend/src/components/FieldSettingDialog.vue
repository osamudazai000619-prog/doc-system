<!-- ============================================================
     FieldSettingDialog.vue —— 字段设置弹窗
     功能：
       1. 展示 8 组预设字段，可点击添加
       2. 展示已选字段，可点击删除
       3. 支持自定义字段输入
       4. 最多 10 个字段上限
       5. 取消时恢复打开前的字段
       6. 确定时写入 fieldStore
       7. 一键解析并填充模板表头
     ============================================================ -->

<template>
  <el-dialog
    :model-value="visible"
    title="设置提取字段"
    width="720px"
    top="6vh"
    :close-on-click-modal="false"
    @update:model-value="handleVisibleChange"
  >

    <!-- ==================================================
         已选字段区
         ================================================== -->
    <div class="section">
      <div class="section-title">
        <span>已选字段</span>
        <el-tag
          :type="localFields.length >= maxFields ? 'danger' : 'info'"
          size="small"
          round
        >
          {{ localFields.length }} / {{ maxFields }}
        </el-tag>
      </div>

      <div class="selected-list">
        <el-tag
          v-for="f in localFields"
          :key="f"
          closable
          size="large"
          effect="dark"
          @close="removeField(f)"
        >
          {{ f }}
        </el-tag>
        <span v-if="localFields.length === 0" class="empty-hint">
          还没有选择字段，请从下方预设中选择，或输入自定义字段
        </span>
      </div>
    </div>

    <!-- ==================================================
         预设字段区（8 组）
         ================================================== -->
    <div class="section">
      <div class="section-header">
        <div class="section-title">
          <span>预设字段</span>
          <span class="section-subtitle">点击即可添加</span>
        </div>
        <el-button
          size="small"
          type="primary"
          plain
          :loading="loadingHeaders"
          @click="handleParseTemplate"
        >
          一键解析表头
        </el-button>
      </div>

      <div
        v-for="group in presetGroups"
        :key="group.key"
        class="preset-group"
      >
        <div class="group-label">
          <el-icon><component :is="group.icon" /></el-icon>
          <span>{{ group.label }}</span>
        </div>
        <div class="group-fields">
          <el-tag
            v-for="field in group.fields"
            :key="field"
            size="default"
            :type="localFields.includes(field) ? 'success' : 'info'"
            :effect="localFields.includes(field) ? 'dark' : 'plain'"
            :class="{ 'tag-clickable': !isDisabled(field), 'tag-disabled': isDisabled(field) }"
            @click="toggleField(field)"
          >
            {{ field }}
          </el-tag>
        </div>
      </div>
    </div>

    <!-- ==================================================
         自定义字段输入
         ================================================== -->
    <div class="section">
      <div class="section-title">
        <span>自定义字段</span>
      </div>

      <div class="custom-input-row">
        <el-input
          v-model="customInput"
          placeholder="输入字段名，例如：合同编号"
          maxlength="30"
          :disabled="localFields.length >= maxFields"
          clearable
          @keyup.enter="handleAddCustom"
        />
        <el-button
          type="primary"
          :disabled="localFields.length >= maxFields || !customInput.trim()"
          @click="handleAddCustom"
        >
          <el-icon><Plus /></el-icon>
          <span>添加</span>
        </el-button>
      </div>

      <div v-if="localFields.length >= maxFields" class="limit-hint">
        已达到 {{ maxFields }} 个字段上限，如需添加请先删除部分字段
      </div>
    </div>

    <!-- ==================================================
         底部按钮
         ================================================== -->
    <template #footer>
      <el-button @click="handleCancel">取消</el-button>
      <el-button type="primary" @click="handleConfirm">确定</el-button>
    </template>

  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useFieldStore, PRESET_GROUPS } from '@/stores/fieldStore'
import { getTemplateHeaders } from '@/api/extract'

// ============================================================
// Props / Emits
// ============================================================
const props = defineProps({
  visible: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['update:visible'])

// ============================================================
// 依赖
// ============================================================
const fieldStore = useFieldStore()
const presetGroups = PRESET_GROUPS
const maxFields = fieldStore.maxFields

// ============================================================
// 本地状态
// ============================================================
// 编辑缓冲：弹窗打开时复制 store 里的字段列表
const localFields = ref([])

// 自定义输入框的内容
const customInput = ref('')

// 解析模板表头时的加载状态
const loadingHeaders = ref(false)

// ============================================================
// 监听弹窗打开，复制 store 数据到本地副本
// ============================================================
watch(
  () => props.visible,
  (val) => {
    if (val) {
      // 打开时：复制
      localFields.value = [...fieldStore.fields]
      customInput.value = ''
    }
  }
)

// ============================================================
// 判断某个预设字段是否"不可用"
// ============================================================
// 规则：
//   1. 已经在已选列表里 → 可以点（用于取消选择）
//   2. 未在已选列表，但已满 10 个 → 禁用
//   3. 其他情况 → 可点
function isDisabled(field) {
  if (localFields.value.includes(field)) return false
  return localFields.value.length >= maxFields
}

// ============================================================
// 点击预设字段：切换选中状态
// ============================================================
function toggleField(field) {
  if (localFields.value.includes(field)) {
    // 已选 → 取消
    removeField(field)
  } else {
    // 未选 → 添加
    addField(field)
  }
}

// ============================================================
// 添加字段（内部统一入口）
// ============================================================
function addField(field) {
  const trimmed = (field || '').trim()
  if (!trimmed) return

  if (localFields.value.includes(trimmed)) {
    ElMessage.warning(`字段 "${trimmed}" 已存在`)
    return
  }

  if (localFields.value.length >= maxFields) {
    ElMessage.warning(`最多只能设置 ${maxFields} 个字段`)
    return
  }

  localFields.value.push(trimmed)
}

// ============================================================
// 删除字段
// ============================================================
function removeField(field) {
  localFields.value = localFields.value.filter((f) => f !== field)
}

// ============================================================
// 添加自定义字段
// ============================================================
function handleAddCustom() {
  const trimmed = customInput.value.trim()
  if (!trimmed) return

  if (localFields.value.includes(trimmed)) {
    ElMessage.warning(`字段 "${trimmed}" 已存在`)
    return
  }

  if (localFields.value.length >= maxFields) {
    ElMessage.warning(`最多只能设置 ${maxFields} 个字段`)
    return
  }

  localFields.value.push(trimmed)
  customInput.value = ''
  ElMessage.success(`已添加：${trimmed}`)
}

// ============================================================
// 一键解析模板表头：调后端 /extract/template-headers，
// 把模板表头批量填入已选字段（自动跳过重复与超上限）
// ============================================================
async function handleParseTemplate() {
  if (loadingHeaders.value) return
  loadingHeaders.value = true

  try {
    const res = await getTemplateHeaders()
    const headers = res.headers || []

    if (headers.length === 0) {
      ElMessage.warning('未找到有效的模板文件或无法解析表头')
      return
    }

    let addedCount = 0
    let skippedCount = 0
    for (const header of headers) {
      if (localFields.value.includes(header)) {
        skippedCount++
        continue
      }
      if (localFields.value.length >= maxFields) {
        ElMessage.warning(`已达到 ${maxFields} 个字段上限，已停止自动添加。`)
        break
      }
      localFields.value.push(header)
      addedCount++
    }

    if (addedCount > 0) {
      ElMessage.success(`成功添加 ${addedCount} 个字段！`)
    } else {
      ElMessage.info('未添加新字段，可能是字段已存在或已达上限。')
    }
  } catch (error) {
    console.error('解析表头失败:', error)
    ElMessage.error('解析表头失败，请稍后重试')
  } finally {
    loadingHeaders.value = false
  }
}

// ============================================================
// 取消：直接关闭，不写 store
// ============================================================
function handleCancel() {
  emit('update:visible', false)
}

// ============================================================
// 确定：把 localFields 写入 store
// ============================================================
function handleConfirm() {
  fieldStore.setFields(localFields.value)
  ElMessage.success(`已保存 ${localFields.value.length} 个字段`)
  emit('update:visible', false)
}

// ============================================================
// 关闭事件（点 × 或遮罩）
// ============================================================
function handleVisibleChange(val) {
  emit('update:visible', val)
}
</script>

<style scoped>
/* ==================== 通用区块 ==================== */
.section {
  margin-bottom: 20px;
}

/* 预设字段区头部：标题 + 一键解析按钮 的弹性布局 */
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid #ebeef5;
}

.section-header .section-title {
  margin-bottom: 0;
  padding-bottom: 0;
  border-bottom: none;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 10px;
  padding-bottom: 6px;
  border-bottom: 1px solid #ebeef5;
}

.section-subtitle {
  font-size: 12px;
  font-weight: 400;
  color: #909399;
}

/* ==================== 已选字段区 ==================== */
.selected-list {
  min-height: 40px;
  padding: 8px;
  background-color: #fafafa;
  border-radius: 4px;
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}

.selected-list .el-tag {
  cursor: default;
}

.empty-hint {
  font-size: 13px;
  color: #c0c4cc;
}

/* ==================== 预设字段区 ==================== */
.preset-group {
  margin-bottom: 12px;
}

.group-label {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: #606266;
  margin-bottom: 8px;
}

.group-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag-clickable {
  cursor: pointer;
  transition: transform 0.1s;
}

.tag-clickable:hover {
  transform: translateY(-1px);
}

.tag-disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* ==================== 自定义输入区 ==================== */
.custom-input-row {
  display: flex;
  gap: 10px;
}

.custom-input-row .el-input {
  flex: 1;
}

.limit-hint {
  font-size: 12px;
  color: #e6a23c;
  margin-top: 8px;
}
</style>