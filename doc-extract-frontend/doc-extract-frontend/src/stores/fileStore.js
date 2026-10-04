// ============================================================
// fileStore.js —— 文件相关的状态管理
// ============================================================

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useFileStore = defineStore('file', () => {

  const targetFiles = ref([])       // 目标文档原始 File 对象
  const templateFiles = ref([])     // 模板文件原始 File 对象
  const allFiles = ref([])          // 后端解析结果 [{ filename, status, content, role, error }]


  /**
   * 可用的目标文件（供 /extract 使用）
   */
  const validTargetFiles = computed(() => {
    const byRole = allFiles.value.filter(
      (item) => item.role === 'target' && item.status === 'success'
    )
    if (byRole.length > 0) return byRole

    const targetNames = new Set(targetFiles.value.map((f) => f.name))
    return allFiles.value.filter(
      (item) => targetNames.has(item.filename) && item.status === 'success'
    )
  })

  const templateParsedFiles = computed(() => {
    return allFiles.value.filter((item) => item.role === 'template')
  })

  /**
   * 是否已经上传并解析过
   */
  const hasUploaded = computed(() => allFiles.value.length > 0)


  function addFile(type, files) {
    if (type !== 'target' && type !== 'template') {
      console.warn(`[fileStore] addFile: 未知的 type="${type}"`)
      return
    }
    const listRef = type === 'target' ? targetFiles : templateFiles
    files.forEach((file) => {
      const exists = listRef.value.some((f) => f.name === file.name)
      if (!exists) {
        listRef.value.push(file)
      } else {
        console.warn(`[fileStore] 文件 "${file.name}" 已存在，跳过`)
      }
    })
  }

  function removeFile(type, filename) {
    const listRef = type === 'target' ? targetFiles : templateFiles
    listRef.value = listRef.value.filter((f) => f.name !== filename)
    allFiles.value = allFiles.value.filter((item) => item.filename !== filename)
  }

  function setAllFiles(files) {
    const targetNames = new Set(targetFiles.value.map((f) => f.name))
    const templateNames = new Set(templateFiles.value.map((f) => f.name))

    allFiles.value = files.map((item) => {
      // 后端已直接返回 role（target/template），优先使用
      if (item.role) return item
      // 兜底：旧数据或 role 缺失时，按文件名在本地两个列表中反查
      let role = 'unknown'
      if (targetNames.has(item.filename)) role = 'target'
      else if (templateNames.has(item.filename)) role = 'template'
      return { ...item, role }
    })
  }

  function clearAll() {
    targetFiles.value = []
    templateFiles.value = []
    allFiles.value = []
  }
  return {
    // state
    targetFiles,
    templateFiles,
    allFiles,
    // getters
    validTargetFiles,
    templateParsedFiles,   
    hasUploaded,
    // actions
    addFile,
    removeFile,
    setAllFiles,
    clearAll,
  }
}, {
  persist: {
    key: 'doc-extract-file',
    storage: localStorage,
    paths: ['allFiles'],
  },
})