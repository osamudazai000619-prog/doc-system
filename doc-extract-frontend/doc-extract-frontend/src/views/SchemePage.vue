<!-- ============================================================
     SchemePage.vue —— 方案管理页
     2 列长方形卡片网格：点击卡片进入编辑，右上角删除；
     顶部「新建方案」。编辑在同页切换（网格 ↔ 表单）。
     ============================================================ -->

<template>
  <div class="scheme-page">

    <!-- ============ 卡片网格视图 ============ -->
    <template v-if="mode === 'grid'">
      <div class="page-topbar">
        <div>
          <div class="page-title">方案管理</div>
          <div class="page-sub">一套方案 = 模板文件 + 提示词 + 提取字段，可在新任务中一键预填</div>
        </div>
        <el-button type="primary" @click="startCreate">
          <el-icon><Plus /></el-icon>
          <span>新建方案</span>
        </el-button>
      </div>

      <div v-loading="loading" class="scheme-grid">
        <div
          v-for="s in schemes"
          :key="s.id"
          class="scheme-card"
          @click="startEdit(s)"
        >
          <!-- 右上角删除（点击不冒泡到卡片） -->
          <el-icon class="card-delete" @click.stop="removeScheme(s)">
            <CircleCloseFilled />
          </el-icon>

          <div class="card-name" :title="s.name">{{ s.name }}</div>

          <div class="card-template">
            <el-icon><Document /></el-icon>
            <span :title="s.template_name">{{ s.template_name || '（未绑定模板）' }}</span>
          </div>

          <div class="card-fields">
            <template v-if="s.fields.length">
              <el-tag
                v-for="f in s.fields.slice(0, 5)" :key="f"
                size="small" type="info" effect="plain"
              >{{ f }}</el-tag>
              <span v-if="s.fields.length > 5" class="card-fields-more">
                +{{ s.fields.length - 5 }}
              </span>
            </template>
            <span v-else class="card-fields-empty">（未设置字段，仅提示词）</span>
          </div>

          <div class="card-prompt" :title="s.prompt">
            {{ s.prompt || '（无提示词）' }}
          </div>

          <div class="card-footer">
            <el-button size="small" text type="primary">
              <el-icon><Edit /></el-icon>
              <span>点击编辑</span>
            </el-button>
            <span v-if="s.last_used_at" class="card-used">最近使用 {{ s.last_used_at }}</span>
          </div>
        </div>
      </div>

      <el-empty
        v-if="!loading && schemes.length === 0"
        description="还没有方案，点击右上角新建一套吧"
      >
        <el-button type="primary" @click="startCreate">
          <el-icon><Plus /></el-icon>
          <span>新建方案</span>
        </el-button>
      </el-empty>
    </template>

    <!-- ============ 编辑 / 新建视图 ============ -->
    <template v-else>
      <div class="page-topbar">
        <div class="page-title">{{ editingId ? '编辑方案' : '新建方案' }}</div>
      </div>

      <el-card class="edit-card" shadow="never">
        <el-form label-width="90px" label-position="left">
          <el-form-item label="方案名称" required>
            <el-input
              v-model="form.name" maxlength="50" show-word-limit
              placeholder="例如：城市经济数据提取"
            />
          </el-form-item>

          <el-form-item label="模板文件">
            <el-select
              v-model="form.template_asset_id"
              placeholder="从文件库选择模板（可不选）"
              clearable
              filterable
              style="width: 100%"
            >
              <el-option
                v-for="a in templateAssets"
                :key="a.id"
                :label="a.original_name"
                :value="a.id"
              />
            </el-select>
          </el-form-item>

          <el-form-item label="提取字段">
            <div class="field-editor">
              <el-tag
                v-for="f in form.fields"
                :key="f" closable size="small"
                @close="form.fields = form.fields.filter((x) => x !== f)"
              >{{ f }}</el-tag>
              <el-input
                v-if="form.fields.length < 10"
                v-model="fieldInput"
                size="small"
                placeholder="输入字段名后回车添加"
                class="field-input"
                @keyup.enter="addField"
              >
                <template #append>
                  <el-button size="small" @click="addField">添加</el-button>
                </template>
              </el-input>
            </div>
          </el-form-item>

          <el-form-item label="提示词">
            <el-input
              v-model="form.prompt"
              type="textarea"
              :rows="5"
              maxlength="500"
              show-word-limit
              placeholder="可选，引导大模型提取的要求，例如：未找到的信息填“未找到”。"
            />
          </el-form-item>
        </el-form>
      </el-card>

      <div class="edit-actions">
        <el-button @click="backToGrid">返回</el-button>
        <el-button type="primary" :loading="saving" @click="submitSave">保存方案</el-button>
      </div>
    </template>

  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { fetchSchemes, saveScheme, deleteScheme } from '@/api/schemes'
import { fetchAssets } from '@/api/assets'

const mode = ref('grid')  // grid / edit
const loading = ref(false)
const saving = ref(false)
const schemes = ref([])
const templateAssets = ref([])

const editingId = ref(null)
const form = ref({ name: '', template_asset_id: null, prompt: '', fields: [] })
const fieldInput = ref('')

async function load() {
  loading.value = true
  try {
    const [schemeRes, assetRes] = await Promise.all([
      fetchSchemes(),
      fetchAssets('template'),
    ])
    schemes.value = schemeRes.items || []
    templateAssets.value = assetRes.items || []
  } finally {
    loading.value = false
  }
}

function startCreate() {
  editingId.value = null
  form.value = { name: '', template_asset_id: null, prompt: '', fields: [] }
  fieldInput.value = ''
  mode.value = 'edit'
}

function startEdit(s) {
  editingId.value = s.id
  form.value = {
    name: s.name,
    template_asset_id: s.template_asset_id,
    prompt: s.prompt,
    fields: [...s.fields],
  }
  fieldInput.value = ''
  mode.value = 'edit'
}

function backToGrid() {
  mode.value = 'grid'
  load()
}

function addField() {
  const name = fieldInput.value.trim()
  if (!name) return
  if (form.value.fields.includes(name)) {
    ElMessage.warning(`字段「${name}」已存在`)
    return
  }
  form.value.fields.push(name)
  fieldInput.value = ''
}

async function submitSave() {
  if (!form.value.name.trim()) {
    ElMessage.warning('请填写方案名称')
    return
  }
  saving.value = true
  try {
    await saveScheme({
      name: form.value.name.trim(),
      prompt: form.value.prompt,
      fields: form.value.fields,
      template_asset_id: form.value.template_asset_id || null,
      scheme_id: editingId.value,
    })
    ElMessage.success(editingId.value ? '方案已更新' : '方案已创建')
    mode.value = 'grid'
    load()
  } catch {
    // 拦截器已提示（如重名 400）
  } finally {
    saving.value = false
  }
}

async function removeScheme(s) {
  try {
    await ElMessageBox.confirm(
      `确定删除方案「${s.name}」吗？历史任务不受影响。`,
      '删除方案',
      { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
    )
  } catch {
    return
  }
  try {
    await deleteScheme(s.id)
    ElMessage.success('方案已删除')
    load()
  } catch {
    // 拦截器已提示
  }
}

onMounted(load)
</script>

<style scoped>
.scheme-page {
  padding: 20px 24px 32px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

/* ===== 顶部栏 ===== */
.page-topbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}
.page-title { font-size: 20px; font-weight: 700; color: #1f2937; }
.page-sub { font-size: 13px; color: #9ca3af; margin-top: 4px; }

/* ===== 卡片网格：一行 2 个，卡片偏长方形 ===== */
.scheme-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}
@media (max-width: 1000px) {
  .scheme-grid { grid-template-columns: 1fr; }
}

.scheme-card {
  position: relative;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 18px 20px 12px;
  min-height: 210px;
  display: flex;
  flex-direction: column;
  cursor: pointer;
  transition: border-color 0.15s, box-shadow 0.15s, transform 0.15s;
}
.scheme-card:hover {
  border-color: #409eff;
  box-shadow: 0 6px 20px rgba(64, 158, 255, 0.12);
  transform: translateY(-2px);
}

.card-delete {
  position: absolute;
  top: 10px;
  right: 12px;
  font-size: 18px;
  color: #c0c4cc;
}
.card-delete:hover { color: #f56c6c; }

.card-name {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
  padding-right: 28px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.card-template {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  font-size: 13px;
  color: #6b7280;
}
.card-template span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.card-fields {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-items: center;
  margin-top: 12px;
}
.card-fields-more { font-size: 12px; color: #9ca3af; }
.card-fields-empty { font-size: 12px; color: #c0c4cc; }

.card-prompt {
  flex: 1;
  margin-top: 10px;
  font-size: 12px;
  color: #9ca3af;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 8px;
  border-top: 1px solid #f3f4f6;
  padding-top: 6px;
}
.card-used { font-size: 11px; color: #c0c4cc; }

/* ===== 编辑视图 ===== */
.edit-card { border-radius: 10px; }
.field-editor {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  align-items: center;
}
.field-input { width: 220px; }
.edit-actions { display: flex; justify-content: flex-end; gap: 10px; }
</style>
