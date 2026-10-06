// ============================================================
// workspaceStore.js —— 工作区管理（任务即草稿范式）
// 职责：
//   1. 草稿（drafts）列表 / 当前草稿 id / 自动保存 / 恢复 / 删除
//   2. 历史任务列表 / 导出完成后草稿转历史
//   3. 新建任务
// 与 fileStore / resultStore 协作：payload 从二者组装
// ============================================================

import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  fetchDrafts,
  saveDraft,
  fetchDraftDetail,
  deleteDraft,
  renameDraft,
  batchDeleteDrafts,
} from '@/api/drafts'
import {
  fetchHistoryList,
  renameHistory,
  batchDeleteHistory,
} from '@/api/history'
import { useFileStore } from '@/stores/fileStore'
import { useResultStore } from '@/stores/resultStore'
import { useFieldStore } from '@/stores/fieldStore'
import { ElMessage, ElMessageBox } from 'element-plus'

export const useWorkspaceStore = defineStore('workspace', () => {

  const fileStore = useFileStore()
  const resultStore = useResultStore()
  const fieldStore = useFieldStore()

  // ==================== 状态 ====================
  const currentDraftId = ref(null)
  const drafts = ref([])
  const historyItems = ref([])
  const historyDetailId = ref(null)  // 打开详情弹窗的历史任务 id

  // 当前任务是否已成功生成文件（生成后不自动跳转，由用户决定何时开启新任务）
  const taskCompleted = ref(false)
  // 已生成产物的信息：{ filename, downloadUrl }
  const completedExport = ref(null)

  // ==================== 派生 ====================
  // 当前工作区是否为空（连一条草稿都没有）
  const isEmptyWorkspace = computed(() =>
    currentDraftId.value === null && drafts.value.length === 0
  )

  // 按当前 stores 推断应处于哪一步
  // 注意：只选了方案（模板/字段/提示词已填入）但还没传目标文档时，
  // 停留在一阶段上传页，恢复草稿不跳到二阶段
  function inferStep() {
    if (resultStore.results.length > 0) {
      return resultStore.confirmed ? '/export' : '/result'
    }
    if (fileStore.validTargetFiles.length > 0) return '/extract'
    return '/upload'
  }

  // 当前 stores 是否有任何实质内容
  function hasContent() {
    return (
      fileStore.allFiles.length > 0 ||
      !!resultStore.prompt ||
      resultStore.fields.length > 0 ||
      resultStore.results.length > 0
    )
  }

  // 组装草稿 payload
  function buildPayload() {
    return {
      version: 1,
      files: fileStore.allFiles,
      prompt: resultStore.prompt,
      fields: fieldStore.fields.length > 0 ? [...fieldStore.fields] : resultStore.fields,
      schemeId: resultStore.schemeId,
      results: resultStore.results,
      confirmed: resultStore.confirmed,
      taskId: resultStore.taskId,
      // 已生成产物的信息，使刷新/恢复后仍能展示结果卡片
      completed: taskCompleted.value ? { ...completedExport.value } : null,
    }
  }

  // 草稿标题：优先目标文档名，否则交后端自动命名「草稿（n）」
  function resolveTitle() {
    const target = fileStore.allFiles.find(
      (f) => f.role === 'target' && f.status === 'success'
    )
    return target?.filename || ''
  }

  // ==================== 列表加载 ====================
  async function loadDrafts() {
    try {
      const data = await fetchDrafts()
      drafts.value = data.items || []
    } catch {
      // 角标/列表加载失败静默
    }
  }

  async function loadHistory() {
    try {
      const data = await fetchHistoryList(1, 50)
      historyItems.value = data.items || []
    } catch {
      // 静默
    }
  }

  // ==================== 自动保存（新建或更新当前草稿） ====================
  let saving = Promise.resolve()

  async function persistCurrent() {
    // 串行化，避免防抖触发的并发保存互相覆盖
    saving = saving.then(async () => {
      try {
        const body = {
          title: resolveTitle(),
          step: inferStep(),
          template_name:
            fileStore.allFiles.find((f) => f.role === 'template')?.filename || '',
          file_count: fileStore.allFiles.filter(
            (f) => f.role === 'target' && f.status === 'success'
          ).length,
          field_count: fieldStore.fields.length || resultStore.fields.length,
          payload: buildPayload(),
          draft_id: currentDraftId.value,
        }
        const res = await saveDraft(body)
        currentDraftId.value = res.id
        if (res.evicted) {
          ElMessage.warning(`草稿箱已满，最早草稿「${res.evicted}」已自动删除`)
        }
        await loadDrafts()
      } catch {
        // 自动保存失败不打扰用户（request 拦截器已统一提示网络错误）
      }
    })
    return saving
  }

  // ==================== 标记文件已生成（不归档、不跳转） ====================
  function setTaskCompleted(info) {
    taskCompleted.value = true
    completedExport.value = {
      filename: info?.filename || '',
      downloadUrl: info?.downloadUrl || '',
    }
  }

  // 归档当前已完成任务的草稿：删除草稿并重置完成标记（currentDraftId 不动，
  // 由后续的新建/恢复流程赋新值，避免触发自动续接 watcher）
  async function archiveCurrentDraft() {
    if (currentDraftId.value !== null) {
      const id = currentDraftId.value
      try { await deleteDraft(id) } catch { /* 删除失败不阻塞 */ }
    }
    taskCompleted.value = false
    completedExport.value = null
  }

  // ==================== 新建任务 ====================
  async function createNewTask() {
    // 当前草稿完全为空：不重复创建
    if (
      currentDraftId.value !== null &&
      !hasContent() &&
      !taskCompleted.value
    ) {
      return '/upload'
    }
    if (currentDraftId.value !== null) {
      // 已完成任务：归档其草稿；否则先保住当前草稿
      if (taskCompleted.value) await archiveCurrentDraft()
      else await persistCurrent()
    }
    // 新建一条空草稿（后端自动命名草稿（n））
    try {
      const res = await saveDraft({
        title: '', step: '/upload', payload: { version: 1 },
      })
      currentDraftId.value = res.id
      fileStore.clearAll()
      resultStore.clearAll()
      fieldStore.clearFields()
      await loadDrafts()
      return '/upload'
    } catch {
      return null
    }
  }

  // ==================== 恢复草稿 ====================
  async function restoreDraft(draft) {
    if (currentDraftId.value === draft.id) {
      return draft.step || '/upload'
    }
    // 当前任务已完成：归档其草稿；否则先保存当前草稿
    if (currentDraftId.value !== null) {
      if (taskCompleted.value) await archiveCurrentDraft()
      else await persistCurrent()
    }
    try {
      const detail = await fetchDraftDetail(draft.id)
      const p = detail.payload || {}
      fileStore.clearAll()
      resultStore.clearAll()
      if (Array.isArray(p.files) && p.files.length) {
        fileStore.setAllFiles(p.files)
      }
      resultStore.setPrompt(p.prompt || '')
      resultStore.setFields(p.fields || [])
      // 同步字段编辑 store：保证恢复草稿后二阶段字段标签与方案填充内容可见
      fieldStore.setFields(p.fields || [])
      resultStore.setSchemeId(p.schemeId || null)
      if (Array.isArray(p.results) && p.results.length) {
        resultStore.setResults(p.results)
      }
      if (p.confirmed) resultStore.setConfirmed(true)
      resultStore.setTaskId(p.taskId || '')
      // 恢复已完成产物信息（若该草稿是在生成后保存的）
      if (p.completed && p.completed.downloadUrl) {
        taskCompleted.value = true
        completedExport.value = {
          filename: p.completed.filename || '',
          downloadUrl: p.completed.downloadUrl,
        }
      } else {
        taskCompleted.value = false
        completedExport.value = null
      }
      currentDraftId.value = detail.id
      return detail.step || '/upload'
    } catch {
      return null
    }
  }

  // ==================== 重命名 / 批量删除 ====================
  async function renameDraftItem(draft, title) {
    try {
      await renameDraft(draft.id, title)
      await loadDrafts()
      ElMessage.success('重命名成功')
      return true
    } catch {
      return false
    }
  }

  async function batchRemoveDrafts(ids) {
    try {
      await batchDeleteDrafts(ids)
    } catch {
      return
    }
    await loadDrafts()
    if (ids.includes(currentDraftId.value)) {
      // 当前草稿被批量删除：清空工作区，自动续接 watcher 会恢复其余草稿
      currentDraftId.value = null
      fileStore.clearAll()
      resultStore.clearAll()
      fieldStore.clearFields()
    }
    ElMessage.success(`已删除 ${ids.length} 条草稿`)
  }

  async function renameHistoryItem(taskId, title) {
    try {
      await renameHistory(taskId, title)
      await loadHistory()
      ElMessage.success('重命名成功')
      return true
    } catch {
      return false
    }
  }

  async function batchRemoveHistory(ids) {
    try {
      await batchDeleteHistory(ids)
    } catch {
      return
    }
    await loadHistory()
    if (ids.includes(historyDetailId.value)) historyDetailId.value = null
    ElMessage.success(`已删除 ${ids.length} 条历史任务`)
  }

  // ==================== 删除草稿 ====================
  async function removeDraft(draft) {
    try {
      await ElMessageBox.confirm(
        `确定删除草稿「${draft.title}」吗？删除后不可恢复。`,
        '删除草稿',
        { type: 'warning', confirmButtonText: '删除', cancelButtonText: '取消' }
      )
    } catch {
      return  // 用户取消
    }
    const deletingCurrent = currentDraftId.value === draft.id
    try {
      await deleteDraft(draft.id)
    } catch {
      return
    }
    // 先刷新列表，再让 currentDraftId 失效：
    // 否则 App 的自动续接 watcher 可能拿到含已删条目的旧列表
    await loadDrafts()
    if (deletingCurrent) {
      currentDraftId.value = null
      fileStore.clearAll()
      resultStore.clearAll()
      fieldStore.clearFields()
    }
    ElMessage.success('草稿已删除')
  }

  // ==================== 历史详情 ====================
  function openHistoryDetail(taskId) {
    historyDetailId.value = taskId
  }

  // ==================== 导出完成：草稿转历史 ====================
  async function markCompleted() {
    const draftId = currentDraftId.value
    if (draftId !== null) {
      try {
        await deleteDraft(draftId)
      } catch {
        // 删除失败不影响成功流程
      }
    }
    // 先删草稿并刷新两个列表，最后才让 currentDraftId 失效，
    // 使 App 的自动续接逻辑看到准确的最新状态
    await Promise.all([loadDrafts(), loadHistory()])
    currentDraftId.value = null
    taskCompleted.value = false
    completedExport.value = null
  }

  return {
    // state
    currentDraftId,
    drafts,
    historyItems,
    historyDetailId,
    taskCompleted,
    completedExport,
    // getters
    isEmptyWorkspace,
    // actions
    loadDrafts,
    loadHistory,
    persistCurrent,
    createNewTask,
    restoreDraft,
    removeDraft,
    renameDraftItem,
    batchRemoveDrafts,
    renameHistoryItem,
    batchRemoveHistory,
    openHistoryDetail,
    markCompleted,
    setTaskCompleted,
    inferStep,
  }
})
