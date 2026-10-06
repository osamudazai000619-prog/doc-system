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
/* ============================================================
   App 外壳：深色玻璃侧边栏 + 工作区
   颜色 / 圆角 / 阴影全部取自 style.css 的 --de-* token
   ============================================================ */
.app-shell {
  height: 100vh;
  display: flex;
  overflow: hidden;
  color: var(--de-text-2);
}

/* ==================== 侧边栏 ==================== */
.sidebar {
  width: 274px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  padding: var(--de-s5) var(--de-s3) var(--de-s3);
  background: var(--de-sidebar);
  border-right: 1px solid var(--de-border);
  backdrop-filter: blur(16px);
}

/* ---------- 品牌 ---------- */
.brand {
  display: flex;
  align-items: center;
  gap: var(--de-s3);
  padding: 0 var(--de-s1) var(--de-s6);
}
.brand-icon {
  display: grid;
  place-items: center;
  width: 40px;
  height: 40px;
  flex: none;
  font-size: var(--de-fs-6);
  border-radius: var(--de-r-sm);
  color: var(--de-on-primary);
  background: linear-gradient(135deg, var(--de-primary), var(--de-primary-2));
  box-shadow: var(--de-glow);
}
.brand-name {
  font-size: var(--de-fs-4);
  font-weight: 650;
  color: var(--de-text-1);
  line-height: 1.3;
  letter-spacing: -0.2px;
}
.brand-sub {
  font-size: var(--de-fs-1);
  color: var(--de-text-3);
  margin-top: 2px;
}

/* ---------- 新建任务（主行动点） ---------- */
.new-task-btn {
  width: 100%;
  height: 42px;
  justify-content: center;
  margin-bottom: var(--de-s3);
  border: none;
  border-radius: var(--de-r-sm);
  background: linear-gradient(135deg, var(--de-primary), var(--de-primary-2));
  color: var(--de-on-primary);
  font-size: var(--de-fs-3);
  font-weight: 700;
  box-shadow: var(--de-glow);
}
.new-task-btn:hover,
.new-task-btn:focus {
  background: linear-gradient(135deg, var(--de-primary-lite), var(--de-primary-2-lite));
  color: var(--de-on-primary);
  box-shadow: 0 3px 22px rgba(34, 211, 238, 0.45);
}
.new-task-icon { font-size: var(--de-fs-5); margin-right: var(--de-s1); }

/* ---------- 方案管理入口 ---------- */
.scheme-entry {
  display: flex;
  align-items: center;
  gap: var(--de-s2);
  height: 42px;
  padding: 0 var(--de-s3);
  margin-bottom: var(--de-s4);
  background: var(--de-surface-2);
  border: 1px solid var(--de-border);
  border-radius: var(--de-r-sm);
  cursor: pointer;
  font-size: var(--de-fs-3);
  font-weight: 600;
  color: var(--de-text-2);
  transition: border-color 0.16s, background-color 0.16s, color 0.16s;
}
.scheme-entry:hover {
  border-color: var(--de-primary-line);
  background: var(--de-surface-1);
  color: var(--de-text-1);
}
.scheme-entry.active {
  border-color: var(--de-primary-line);
  background: var(--de-primary-soft);
  color: var(--de-primary);
}
.scheme-entry-icon { font-size: var(--de-fs-5); color: var(--de-primary); }
.scheme-entry-name { flex: 1; }
.scheme-entry-count {
  padding: 0 var(--de-s2);
  border-radius: var(--de-r-sm);
  background: rgba(255, 255, 255, 0.09);
  color: var(--de-text-3);
  font-size: var(--de-fs-1);
  font-weight: 700;
  line-height: 18px;
}
.scheme-entry.active .scheme-entry-count {
  background: var(--de-primary-soft);
  color: var(--de-primary);
}
.scheme-entry-arrow { font-size: var(--de-fs-2); color: var(--de-text-3); }
.scheme-entry:hover .scheme-entry-arrow,
.scheme-entry.active .scheme-entry-arrow { color: var(--de-primary); }

/* ---------- 分组（草稿箱 / 历史任务） ---------- */
.side-group {
  display: flex;
  flex-direction: column;
  min-height: 0;
  margin-bottom: var(--de-s3);
}
.draft-group { flex: 1.1; }
.history-group { flex: 1; }

.group-label {
  display: flex;
  align-items: center;
  gap: var(--de-s1);
  padding: 0 var(--de-s2) var(--de-s2);
  font-size: var(--de-fs-2);
  font-weight: 700;
  letter-spacing: 0.3px;
  color: var(--de-text-3);
}
.group-label .el-icon { font-size: var(--de-fs-4); }
.group-count {
  margin-left: auto;
  padding: 0 var(--de-s2);
  border-radius: var(--de-r-sm);
  background: rgba(255, 255, 255, 0.09);
  color: var(--de-text-3);
  font-size: var(--de-fs-1);
  font-weight: 700;
  line-height: 18px;
}

.group-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.group-list :deep(.el-empty) { padding: var(--de-s2) 0; }
.group-list :deep(.el-empty__description p) { font-size: var(--de-fs-1); }

/* ---------- 条目 ---------- */
.side-item {
  display: flex;
  align-items: center;
  gap: var(--de-s2);
  padding: var(--de-s2);
  border-radius: var(--de-r-sm);
  border: 1px solid transparent;
  cursor: pointer;
  position: relative;
  transition: background-color 0.14s;
}
.side-item:hover { background: rgba(255, 255, 255, 0.06); }
.side-item.active {
  background: var(--de-primary-soft);
  border-color: var(--de-primary-line);
}
.side-item.active .item-title { color: var(--de-primary); }
.side-item.active .item-icon { color: var(--de-primary); }

.item-icon { color: var(--de-text-3); font-size: var(--de-fs-4); flex-shrink: 0; }
.item-text { flex: 1; min-width: 0; }
.item-title {
  font-size: var(--de-fs-2);
  color: var(--de-text-1);
  font-weight: 600;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-meta {
  font-size: var(--de-fs-1);
  color: var(--de-text-3);
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-delete {
  display: none;
  color: var(--de-text-3);
  font-size: var(--de-fs-4);
  flex-shrink: 0;
}
.item-delete:hover { color: var(--de-danger); }
.side-item:hover .item-delete { display: block; }

/* ==================== 工作区 ==================== */
.workspace {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
}
.workspace-main {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
}
.preparing { height: 100%; }

/* ==================== 欢迎页 ==================== */
.welcome {
  height: 100%;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--de-s6);
  padding: var(--de-s6);
}
.welcome-icon {
  display: grid;
  place-items: center;
  width: 92px;
  height: 92px;
  font-size: 44px;
  border-radius: var(--de-r-lg);
  color: var(--de-on-primary);
  background: linear-gradient(135deg, var(--de-primary), var(--de-primary-2));
  box-shadow: 0 12px 48px rgba(34, 211, 238, 0.35);
}
.welcome-title {
  font-size: var(--de-fs-7);
  font-weight: 650;
  color: var(--de-text-1);
  text-align: center;
  letter-spacing: -0.4px;
}
.welcome-desc {
  font-size: var(--de-fs-3);
  color: var(--de-text-2);
  line-height: 1.9;
  text-align: center;
  max-width: 620px;
}
.welcome-btn {
  margin-top: var(--de-s1);
  height: 48px;
  padding: 0 var(--de-s8);
  border-radius: var(--de-r-sm);
  font-size: var(--de-fs-4);
  font-weight: 700;
}
.welcome-btn .el-icon { font-size: var(--de-fs-5); margin-right: var(--de-s1); }
</style>
