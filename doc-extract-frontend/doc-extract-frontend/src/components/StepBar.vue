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
   步骤条：无连接线 · 序号徽章（圆内嵌浅色方边）
   ------------------------------------------------------------
   注意：Element Plus 把 is-process / is-finish 等状态类加在
   .el-step__head（以及标题）上，.el-step__icon 自身只有 is-text，
   所以圆圈的状态选择器必须从 .el-step__head.is-xxx 往下写。
   ============================================================ */
.step-bar-card {
  margin: var(--de-s4) var(--de-s6) 0;
  border-radius: var(--de-r-md);
}
.step-bar-card :deep(.el-card__body) {
  padding: var(--de-s6) var(--de-s6) var(--de-s5);
}

/* ---------- 连接线：全部移除 ---------- */
.step-bar-card :deep(.el-step__line),
.step-bar-card :deep(.el-step__line-inner) { display: none; }

/* ---------- 圆圈序号：玻璃质感实心球 ---------- */
/* head 必须保持组件默认的满宽（width:100%），由 flex 把 48px 图标推到列中心；
   若给 head 设 width:48px，块级元素默认靠左，圆圈会跑到左上方 */
.step-bar-card :deep(.el-step__head) {
  display: flex;
  justify-content: center;
}
.step-bar-card :deep(.el-step__icon) {
  position: relative;
  width: 48px;
  height: 48px;
  /* 白色半透明玻璃填充：左上亮、右下收，形成球体感 */
  background: linear-gradient(145deg, rgba(255, 255, 255, 0.78), rgba(255, 255, 255, 0.42));
  border: 1px solid rgba(255, 255, 255, 0.75);
  /* 外柔光 + 顶部内高光 */
  box-shadow:
    0 0 20px rgba(200, 230, 255, 0.55),
    inset 0 1px 5px rgba(255, 255, 255, 0.65);
  color: #ffffff;                 /* 等待态白色亮序号 */
  font-size: var(--de-fs-4);
  font-weight: 700;
  transition: all 0.2s;
}

/* 当前步骤：青蓝渐变实心球 + 深色数字 + 青色光晕 */
.step-bar-card :deep(.el-step__head.is-process .el-step__icon) {
  background: linear-gradient(135deg, var(--de-primary), var(--de-primary-2));
  border-color: rgba(255, 255, 255, 0.5);
  color: var(--de-on-primary);
  box-shadow:
    0 0 20px rgba(34, 211, 238, 0.55),
    inset 0 1px 3px rgba(255, 255, 255, 0.45);
}
/* 已完成步骤：青色玻璃球（finish-status="success" 实际类为 is-success） */
.step-bar-card :deep(.el-step__head.is-finish .el-step__icon),
.step-bar-card :deep(.el-step__head.is-success .el-step__icon) {
  background: linear-gradient(145deg, rgba(34, 211, 238, 0.40), rgba(99, 102, 241, 0.28));
  border-color: rgba(103, 232, 249, 0.6);
  color: #eafdff;
  box-shadow:
    0 0 14px rgba(34, 211, 238, 0.35),
    inset 0 1px 3px rgba(255, 255, 255, 0.3);
}

/* ---------- 标题与描述 ---------- */
.step-bar-card :deep(.el-step__main) {
  margin-top: var(--de-s2);
  text-align: center;
}
.step-bar-card :deep(.el-step__title) {
  font-size: var(--de-fs-4);
  font-weight: 600;
  line-height: 24px;
  color: var(--de-text-2);
}
.step-bar-card :deep(.el-step__title.is-process) {
  color: var(--de-primary);
  font-weight: 650;
}
.step-bar-card :deep(.el-step__title.is-wait) {
  color: var(--de-text-3);
  font-weight: 550;
}
.step-bar-card :deep(.el-step__title.is-finish),
.step-bar-card :deep(.el-step__title.is-success) { color: var(--de-text-1); }
.step-bar-card :deep(.el-step__description) {
  margin-top: 2px;
  font-size: var(--de-fs-1);
  line-height: 20px;
  white-space: nowrap;      /* 四步等宽列较窄，描述强制单行，避免折成两行显乱 */
  color: var(--de-text-3);
}
</style>
