// ============================================================
// fileStore.js —— 文件相关的状态管理
// ============================================================

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useFileStore = defineStore('file', () => {

  const targetFiles = ref([])       // 目标文档原始 File 对象
  const templateFiles = ref([])     // 模板文件原始 File 对象
  const allFiles = ref([])          // 后端解析结果 [{ filename, status, content, kind }]


  /**
   * 可用的目标文件（供 /extract 使用）
   */
  const validTargetFiles = computed(() => {
    const byKind = allFiles.value.filter(
      (item) => item.kind === 'target' && item.status === 'success'
    )
    if (byKind.length > 0) return byKind

    const targetNames = new Set(targetFiles.value.map((f) => f.name))
    return allFiles.value.filter(
      (item) => targetNames.has(item.filename) && item.status === 'success'
    )
  })

  const templateParsedFiles = computed(() => {
    return allFiles.value.filter((item) => item.kind === 'template')
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
      if (item.kind) return item 
      let kind = 'unknown'
      if (targetNames.has(item.filename)) kind = 'target'
      else if (templateNames.has(item.filename)) kind = 'template'
      return { ...item, kind }
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