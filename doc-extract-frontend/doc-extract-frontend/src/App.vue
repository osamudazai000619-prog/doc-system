<!-- ============================================================
     App.vue —— 全局布局
     结构：Header（标题） + StepBar（步骤条） + router-view（内容）
     ============================================================ -->

<template>
  <!-- 外层容器，撑满整个屏幕 -->
  <div class="app-container">

    <!-- ==================== 顶部标题栏 ==================== -->
    <header class="app-header">
      <div class="app-title">
        <!-- 图标：用 Element Plus 的 Document 图标 -->
        <el-icon class="title-icon"><Document /></el-icon>
        <span>文档信息提取与表格自动填充系统</span>
      </div>
      <div class="app-subtitle">基于大语言模型 · 比赛项目</div>
    </header>

    <!-- ==================== 步骤条 ==================== -->
    <!-- 这里的 StepBar 是我们在上面建的组件 -->
    <!-- 它会自己根据当前路由高亮对应的步骤 -->
    <StepBar />

    <!-- ==================== 内容区 ==================== -->
    <!-- router-view 是"占位符"，路由匹配到的页面会渲染在这里 -->
    <!-- 例如访问 /upload 时，UploadPage.vue 的内容会出现在这里 -->
    <main class="app-main">
      <router-view />
    </main>

  </div>
</template>

<script setup>
// ============================================================
// 引入 StepBar 组件
// ============================================================
import StepBar from './components/StepBar.vue'

// 注意：Document 图标已经在 main.js 里全局注册过，
// 这里不需要再 import，直接用 <Document /> 即可。
</script>

<style scoped>
/* ==================== 外层容器 ==================== */
.app-container {
  min-height: 100vh;               /* 至少撑满一屏 */
  background-color: #f5f7fa;       /* 浅灰底色，让卡片更醒目 */
  display: flex;                   /* 用 flex 纵向排列 */
  flex-direction: column;
}

/* ==================== 顶部标题栏 ==================== */
.app-header {
  background: linear-gradient(135deg, #409eff 0%, #2b7cd3 100%);
  color: #fff;
  padding: 16px 32px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  display: flex;                   /* 标题和副标题左右分布 */
  align-items: center;
  justify-content: space-between;
}

.app-title {
  font-size: 20px;
  font-weight: 600;
  letter-spacing: 1px;
  display: flex;
  align-items: center;
  gap: 10px;                       /* 图标和文字间距 */
}

.title-icon {
  font-size: 24px;
}

.app-subtitle {
  font-size: 13px;
  opacity: 0.85;
}

/* ==================== 内容区 ==================== */
.app-main {
  flex: 1;                         /* 占据剩余高度 */
  padding: 0 0 32px 0;             /* 底部留白 */
}
</style>