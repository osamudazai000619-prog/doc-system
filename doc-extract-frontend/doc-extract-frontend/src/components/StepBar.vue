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
/* scoped：表示这些样式只作用于当前组件，不影响其他组件 */

.step-bar-card {
  margin: 18px 24px 0 24px;  /* 上 右 下 左 */
  border-radius: 12px;
}
.step-bar-card :deep(.el-card__body) {
  padding: 22px 32px 18px;
}

/* ---------- 放大圆圈序号 ---------- */
.step-bar-card :deep(.el-step__icon) {
  width: 38px;
  height: 38px;
  font-size: 18px;
}
.step-bar-card :deep(.el-step__icon.is-text) {
  font-size: 17px;
  font-weight: 700;
}

/* ---------- 放大标题与描述 ---------- */
.step-bar-card :deep(.el-step__title) {
  font-size: 17px;
  font-weight: 700;
  line-height: 38px;
}
.step-bar-card :deep(.el-step__description) {
  font-size: 13px;
  line-height: 1.6;
  padding-top: 2px;
}

/* ---------- 连接线随圆圈加粗 ---------- */
.step-bar-card :deep(.el-step__line) {
  top: 19px;
}
.step-bar-card :deep(.el-step__head) {
  width: 38px;
}
</style>