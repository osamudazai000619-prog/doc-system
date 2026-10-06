<!-- ============================================================
     StepBar.vue —— 顶部步骤条组件
     作用：展示 4 个流程步骤，根据当前路由高亮
     ============================================================ -->

<template>
  <!-- el-card 是 Element Plus 的卡片容器，用来包一层白底阴影 -->
  <el-card class="step-bar-card" shadow="never">
    <!-- el-steps：Element Plus 的步骤条组件
         :active="activeStep"  → 当前进行到第几步（从 0 开始计数）
         finish-status="success" → 已完成的步骤显示为绿色勾
         align-center → 步骤标题居中 -->
    <el-steps :active="activeStep" finish-status="success" align-center>
      <el-step title="上传文档" description="选择目标文档与模板" />
      <el-step title="设置字段" description="配置需要提取的信息" />
      <el-step title="核对结果" description="检查并修正提取内容" />
      <el-step title="导出文件" description="映射模板并下载" />
    </el-steps>
  </el-card>
</template>

<script setup>
// ============================================================
// 逻辑部分
// ============================================================
import { computed } from 'vue'
import { useRoute } from 'vue-router'

// 拿到当前路由对象（用来判断当前在哪个页面）
const route = useRoute()

// 路由路径 和 步骤序号 的映射表
// 0 = 上传文档，1 = 设置字段，2 = 核对结果，3 = 导出文件
const pathToStep = {
  '/upload': 0,
  '/extract': 1,
  '/result': 2,
  '/export': 3,
}

// 计算当前应该高亮第几步
// 如果当前路由不在表里（比如根路径 /），默认 -1，即所有步骤都不高亮
const activeStep = computed(() => {
  return pathToStep[route.path] ?? -1
})
</script>

<style scoped>
/* ============================================================
   步骤条：深色玻璃卡片 + 自定义圆圈
   ============================================================ */
.step-bar-card {
  margin: var(--de-s4) var(--de-s6) 0;
  border-radius: var(--de-r-md);
}
.step-bar-card :deep(.el-card__body) {
  padding: var(--de-s5) var(--de-s7) var(--de-s4);
}

/* ---------- 圆圈序号 ---------- */
.step-bar-card :deep(.el-step__icon) {
  width: 32px;
  height: 32px;
  background: transparent;
  border: 1.5px solid var(--de-border-strong);
  color: var(--de-text-3);
  font-size: var(--de-fs-2);
  transition: all 0.2s;
}
.step-bar-card :deep(.el-step__icon.is-text) { font-weight: 700; }

/* 当前步骤：品牌渐变实心 */
.step-bar-card :deep(.el-step.is-process .el-step__icon) {
  background: linear-gradient(135deg, var(--de-primary), var(--de-primary-2));
  border-color: transparent;
  color: var(--de-on-primary);
  box-shadow: var(--de-glow);
}
/* 已完成步骤：品牌淡底 + 主色描边 */
.step-bar-card :deep(.el-step.is-finish .el-step__icon) {
  background: var(--de-primary-soft);
  border-color: var(--de-primary-line);
  color: var(--de-primary);
}

/* ---------- 标题与描述 ---------- */
.step-bar-card :deep(.el-step__title) {
  font-size: var(--de-fs-3);
  font-weight: 650;
  line-height: 32px;
  color: var(--de-text-1);
}
.step-bar-card :deep(.el-step__title.is-process) { color: var(--de-primary); }
.step-bar-card :deep(.el-step__title.is-wait) {
  color: var(--de-text-3);
  font-weight: 550;
}
.step-bar-card :deep(.el-step__title.is-finish) { color: var(--de-text-1); }
.step-bar-card :deep(.el-step__description) {
  font-size: var(--de-fs-1);
  color: var(--de-text-3);
  padding-top: 2px;
}

/* ---------- 连接线 ---------- */
.step-bar-card :deep(.el-step__line) {
  top: 16px;
  background-color: var(--de-border);
}
.step-bar-card :deep(.el-step__line-inner) {
  border-color: var(--de-primary-line);
  border-width: 1px;
}
.step-bar-card :deep(.el-step__head) { width: 32px; }
</style>
