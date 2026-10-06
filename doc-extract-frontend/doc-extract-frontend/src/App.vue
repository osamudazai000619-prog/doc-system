<!-- ============================================================
     App.vue —— 全屏工作台（左侧边栏 + 右侧工作区）
     侧边栏：新建任务 / 方案管理 / 草稿箱 / 历史任务
     欢迎引导仅首次使用呈现；之后始终处于某个任务上下文中
     ============================================================ -->

<template>
  <div class="app-shell">

    <!-- ==================== 左侧边栏 ==================== -->
    <aside class="sidebar">

      <!-- 品牌区 -->
      <div class="brand">
        <el-icon class="brand-icon"><Document /></el-icon>
        <div class="brand-text">
          <div class="brand-name">文档提取系统</div>
          <div class="brand-sub">基于大语言模型</div>
        </div>
      </div>

      <!-- 新建任务 -->
      <el-button class="new-task-btn" @click="handleNewTask">
        <el-icon class="new-task-icon"><Plus /></el-icon>
        <span>新建任务</span>
      </el-button>

      <!-- 方案管理（点击跳转到方案卡片页） -->
      <div
        class="scheme-entry"
        :class="{ active: route.path === '/schemes' }"
        @click="goSchemes"
      >
        <el-icon class="scheme-entry-icon"><Collection /></el-icon>
        <span class="scheme-entry-name">方案管理</span>
        <span v-if="schemeCount > 0" class="scheme-entry-count">{{ schemeCount }}</span>
        <el-icon class="scheme-entry-arrow"><ArrowRight /></el-icon>
      </div>

      <!-- 草稿箱 -->
      <div class="side-group draft-group">
        <div class="group-label">
          <el-icon><EditPen /></el-icon>
          <span>草稿箱</span>
          <span class="group-count">{{ ws.drafts.length }}</span>
        </div>
        <div class="group-list">
          <div
            v-for="d in ws.drafts"
            :key="d.id"
            class="side-item"
            :class="{ active: ws.currentDraftId === d.id }"
            @click="handleRestore(d)"
          >
            <el-icon class="item-icon"><ChatDotRound /></el-icon>
            <div class="item-text">
              <div class="item-title">{{ d.title }}</div>
              <div class="item-meta">
                {{ stepLabel(d.step) }} · {{ d.file_count }} 文件 / {{ d.field_count }} 字段
              </div>
            </div>
            <el-icon class="item-delete" @click.stop="ws.removeDraft(d)"><Delete /></el-icon>
          </div>
          <el-empty
            v-if="ws.drafts.length === 0"
            description="暂无草稿" :image-size="40"
          />
        </div>
      </div>

      <!-- 历史任务 -->
      <div class="side-group history-group">
        <div class="group-label">
          <el-icon><Clock /></el-icon>
          <span>历史任务</span>
          <span class="group-count">{{ ws.historyItems.length }}</span>
        </div>
        <div class="group-list">
          <div
            v-for="h in ws.historyItems"
            :key="h.id"
            class="side-item history-item"
            @click="ws.openHistoryDetail(h.id)"
          >
            <el-icon class="item-icon"><DocumentCopy /></el-icon>
            <div class="item-text">
              <div class="item-title">{{ h.template_name || '（无模板）' }}</div>
              <div class="item-meta">
                {{ h.created_at }} · {{ h.file_count }} 文件 / {{ h.record_count }} 记录
              </div>
            </div>
          </div>
          <el-empty
            v-if="ws.historyItems.length === 0"
            description="暂无历史" :image-size="40"
          />
        </div>
      </div>
    </aside>

    <!-- ==================== 右侧工作区 ==================== -->
    <section class="workspace">
      <StepBar />
      <main class="workspace-main">
        <!-- 首次使用：放大居中的欢迎引导（之后不再出现） -->
        <div v-if="showWelcome" class="welcome">
          <el-icon class="welcome-icon"><Document /></el-icon>
          <div class="welcome-title">文档信息提取与表格自动填充</div>
          <div class="welcome-desc">
            点击「新建任务」开始；也可以从草稿箱恢复未完成的任务，
            或在历史任务中查看与下载已完成的产物。
          </div>
          <el-button
            type="primary"
            class="welcome-btn"
            @click="handleWelcomeStart"
          >
            <el-icon><Plus /></el-icon>
            <span>新建任务</span>
          </el-button>
        </div>

        <!-- 已初始化但任务上下文正在切换（导出归档/删除后自动续接的瞬间） -->
        <div
          v-else-if="ws.currentDraftId === null && route.path !== '/schemes'"
          v-loading="true"
          element-loading-text="正在准备工作区…"
          element-loading-background="rgba(245,247,250,0.6)"
          class="preparing"
        ></div>

        <router-view v-else />
      </main>
    </section>

    <!-- ==================== 弹窗 ==================== -->
    <TaskDetailDialog
      v-model:visible="historyDetailVisible"
      :task-id="ws.historyDetailId"
    />

  </div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

import StepBar from './components/StepBar.vue'
import TaskDetailDialog from './components/TaskDetailDialog.vue'
import { useWorkspaceStore } from '@/stores/workspaceStore'
import { useFileStore } from '@/stores/fileStore'
import { useResultStore } from '@/stores/resultStore'
import { fetchSchemes } from '@/api/schemes'

const route = useRoute()
const router = useRouter()
const ws = useWorkspaceStore()
const fileStore = useFileStore()
const resultStore = useResultStore()

// ============================================================
// 首次使用标记：localStorage 持久化；已有历史任务也视为已初始化
// ============================================================
const WELCOME_FLAG = 'doc-system-welcome-shown'
const initialized = ref(localStorage.getItem(WELCOME_FLAG) === '1')
const schemeCount = ref(0)

function markInitialized() {
  initialized.value = true
  try { localStorage.setItem(WELCOME_FLAG, '1') } catch { /* 忽略隐私模式 */ }
}

// TaskDetailDialog 的显隐：ws.historyDetailId 变化即打开
const historyDetailVisible = computed({
  get: () => ws.historyDetailId !== null,
  set: (v) => { if (!v) ws.historyDetailId = null },
})

// 欢迎页显示条件：未初始化 + 无任务上下文 + 不在方案页
const showWelcome = computed(
  () =>
    !initialized.value &&
    ws.currentDraftId === null &&
    route.path !== '/schemes'
)

// 步骤路径 → 展示名
const STEP_LABELS = {
  '/upload': '上传文档',
  '/extract': '设置字段',
  '/result': '核对结果',
  '/export': '导出文件',
}
function stepLabel(step) {
  return STEP_LABELS[step] || '上传文档'
}

// ==================== 方案数量角标 ====================
async function loadSchemeCount() {
  try {
    const list = await fetchSchemes()
    schemeCount.value = Array.isArray(list) ? list.length : 0
  } catch {
    schemeCount.value = 0
  }
}

// ==================== 跳转方案页 ====================
function goSchemes() {
  if (route.path !== '/schemes') router.push('/schemes')
}

// ==================== 新建任务 ====================
async function handleNewTask() {
  const target = await ws.createNewTask()
  if (target) {
    markInitialized()
    if (route.path !== target) router.push(target)
    ElMessage.success('已创建新任务')
  }
}

// ==================== 欢迎页点击新建 ====================
async function handleWelcomeStart() {
  const target = await ws.createNewTask()
  if (target) {
    markInitialized()
    router.push(target)
  }
}

// ==================== 恢复草稿 ====================
async function handleRestore(d) {
  suspendAutosave = true
  const target = await ws.restoreDraft(d)
  if (target) {
    markInitialized()
    await router.push(target)
    ElMessage.success(`已恢复草稿「${d.title}」`)
  }
  // 下一个 tick 再恢复自动保存，避免回填触发的 watch 落一次多余请求
  setTimeout(() => { suspendAutosave = false }, 0)
}

// ============================================================
// 自动续接：已初始化用户的任务上下文不应出现空档（欢迎页不再出现）
// 导出归档 / 删除当前草稿导致 currentDraftId 变 null 时，
// 自动恢复最近的草稿或新建一条空任务
// ============================================================
watch(
  () => ws.currentDraftId,
  async (id) => {
    if (id !== null) return
    if (!initialized.value) return
    if (route.path === '/schemes') return

    if (ws.drafts.length > 0) {
      const d = ws.drafts[0]
      suspendAutosave = true
      const target = await ws.restoreDraft(d)
      if (target) {
        if (route.path !== target) router.push(target)
      }
      setTimeout(() => { suspendAutosave = false }, 0)
    } else {
      const target = await ws.createNewTask()
      if (target && route.path !== target) router.push(target)
    }
  }
)

// 从方案页返回时刷新角标数量
watch(
  () => route.path,
  (p) => { if (p !== '/schemes') loadSchemeCount() }
)

// ==================== 自动保存（watch 防抖） ====================
let suspendAutosave = false
let autosaveTimer = null

watch(
  () => [
    fileStore.allFiles,
    resultStore.prompt,
    resultStore.fields,
    resultStore.results,
    resultStore.confirmed,
    resultStore.taskId,
  ],
  () => {
    if (suspendAutosave) return
    if (ws.currentDraftId === null) return
    clearTimeout(autosaveTimer)
    autosaveTimer = setTimeout(() => {
      ws.persistCurrent()
    }, 1500)
  },
  { deep: true }
)

// ==================== 初始化 ====================
onMounted(async () => {
  await Promise.all([ws.loadDrafts(), ws.loadHistory(), loadSchemeCount()])

  const hasLocalContent =
    fileStore.allFiles.length > 0 ||
    resultStore.fields.length > 0 ||
    resultStore.results.length > 0

  if (hasLocalContent) {
    // 刷新前遗留的工作区状态：落为一条草稿，避免丢失
    await ws.persistCurrent()
    markInitialized()
    return
  }

  // 已有历史任务：视作老用户，欢迎页不再呈现
  if (ws.historyItems.length > 0) markInitialized()

  if (initialized.value) {
    if (ws.drafts.length > 0) {
      // 自动进入最近一条草稿
      suspendAutosave = true
      const target = await ws.restoreDraft(ws.drafts[0])
      if (target) router.push(target)
      setTimeout(() => { suspendAutosave = false }, 0)
    } else {
      // 已初始化且无草稿：直接开始一条空任务
      const target = await ws.createNewTask()
      if (target) router.push(target)
    }
  }
  // 未初始化：保持欢迎页，等待用户点击「新建任务」
})
</script>

<style scoped>
.app-shell {
  height: 100vh;
  display: flex;
  overflow: hidden;
  background: #f5f7fa;
}

/* ==================== 侧边栏 ==================== */
.sidebar {
  width: 272px;
  flex-shrink: 0;
  background: #f9fafb;
  border-right: 1px solid #e5e7eb;
  display: flex;
  flex-direction: column;
  padding: 18px 14px 12px;
}

/* ---------- 品牌 ---------- */
.brand {
  display: flex; align-items: center; gap: 12px;
  padding: 2px 6px 18px;
}
.brand-icon { font-size: 34px; color: #409eff; }
.brand-name { font-size: 18px; font-weight: 800; color: #1f2937; line-height: 1.3; }
.brand-sub { font-size: 12px; color: #9ca3af; margin-top: 1px; }

/* ---------- 新建任务（主按钮，最突出） ---------- */
.new-task-btn {
  width: 100%;
  height: 46px;
  justify-content: center;
  margin-bottom: 12px;
  border: none;
  border-radius: 10px;
  background: linear-gradient(135deg, #409eff 0%, #2b7de9 100%);
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  box-shadow: 0 3px 10px rgba(64, 158, 255, 0.28);
}
.new-task-icon { font-size: 18px; margin-right: 4px; }
.new-task-btn:hover,
.new-task-btn:focus {
  background: linear-gradient(135deg, #5da8ff 0%, #3a8bef 100%);
  color: #fff;
  box-shadow: 0 4px 14px rgba(64, 158, 255, 0.38);
}

/* ---------- 方案管理（卡片式入口，位于分组之上） ---------- */
.scheme-entry {
  display: flex; align-items: center; gap: 9px;
  height: 46px;
  padding: 0 14px;
  margin-bottom: 16px;
  background: #fff;
  border: 1px solid #dfe3e8;
  border-radius: 10px;
  cursor: pointer;
  font-size: 14px; font-weight: 700; color: #374151;
  transition: border-color 0.15s, box-shadow 0.15s, color 0.15s;
}
.scheme-entry:hover {
  border-color: #409eff;
  color: #409eff;
  box-shadow: 0 3px 10px rgba(64, 158, 255, 0.16);
}
.scheme-entry.active {
  border-color: #409eff;
  color: #2b7de9;
  background: #eef6ff;
  box-shadow: inset 0 0 0 1px rgba(64, 158, 255, 0.25);
}
.scheme-entry-icon { font-size: 18px; color: #409eff; }
.scheme-entry-name { flex: 1; }
.scheme-entry-count {
  background: #e5e7eb; color: #6b7280;
  border-radius: 11px; padding: 0 8px;
  font-size: 12px; font-weight: 700; line-height: 18px;
}
.scheme-entry.active .scheme-entry-count {
  background: #d3e8ff; color: #2b7de9;
}
.scheme-entry-arrow { font-size: 14px; color: #b5bac2; }
.scheme-entry:hover .scheme-entry-arrow,
.scheme-entry.active .scheme-entry-arrow { color: #409eff; }

/* ---------- 分组 ---------- */
.side-group {
  display: flex;
  flex-direction: column;
  min-height: 0;
  margin-bottom: 12px;
}
.draft-group { flex: 1.1; }
.history-group { flex: 1; }

.group-label {
  display: flex; align-items: center; gap: 7px;
  font-size: 14px; font-weight: 800; color: #4b5563;
  padding: 0 6px 8px;
}
.group-label .el-icon { font-size: 16px; }
.group-count {
  margin-left: auto;
  background: #e5e7eb; color: #6b7280;
  border-radius: 10px; padding: 0 8px;
  font-size: 12px; font-weight: 700; line-height: 18px;
}

.group-list {
  flex: 1; min-height: 0;
  overflow-y: auto;
  display: flex; flex-direction: column; gap: 3px;
}
.group-list :deep(.el-empty) { padding: 10px 0; }
.group-list :deep(.el-empty__description p) { font-size: 12px; }

/* ---------- 条目 ---------- */
.side-item {
  display: flex; align-items: center; gap: 9px;
  padding: 9px 10px; border-radius: 9px;
  cursor: pointer; position: relative;
}
.side-item:hover { background: #eceef1; }
.side-item.active { background: #e1efff; }
.side-item.active .item-title { color: #1d6fd1; }

.item-icon { color: #9ca3af; font-size: 17px; flex-shrink: 0; }
.side-item.active .item-icon { color: #409eff; }
.item-text { flex: 1; min-width: 0; }
.item-title {
  font-size: 13.5px; color: #374151; font-weight: 600;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.item-meta {
  font-size: 11.5px; color: #9ca3af; margin-top: 2px;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.item-delete {
  display: none;
  color: #9ca3af; font-size: 15px; flex-shrink: 0;
}
.item-delete:hover { color: #f56c6c; }
.side-item:hover .item-delete { display: block; }

/* ==================== 工作区 ==================== */
.workspace {
  flex: 1; min-width: 0;
  display: flex; flex-direction: column;
}
.workspace-main {
  flex: 1; min-height: 0;
  overflow-y: auto;
}
.preparing { height: 100%; }

/* ==================== 欢迎页（放大居中，仅首次使用） ==================== */
.welcome {
  height: 100%;
  display: flex; flex-direction: column;
  align-items: center; justify-content: center;
  gap: 22px; padding: 24px;
}
.welcome-icon { font-size: 84px; color: #409eff; }
.welcome-title {
  font-size: 34px; font-weight: 800; color: #1f2937;
  letter-spacing: 1px; text-align: center;
}
.welcome-desc {
  font-size: 16px; color: #6b7280; line-height: 1.9;
  text-align: center; max-width: 640px;
}
.welcome-btn {
  margin-top: 8px;
  height: 54px;
  padding: 0 40px;
  border-radius: 12px;
  font-size: 17px;
  font-weight: 700;
}
.welcome-btn .el-icon { font-size: 20px; margin-right: 4px; }
</style>
